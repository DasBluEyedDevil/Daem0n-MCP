"""Staged, rebuildable dense retrieval projection lifecycle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import sqlite3
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from ..event_store import canonical_json_bytes, deterministic_id, sha256_json
from .providers import (
    DENSE_BUILDER_VERSION,
    build_dense_point_payload,
    create_qdrant_client,
    dense_builder_contract,
    dense_manifest_details,
)


_WORKSPACE_ID = re.compile(r"^ws_[0-9a-f]{24}$")
_CLIENT_METHODS = (
    "create_collection",
    "delete_collection",
    "upsert",
    "retrieve",
    "count",
)


class DenseProjectionBuildError(RuntimeError):
    """A dense staging generation could not be validated or activated."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class DenseProjectionBuildResult:
    projection_name: str
    generation: int
    status: str
    row_count: int
    source_event_count: int
    source_event_root_hash: str
    content_digest: str
    build_config_hash: str
    builder_contract_hash: str
    collection_name: str
    staging_manifest_id: str
    dry_run: bool = False
    capability_status: str = "ready"
    capability_reason: str | None = None
    provider_key: str = ""
    model_id: str = ""
    dimension: int = 0
    active_manifest_id: str | None = None
    active_generation: int | None = None
    active_status: str | None = None
    active_row_count: int = 0
    active_content_digest: str | None = None
    row_count_delta: int = 0
    content_digest_changed: bool = True
    reused: bool = False


@dataclass(frozen=True, slots=True)
class _DenseRecord:
    record_id: str
    content: str
    content_hash: str
    source_event_id: str


def _point_field(point: object, field_name: str) -> object:
    if isinstance(point, Mapping):
        return point.get(field_name)
    return getattr(point, field_name, None)


class DenseProjectionBuilder:
    """Build and atomically activate one isolated Qdrant generation."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        provider_key: str,
        model_id: str,
        dimension: int,
        encoder: object,
        query_prefix: str | None = None,
        client: object | None = None,
        qdrant_path: str | os.PathLike[str] | None = None,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        timeout_seconds: float = 5.0,
        client_factory: Callable[..., object] | None = None,
        qdrant_models: object | None = None,
        collection_prefix: str = "daem0nmcp",
        clock_us: Callable[[], int] | None = None,
    ) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise ValueError("a SQLite connection is required")
        self.connection = connection
        self.provider_key = provider_key
        self.model_id = model_id
        self.dimension = dimension
        self.encoder = encoder
        if query_prefix is not None and (
            not isinstance(query_prefix, str) or len(query_prefix) > 4_096
        ):
            raise ValueError("encoder query prefix is invalid")
        self.query_prefix = query_prefix
        self.client = client
        if client is not None and any(
            value is not None
            for value in (
                qdrant_path,
                qdrant_url,
                qdrant_api_key,
                client_factory,
            )
        ):
            raise ValueError(
                "explicit client cannot be combined with Qdrant configuration"
            )
        if qdrant_path is not None and qdrant_url is not None:
            raise ValueError("qdrant_path and qdrant_url are mutually exclusive")
        if qdrant_api_key is not None and qdrant_url is None:
            raise ValueError("qdrant_api_key requires qdrant_url")
        if client_factory is not None and not callable(client_factory):
            raise ValueError("client_factory must be callable")
        if isinstance(timeout_seconds, bool) or not isinstance(
            timeout_seconds, (int, float)
        ):
            raise ValueError("timeout_seconds must be a positive finite number")
        try:
            timeout = float(timeout_seconds)
        except OverflowError as exc:
            raise ValueError(
                "timeout_seconds must be a positive finite number"
            ) from exc
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
            raise ValueError("timeout_seconds must be a positive finite number")
        self._qdrant_path = qdrant_path
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key
        self._timeout_seconds = timeout
        self._client_factory = client_factory
        self._qdrant_models = qdrant_models
        self.collection_prefix = collection_prefix
        self._clock_us = clock_us or (lambda: time.time_ns() // 1_000)

    def rebuild(
        self, workspace_id: str, *, dry_run: bool = False
    ) -> DenseProjectionBuildResult:
        if not isinstance(workspace_id, str) or _WORKSPACE_ID.fullmatch(
            workspace_id
        ) is None:
            raise DenseProjectionBuildError(
                "INVALID_WORKSPACE_ID", "workspace identifier is invalid"
            )
        self._require_schema()
        if self.connection.in_transaction:
            raise DenseProjectionBuildError(
                "DENSE_BUILD_TRANSACTION_OPEN",
                "dense projection build requires an idle connection",
            )
        (
            records,
            event_count,
            event_root,
            cursor,
            active,
            generation,
        ) = self._capture_snapshot(workspace_id)
        content_digest = self._content_digest(records)
        details = self._projection_details(
            workspace_id=workspace_id,
            generation=generation,
            content_digest=content_digest,
        )
        capability_ready = self._capability_ready()
        manifest_id = deterministic_id(
            "prj", "projection", workspace_id, "dense", generation, event_root
        )
        result = DenseProjectionBuildResult(
            projection_name="dense",
            generation=generation,
            status=(
                "unavailable"
                if not capability_ready
                else ("ready" if dry_run else "active")
            ),
            row_count=len(records),
            source_event_count=event_count,
            source_event_root_hash=event_root,
            content_digest=content_digest,
            build_config_hash=str(details["build_config_hash"]),
            builder_contract_hash=str(details["builder_contract_hash"]),
            collection_name=str(details["collection_name"]),
            staging_manifest_id=manifest_id,
            dry_run=dry_run,
            capability_status=("ready" if capability_ready else "unavailable"),
            capability_reason=(
                None if capability_ready else "DENSE_UNAVAILABLE"
            ),
            provider_key=self.provider_key,
            model_id=self.model_id,
            dimension=self.dimension,
            active_manifest_id=active[0] if active is not None else None,
            active_generation=active[1] if active is not None else None,
            active_status=active[2] if active is not None else None,
            active_row_count=active[3] if active is not None else 0,
            active_content_digest=active[4] if active is not None else None,
            row_count_delta=(
                len(records) - (active[3] if active is not None else 0)
            ),
            content_digest_changed=(
                active is None or active[4] != content_digest
            ),
        )
        staging_reserved = False
        try:
            if (
                not dry_run
                and active is not None
                and self._active_is_current(
                    workspace_id,
                    records,
                    event_count,
                    event_root,
                    content_digest,
                    active,
                )
            ):
                self._reject_external_transaction()
                self._validate_reuse_snapshot(
                    workspace_id,
                    records,
                    event_count,
                    event_root,
                    cursor,
                    active,
                )
                active_details = self._projection_details(
                    workspace_id=workspace_id,
                    generation=active[1],
                    content_digest=content_digest,
                )
                return DenseProjectionBuildResult(
                    projection_name="dense",
                    generation=active[1],
                    status="active",
                    row_count=len(records),
                    source_event_count=event_count,
                    source_event_root_hash=event_root,
                    content_digest=content_digest,
                    build_config_hash=str(active_details["build_config_hash"]),
                    builder_contract_hash=str(
                        active_details["builder_contract_hash"]
                    ),
                    collection_name=str(active_details["collection_name"]),
                    staging_manifest_id=active[0],
                    provider_key=self.provider_key,
                    model_id=self.model_id,
                    dimension=self.dimension,
                    active_manifest_id=active[0],
                    active_generation=active[1],
                    active_status=active[2],
                    active_row_count=active[3],
                    active_content_digest=active[4],
                    row_count_delta=0,
                    content_digest_changed=False,
                    reused=True,
                )
            if dry_run:
                return result
            if not capability_ready:
                raise DenseProjectionBuildError(
                    "DENSE_UNAVAILABLE",
                    "dense projection capability is unavailable",
                )

            now = self._clock_value()
            self._reserve_staging(
                manifest_id=manifest_id,
                workspace_id=workspace_id,
                generation=generation,
                records=records,
                event_count=event_count,
                event_root=event_root,
                cursor=cursor,
                content_digest=content_digest,
                details=details,
                started_at_us=now,
            )
            staging_reserved = True
            points = [
                self._point(workspace_id, generation, record)
                for record in records
            ]
            self._reject_external_transaction()
            self._replace_collection(str(details["collection_name"]), points)
            self._reject_external_transaction()
            self._validate_collection(str(details["collection_name"]), points)
            self._reject_external_transaction()
            self._activate_staging(
                manifest_id=manifest_id,
                workspace_id=workspace_id,
                generation=generation,
                records=records,
                event_count=event_count,
                event_root=event_root,
                cursor=cursor,
                content_digest=content_digest,
                details=details,
                started_at_us=now,
            )
            return result
        except Exception as exc:
            if staging_reserved:
                self._cleanup_staging(
                    workspace_id,
                    generation,
                    manifest_id,
                    str(details["collection_name"]),
                )
            if isinstance(exc, DenseProjectionBuildError):
                raise
            raise DenseProjectionBuildError(
                "DENSE_BUILD_FAILED", "dense projection build failed"
            ) from exc

    @staticmethod
    def _content_digest(records: Sequence[_DenseRecord]) -> str:
        return sha256_json(
            [
                {
                    "content_hash": record.content_hash,
                    "record_id": record.record_id,
                }
                for record in records
            ]
        )

    def _capture_snapshot(
        self, workspace_id: str
    ) -> tuple[
        tuple[_DenseRecord, ...],
        int,
        str,
        tuple[int, str] | None,
        tuple[str, int, str, int, str | None] | None,
        int,
    ]:
        self.connection.execute("BEGIN")
        try:
            records = self._records(workspace_id)
            event_count, event_root, cursor = self._event_snapshot(workspace_id)
            active = self._active_manifest(workspace_id)
            generation = int(
                self.connection.execute(
                    "SELECT COALESCE(MAX(generation),0) "
                    "FROM projection_manifests WHERE workspace_id=? "
                    "AND projection_name='dense'",
                    (workspace_id,),
                ).fetchone()[0]
            ) + 1
            self.connection.rollback()
            return (
                records,
                event_count,
                event_root,
                cursor,
                active,
                generation,
            )
        except Exception:
            self.connection.rollback()
            raise

    def _reserve_staging(
        self,
        *,
        manifest_id: str,
        workspace_id: str,
        generation: int,
        records: Sequence[_DenseRecord],
        event_count: int,
        event_root: str,
        cursor: tuple[int, str] | None,
        content_digest: str,
        details: Mapping[str, object],
        started_at_us: int,
    ) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._validate_source_snapshot(
                workspace_id,
                records,
                event_count,
                event_root,
                cursor,
                content_digest,
            )
            next_generation = int(
                self.connection.execute(
                    "SELECT COALESCE(MAX(generation),0) "
                    "FROM projection_manifests WHERE workspace_id=? "
                    "AND projection_name='dense'",
                    (workspace_id,),
                ).fetchone()[0]
            ) + 1
            if next_generation != generation:
                raise DenseProjectionBuildError(
                    "PROJECTION_VALIDATION_FAILED",
                    "dense generation changed before staging",
                )
            self.connection.execute(
                """
                INSERT INTO projection_manifests (
                    manifest_id,workspace_id,projection_name,generation,
                    projection_version,status,source_event_count,
                    source_event_root_hash,cursor_recorded_at_us,cursor_event_id,
                    row_count,builder_version,details_json,started_at_us,
                    completed_at_us,activated_at_us
                ) VALUES (?,?,'dense',?,1,'building',?,?,?,?,0,?,?,?,NULL,NULL)
                """,
                (
                    manifest_id,
                    workspace_id,
                    generation,
                    event_count,
                    event_root,
                    cursor[0] if cursor is not None else None,
                    cursor[1] if cursor is not None else None,
                    DENSE_BUILDER_VERSION,
                    canonical_json_bytes(details).decode("utf-8"),
                    started_at_us,
                ),
            )
            self.connection.executemany(
                """
                INSERT INTO dense_projection_refs (
                    workspace_id,provider_key,projection_generation,record_id,
                    content_hash,model_id,dimension,state,updated_event_id,
                    failure_code,updated_at_us
                ) VALUES (?,?,?,?,?,?,?,'pending',?,NULL,?)
                """,
                [
                    (
                        workspace_id,
                        self.provider_key,
                        generation,
                        record.record_id,
                        record.content_hash,
                        self.model_id,
                        self.dimension,
                        record.source_event_id,
                        started_at_us,
                    )
                    for record in records
                ],
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _activate_staging(
        self,
        *,
        manifest_id: str,
        workspace_id: str,
        generation: int,
        records: Sequence[_DenseRecord],
        event_count: int,
        event_root: str,
        cursor: tuple[int, str] | None,
        content_digest: str,
        details: Mapping[str, object],
        started_at_us: int,
    ) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self._validate_source_snapshot(
                workspace_id,
                records,
                event_count,
                event_root,
                cursor,
                content_digest,
            )
            superseding = self.connection.execute(
                "SELECT generation FROM projection_manifests "
                "WHERE workspace_id=? AND projection_name='dense' "
                "AND generation>? ORDER BY generation DESC LIMIT 1",
                (workspace_id, generation),
            ).fetchone()
            if superseding is not None:
                raise DenseProjectionBuildError(
                    "PROJECTION_VALIDATION_FAILED",
                    "dense staging generation was superseded",
                )
            if self._projection_details(
                workspace_id=workspace_id,
                generation=generation,
                content_digest=content_digest,
            ) != details:
                raise DenseProjectionBuildError(
                    "PROJECTION_VALIDATION_FAILED",
                    "dense encoder contract changed during build",
                )
            self._validate_manifest(
                manifest_id=manifest_id,
                workspace_id=workspace_id,
                generation=generation,
                event_count=event_count,
                event_root=event_root,
                cursor=cursor,
                details=details,
                started_at_us=started_at_us,
            )
            self.connection.execute(
                "UPDATE dense_projection_refs SET state='ready' "
                "WHERE workspace_id=? AND provider_key=? "
                "AND projection_generation=? AND state='pending'",
                (workspace_id, self.provider_key, generation),
            )
            self._validate_references(workspace_id, generation, records)
            self.connection.execute(
                "UPDATE projection_manifests SET status='ready' "
                "WHERE workspace_id=? AND projection_name='dense' "
                "AND status='active'",
                (workspace_id,),
            )
            changed = self.connection.execute(
                "UPDATE projection_manifests SET status='active',row_count=?,"
                "completed_at_us=?,activated_at_us=? "
                "WHERE manifest_id=? AND status='building'",
                (
                    len(records),
                    started_at_us,
                    started_at_us,
                    manifest_id,
                ),
            ).rowcount
            if changed != 1:
                raise DenseProjectionBuildError(
                    "PROJECTION_ACTIVATION_FAILED",
                    "staging dense manifest is unavailable",
                )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _validate_reuse_snapshot(
        self,
        workspace_id: str,
        records: Sequence[_DenseRecord],
        event_count: int,
        event_root: str,
        cursor: tuple[int, str] | None,
        active: tuple[str, int, str, int, str | None],
    ) -> None:
        self.connection.execute("BEGIN")
        try:
            self._validate_source_snapshot(
                workspace_id,
                records,
                event_count,
                event_root,
                cursor,
                self._content_digest(records),
            )
            current = self._active_manifest(workspace_id)
            if current is None or current[:2] != active[:2]:
                raise DenseProjectionBuildError(
                    "PROJECTION_VALIDATION_FAILED",
                    "active dense generation changed during validation",
                )
        finally:
            self.connection.rollback()

    def _reject_external_transaction(self) -> None:
        if not self.connection.in_transaction:
            return
        self.connection.rollback()
        raise DenseProjectionBuildError(
            "PROJECTION_VALIDATION_FAILED",
            "external dense work mutated the SQLite transaction",
        )

    def _cleanup_staging(
        self,
        workspace_id: str,
        generation: int,
        manifest_id: str,
        collection_name: str,
    ) -> None:
        if self.connection.in_transaction:
            self.connection.rollback()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            self.connection.execute(
                "DELETE FROM dense_projection_refs WHERE workspace_id=? "
                "AND provider_key=? AND projection_generation=?",
                (workspace_id, self.provider_key, generation),
            )
            self.connection.execute(
                "DELETE FROM projection_manifests WHERE manifest_id=? "
                "AND workspace_id=? AND projection_name='dense' "
                "AND generation=?",
                (manifest_id, workspace_id, generation),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
        try:
            client = self._get_client()
            if self._collection_exists(client, collection_name):
                client.delete_collection(collection_name)
        except Exception:
            pass

    def active_is_current(self, workspace_id: str) -> bool:
        """Return whether active manifest, refs, and points exactly agree."""

        if not isinstance(workspace_id, str) or _WORKSPACE_ID.fullmatch(
            workspace_id
        ) is None:
            raise DenseProjectionBuildError(
                "INVALID_WORKSPACE_ID", "workspace identifier is invalid"
            )
        self._require_schema()
        owns_transaction = not self.connection.in_transaction
        try:
            if owns_transaction:
                self.connection.execute("BEGIN")
            records = self._records(workspace_id)
            event_count, event_root, _ = self._event_snapshot(workspace_id)
            active = self._active_manifest(workspace_id)
            if active is None:
                return False
            content_digest = sha256_json(
                [
                    {"content_hash": record.content_hash, "record_id": record.record_id}
                    for record in records
                ]
            )
            return self._active_is_current(
                workspace_id,
                records,
                event_count,
                event_root,
                content_digest,
                active,
            )
        except Exception:
            return False
        finally:
            if owns_transaction and self.connection.in_transaction:
                self.connection.rollback()

    def _point(
        self, workspace_id: str, generation: int, record: _DenseRecord
    ) -> dict[str, object]:
        point_id, payload = build_dense_point_payload(
            workspace_id=workspace_id,
            record_id=record.record_id,
            content_hash=record.content_hash,
            projection_generation=generation,
            model_id=self.model_id,
        )
        encode = getattr(self.encoder, "encode", None)
        vector = (
            encode(record.content)
            if callable(encode)
            else self.encoder(record.content)
        )
        if isinstance(vector, (str, bytes, Mapping)):
            raise DenseProjectionBuildError(
                "DENSE_ENCODER_FAILED", "dense encoder returned invalid output"
            )
        values = [float(value) for value in vector]
        if len(values) != self.dimension or not all(map(math.isfinite, values)):
            raise DenseProjectionBuildError(
                "DENSE_ENCODER_FAILED", "dense encoder returned invalid output"
            )
        return {"id": point_id, "payload": payload, "vector": values}

    def _projection_details(
        self,
        *,
        workspace_id: str,
        generation: int,
        content_digest: str,
    ) -> dict[str, object]:
        details = dense_manifest_details(
            workspace_id=workspace_id,
            provider_key=self.provider_key,
            generation=generation,
            model_id=self.model_id,
            dimension=self.dimension,
            collection_prefix=self.collection_prefix,
        )
        contract = dense_builder_contract(
            build_config_hash=str(details["build_config_hash"]),
            encoder=self.encoder,
            model_id=self.model_id,
            dimension=self.dimension,
            query_prefix=self.query_prefix,
        )
        return {
            **details,
            **contract,
            "content_digest": content_digest,
            "projection": "dense",
        }

    def _capability_ready(self) -> bool:
        encoder_ready = callable(self.encoder) or callable(
            getattr(self.encoder, "encode", None)
        )
        if self.client is not None:
            client_ready = self._client_contract_ready(self.client)
        else:
            configured = (
                self._qdrant_url is not None or self._qdrant_path is not None
            )
            dependency_ready = self._client_factory is not None or (
                importlib.util.find_spec("qdrant_client") is not None
            )
            client_ready = configured and dependency_ready
        return encoder_ready and client_ready

    def _get_client(self) -> object:
        if self.client is None:
            self.client = create_qdrant_client(
                qdrant_url=self._qdrant_url,
                qdrant_api_key=self._qdrant_api_key,
                qdrant_path=self._qdrant_path,
                timeout_seconds=self._timeout_seconds,
                client_factory=self._client_factory,
            )
        if not self._client_contract_ready(self.client):
            raise DenseProjectionBuildError(
                "DENSE_UNAVAILABLE", "dense projection capability is unavailable"
            )
        return self.client

    @staticmethod
    def _client_contract_ready(client: object) -> bool:
        required_ready = all(
            callable(getattr(client, name, None))
            for name in _CLIENT_METHODS
        )
        existence_ready = any(
            callable(getattr(client, name, None))
            for name in (
                "collection_exists",
                "get_collections",
                "get_collection",
            )
        )
        return required_ready and existence_ready

    def _models_for_client(self, client: object) -> object | None:
        if self._qdrant_models is not None:
            return self._qdrant_models
        module_name = type(client).__module__
        if not module_name.startswith("qdrant_client"):
            return None
        try:
            from qdrant_client import models
        except ImportError as exc:
            raise DenseProjectionBuildError(
                "DENSE_UNAVAILABLE", "dense projection capability is unavailable"
            ) from exc
        return models

    @staticmethod
    def _collection_exists(client: object, collection_name: str) -> bool:
        collection_exists = getattr(client, "collection_exists", None)
        if callable(collection_exists):
            return bool(collection_exists(collection_name))
        get_collections = getattr(client, "get_collections", None)
        if callable(get_collections):
            response = get_collections()
            collections = (
                response.get("collections", ())
                if isinstance(response, Mapping)
                else getattr(response, "collections", ())
            )
            if isinstance(collections, (str, bytes, Mapping)):
                raise TypeError("invalid Qdrant collections response")
            return any(
                (
                    item.get("name")
                    if isinstance(item, Mapping)
                    else getattr(item, "name", None)
                )
                == collection_name
                for item in collections
            )
        get_collection = getattr(client, "get_collection", None)
        if not callable(get_collection):
            raise TypeError("Qdrant client has no collection lookup")
        try:
            get_collection(collection_name)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            response = getattr(exc, "response", None)
            response_status = getattr(response, "status_code", None)
            if status_code == 404 or response_status == 404:
                return False
            raise
        return True

    def _qdrant_vector_config(self, client: object) -> object:
        models = self._models_for_client(client)
        if models is None:
            return {"size": self.dimension, "distance": "Cosine"}
        vector_params = getattr(models, "VectorParams", None)
        distance = getattr(getattr(models, "Distance", None), "COSINE", None)
        if not callable(vector_params) or distance is None:
            raise DenseProjectionBuildError(
                "DENSE_UNAVAILABLE", "dense projection capability is unavailable"
            )
        return vector_params(size=self.dimension, distance=distance)

    def _qdrant_points(
        self,
        client: object,
        points: list[dict[str, object]],
    ) -> list[object]:
        models = self._models_for_client(client)
        if models is None:
            return list(points)
        point_struct = getattr(models, "PointStruct", None)
        if not callable(point_struct):
            raise DenseProjectionBuildError(
                "DENSE_UNAVAILABLE", "dense projection capability is unavailable"
            )
        return [
            point_struct(
                id=point["id"],
                vector=point["vector"],
                payload=point["payload"],
            )
            for point in points
        ]

    def _replace_collection(
        self, collection_name: str, points: list[dict[str, object]]
    ) -> None:
        client = self._get_client()
        if self._collection_exists(client, collection_name):
            client.delete_collection(collection_name)
        client.create_collection(
            collection_name=collection_name,
            vectors_config=self._qdrant_vector_config(client),
        )
        if points:
            client.upsert(
                collection_name=collection_name,
                points=self._qdrant_points(client, points),
                wait=True,
            )

    def _validate_staging(
        self,
        workspace_id: str,
        generation: int,
        collection_name: str,
        records: Sequence[_DenseRecord],
        points: Sequence[Mapping[str, object]],
    ) -> None:
        self._validate_collection(collection_name, points)
        self._validate_references(workspace_id, generation, records)

    def _validate_collection(
        self,
        collection_name: str,
        points: Sequence[Mapping[str, object]],
    ) -> None:
        expected = {str(point["id"]): point for point in points}
        client = self._get_client()
        retrieved = client.retrieve(
            collection_name=collection_name,
            ids=sorted(expected),
            with_payload=True,
            with_vectors=True,
        )
        actual: dict[str, tuple[object, object]] = {}
        for point in retrieved:
            point_id = _point_field(point, "id")
            payload = _point_field(point, "payload")
            vector = _point_field(point, "vector")
            if not isinstance(point_id, str) or not isinstance(payload, Mapping):
                raise DenseProjectionBuildError(
                    "PROJECTION_VALIDATION_FAILED", "dense point is malformed"
                )
            actual[point_id] = (payload, vector)
        count_response = client.count(
            collection_name=collection_name, exact=True
        )
        count = (
            count_response.get("count")
            if isinstance(count_response, Mapping)
            else getattr(count_response, "count", None)
        )
        if count != len(expected) or set(actual) != set(expected):
            raise DenseProjectionBuildError(
                "PROJECTION_VALIDATION_FAILED", "dense point set differs"
            )
        for point_id, wanted in expected.items():
            payload, vector = actual[point_id]
            if (
                payload != wanted["payload"]
                or not isinstance(vector, Sequence)
                or isinstance(vector, (str, bytes))
                or list(vector) != wanted["vector"]
            ):
                raise DenseProjectionBuildError(
                    "PROJECTION_VALIDATION_FAILED", "dense point content differs"
                )

    def _validate_references(
        self,
        workspace_id: str,
        generation: int,
        records: Sequence[_DenseRecord],
    ) -> None:
        rows = self.connection.execute(
            "SELECT record_id,content_hash,model_id,dimension,state,updated_event_id "
            "FROM dense_projection_refs WHERE workspace_id=? AND provider_key=? "
            "AND projection_generation=? ORDER BY record_id",
            (workspace_id, self.provider_key, generation),
        ).fetchall()
        wanted_rows = [
            (
                record.record_id,
                record.content_hash,
                self.model_id,
                self.dimension,
                "ready",
                record.source_event_id,
            )
            for record in records
        ]
        if [tuple(row) for row in rows] != wanted_rows:
            raise DenseProjectionBuildError(
                "PROJECTION_VALIDATION_FAILED", "dense reference set differs"
            )

    def _validate_manifest(
        self,
        *,
        manifest_id: str,
        workspace_id: str,
        generation: int,
        event_count: int,
        event_root: str,
        cursor: tuple[int, str] | None,
        details: Mapping[str, object],
        started_at_us: int,
    ) -> None:
        row = self.connection.execute(
            "SELECT workspace_id,projection_name,generation,projection_version,"
            "status,source_event_count,source_event_root_hash,"
            "cursor_recorded_at_us,cursor_event_id,row_count,builder_version,"
            "details_json,started_at_us,completed_at_us,activated_at_us "
            "FROM projection_manifests WHERE manifest_id=?",
            (manifest_id,),
        ).fetchone()
        expected = (
            workspace_id,
            "dense",
            generation,
            1,
            "building",
            event_count,
            event_root,
            cursor[0] if cursor is not None else None,
            cursor[1] if cursor is not None else None,
            0,
            DENSE_BUILDER_VERSION,
            canonical_json_bytes(details).decode("utf-8"),
            started_at_us,
            None,
            None,
        )
        if row is None or tuple(row) != expected:
            raise DenseProjectionBuildError(
                "PROJECTION_VALIDATION_FAILED", "dense manifest differs"
            )

    def _validate_source_snapshot(
        self,
        workspace_id: str,
        records: Sequence[_DenseRecord],
        event_count: int,
        event_root: str,
        cursor: tuple[int, str] | None,
        content_digest: str,
    ) -> None:
        current_records = self._records(workspace_id)
        current_snapshot = self._event_snapshot(workspace_id)
        if (
            current_records != tuple(records)
            or self._content_digest(current_records) != content_digest
            or current_snapshot != (event_count, event_root, cursor)
        ):
            raise DenseProjectionBuildError(
                "PROJECTION_VALIDATION_FAILED",
                "dense source snapshot changed during build",
            )

    def _records(self, workspace_id: str) -> tuple[_DenseRecord, ...]:
        return tuple(
            _DenseRecord(str(row[0]), str(row[1]), str(row[2]), str(row[3]))
            for row in self.connection.execute(
                "SELECT record_id,content,content_hash,source_event_id "
                "FROM memory_records WHERE workspace_id=? AND deleted_at_us IS NULL "
                "ORDER BY record_id",
                (workspace_id,),
            )
        )

    def _active_manifest(
        self, workspace_id: str
    ) -> tuple[str, int, str, int, str | None] | None:
        row = self.connection.execute(
            "SELECT manifest_id,generation,status,row_count,details_json "
            "FROM projection_manifests WHERE workspace_id=? "
            "AND projection_name='dense' AND status='active' "
            "ORDER BY generation DESC LIMIT 1",
            (workspace_id,),
        ).fetchone()
        if row is None:
            return None
        digest = None
        try:
            details = json.loads(str(row[4]))
            candidate = details.get("content_digest")
            if (
                isinstance(candidate, str)
                and len(candidate) == 64
                and not set(candidate).difference("0123456789abcdef")
            ):
                digest = candidate
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            pass
        return str(row[0]), int(row[1]), str(row[2]), int(row[3]), digest

    def _active_is_current(
        self,
        workspace_id: str,
        records: Sequence[_DenseRecord],
        event_count: int,
        event_root: str,
        content_digest: str,
        active: tuple[str, int, str, int, str | None],
    ) -> bool:
        generation = active[1]
        expected_details = self._projection_details(
            workspace_id=workspace_id,
            generation=generation,
            content_digest=content_digest,
        )
        row = self.connection.execute(
            "SELECT source_event_count,source_event_root_hash,row_count,details_json "
            "FROM projection_manifests WHERE manifest_id=? AND status='active'",
            (active[0],),
        ).fetchone()
        if row is None:
            return False
        try:
            stored_details = json.loads(str(row[3]))
        except (TypeError, ValueError, json.JSONDecodeError, RecursionError):
            return False
        if (
            int(row[0]) != event_count
            or str(row[1]) != event_root
            or int(row[2]) != len(records)
            or stored_details != expected_details
        ):
            return False
        points = [
            self._point(workspace_id, generation, record) for record in records
        ]
        try:
            self._validate_staging(
                workspace_id,
                generation,
                str(expected_details["collection_name"]),
                records,
                points,
            )
        except Exception:
            return False
        return True

    def _event_snapshot(
        self, workspace_id: str
    ) -> tuple[int, str, tuple[int, str] | None]:
        digest = hashlib.sha256()
        count = 0
        for row in self.connection.execute(
            "SELECT event_hash FROM memory_events WHERE workspace_id=? "
            "ORDER BY event_id",
            (workspace_id,),
        ):
            digest.update(bytes.fromhex(str(row[0])))
            count += 1
        row = self.connection.execute(
            "SELECT recorded_at_us,event_id FROM memory_events WHERE workspace_id=? "
            "ORDER BY recorded_at_us DESC,event_id DESC LIMIT 1",
            (workspace_id,),
        ).fetchone()
        cursor = None if row is None else (int(row[0]), str(row[1]))
        return count, digest.hexdigest(), cursor

    def _require_schema(self) -> None:
        names = {
            str(row[0])
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE name IN "
                "('memory_events','memory_records','projection_manifests',"
                "'dense_projection_refs')"
            )
        }
        if names != {
            "memory_events",
            "memory_records",
            "projection_manifests",
            "dense_projection_refs",
        }:
            raise DenseProjectionBuildError(
                "DENSE_UNAVAILABLE", "dense projection schema is unavailable"
            )

    def _clock_value(self) -> int:
        value = self._clock_us()
        if isinstance(value, bool) or not isinstance(value, int):
            raise DenseProjectionBuildError(
                "INVALID_CLOCK", "projection clock must return integer microseconds"
            )
        return value

__all__ = [
    "DenseProjectionBuildError",
    "DenseProjectionBuildResult",
    "DenseProjectionBuilder",
]
