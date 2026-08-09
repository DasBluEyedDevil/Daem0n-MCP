"""Retrieval providers backed by rebuildable v7 projections."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import math
import os
import re
import sqlite3
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from time import perf_counter_ns

from ..bounded_workers import BoundedWorkerBusyError, BoundedWorkerPool
from .lexical_config import (
    LEXICAL_BM25_WEIGHTS,
    lexical_build_config_hash,
    lexical_fts_table_name,
)
from .types import (
    Candidate,
    EvidenceRef,
    ProviderResult,
    ProviderStatus,
    RetrievalQuery,
)


_MAX_FTS_TERMS = 64
_MAX_FTS_TERM_CHARS = 256
_FTS_QUESTION_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "are",
        "be",
        "do",
        "does",
        "how",
        "i",
        "is",
        "the",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "you",
    }
)
_WORKSPACE_ID = re.compile(r"^ws_[0-9a-f]{24}$")
_RECORD_ID = re.compile(r"^mem_[0-9a-f]{64}$")
_CONTENT_HASH = re.compile(r"^[0-9a-f]{64}$")
_PROVIDER_KEY = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_COLLECTION_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_DENSE_DISTANCE = "cosine"
_DENSE_SCHEMA_VERSION = 1
DENSE_BUILDER_VERSION = "retrieval-dense-1"
_DENSE_REBUILD_MARKERS = frozenset(
    {"rebuild_required_at_us", "rebuild_required_event_id"}
)
_DENSE_PAYLOAD_KEYS = frozenset(
    {
        "workspace_id",
        "record_id",
        "content_hash",
        "projection_generation",
        "model_id",
    }
)
_LEXICAL_WORKERS = BoundedWorkerPool(
    max_workers=4,
    thread_name_prefix="daem0nmcp-lexical",
)
_DENSE_WORKERS = BoundedWorkerPool(
    max_workers=2,
    thread_name_prefix="daem0nmcp-dense",
)


def _safe_fts_queries(text: str) -> tuple[str, ...] | None:
    """Return bounded precision-first queries with no caller FTS operators."""

    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if any(ord(character) < 32 and not character.isspace() for character in text):
        return None
    terms = tuple(
        dict.fromkeys(
            term
            for term in re.findall(r"\w+", text, flags=re.UNICODE)
            if term.casefold() not in _FTS_QUESTION_STOP_WORDS
        )
    )
    if not terms:
        return ()
    if len(terms) > _MAX_FTS_TERMS or any(
        len(term) > _MAX_FTS_TERM_CHARS for term in terms
    ):
        return None
    quoted = tuple(f'"{term}"' for term in terms)
    conjunctive = " ".join(quoted)
    if len(quoted) == 1:
        return (conjunctive,)
    if len(quoted) == 2:
        return (conjunctive, " OR ".join(quoted))
    if len(quoted) <= 12:
        pairs = tuple(
            f"{quoted[left]} {quoted[right]}"
            for left in range(len(quoted))
            for right in range(left + 1, len(quoted))
        )
    else:
        pairs = tuple(
            f"{quoted[index]} {quoted[index + 1]}"
            for index in range(len(quoted) - 1)
        )
    return (conjunctive, " OR ".join(pairs))


def _transaction_datetime(value: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value) / 1_000_000, timezone.utc)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


class LexicalProvider:
    """Complete SQLite FTS5 baseline; never falls back to LIKE or TF-IDF."""

    name = "lexical"

    def __init__(
        self,
        connection: sqlite3.Connection | None = None,
        *,
        connection_factory: Callable[[], sqlite3.Connection] | None = None,
        timeout_seconds: float = 2.0,
        worker_pool: BoundedWorkerPool | None = None,
    ) -> None:
        self._connection_factory = _sqlite_read_factory(
            connection, connection_factory
        )
        self._timeout_seconds = _positive_timeout(
            timeout_seconds, "timeout_seconds"
        )
        if worker_pool is not None and not isinstance(
            worker_pool, BoundedWorkerPool
        ):
            raise ValueError("worker_pool must be a BoundedWorkerPool")
        self._worker_pool = worker_pool or _LEXICAL_WORKERS

    async def search(
        self,
        query: RetrievalQuery,
        limit: int,
    ) -> ProviderResult:
        started = perf_counter_ns()
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        try:
            return await asyncio.wait_for(
                self._worker_pool.run(
                    lambda: self._search_sync(query, limit, started)
                ),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            return self._unavailable(started, "LEXICAL_TIMEOUT")
        except BoundedWorkerBusyError:
            return self._unavailable(started, "LEXICAL_BUSY")
        except Exception:
            return self._unavailable(started)

    def _search_sync(
        self,
        query: RetrievalQuery,
        limit: int,
        started_ns: int,
    ) -> ProviderResult:
        connection = _open_read_connection(self._connection_factory)
        try:
            return self._search_connection(
                connection,
                query,
                limit,
                started_ns,
            )
        finally:
            connection.close()

    def _search_connection(
        self,
        connection: sqlite3.Connection,
        query: RetrievalQuery,
        limit: int,
        started_ns: int,
    ) -> ProviderResult:
        started = started_ns
        bounded_limit = min(limit, query.candidate_limit)
        try:
            manifest = connection.execute(
                "SELECT generation,details_json FROM projection_manifests "
                "WHERE workspace_id=? AND projection_name='lexical' "
                "AND status='active'",
                (query.workspace_id,),
            ).fetchone()
            if manifest is None:
                stale = connection.execute(
                    "SELECT 1 FROM projection_manifests WHERE workspace_id=? "
                    "AND projection_name='lexical' "
                    "AND status='rebuild_required' LIMIT 1",
                    (query.workspace_id,),
                ).fetchone()
                if stale is not None:
                    return self._unavailable(
                        started, "LEXICAL_REBUILD_REQUIRED"
                    )
                return self._unavailable(started)
            generation = int(manifest[0])
            details = json.loads(str(manifest[1]))
            stale_reason = (
                "LEXICAL_REBUILD_REQUIRED"
                if isinstance(details, Mapping)
                and details.get("rebuild_required_event_id") is not None
                else None
            )
            expected_table = lexical_fts_table_name(
                query.workspace_id, generation
            )
            if (
                not isinstance(details, Mapping)
                or details.get("fts_table") != expected_table
                or details.get("build_config_hash")
                != lexical_build_config_hash()
                or connection.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type='table' AND name=?",
                    (expected_table,),
                ).fetchone()
                is None
            ):
                return self._unavailable(started)
            fts_queries = _safe_fts_queries(query.text)
            result_status = (
                "degraded" if stale_reason is not None else "ready"
            )
            if fts_queries is None:
                return ProviderResult(
                    provider=self.name,
                    status=result_status,
                    reason=stale_reason or "INVALID_FTS_QUERY",
                    manifest_generation=generation,
                    elapsed_ms=(perf_counter_ns() - started) / 1_000_000,
                )
            if not fts_queries:
                return ProviderResult(
                    provider=self.name,
                    status=result_status,
                    reason=stale_reason,
                    manifest_generation=generation,
                    elapsed_ms=(perf_counter_ns() - started) / 1_000_000,
                )
            content_weight, rationale_weight, tags_weight = (
                LEXICAL_BM25_WEIGHTS
            )
            rows = []
            for fts_query in fts_queries:
                rows = connection.execute(
                    f"""
                    SELECT document.record_id, document.content_hash,
                           document.source_event_id, document.updated_at_us,
                           bm25(
                               {expected_table}, {content_weight},
                               {rationale_weight}, {tags_weight}
                           ) AS score,
                           snippet({expected_table}, 0, '', '', ' … ', 18)
                    FROM "{expected_table}"
                    JOIN (
                        SELECT document_rowid,record_id,content_hash,
                               source_event_id,
                               transaction_from_us AS updated_at_us
                        FROM retrieval_documents
                        WHERE workspace_id=? AND projection_generation=?
                    ) AS document
                      ON document.document_rowid="{expected_table}".rowid
                    WHERE "{expected_table}" MATCH ?
                    ORDER BY score ASC, document.record_id ASC
                    LIMIT ?
                    """,
                    (
                        query.workspace_id,
                        generation,
                        fts_query,
                        bounded_limit,
                    ),
                ).fetchall()
                if rows:
                    break
        except (json.JSONDecodeError, sqlite3.Error, TypeError, ValueError):
            return self._unavailable(started)

        candidates = []
        for rank, row in enumerate(rows, 1):
            score = float(row[4])
            snippet = row[5]
            candidates.append(
                Candidate(
                    evidence=EvidenceRef(
                        record_id=str(row[0]),
                        event_id=str(row[2]),
                        content_hash=str(row[1]),
                        version_id=None,
                        provider=self.name,
                    ),
                    rank=rank,
                    raw_score=max(0.0, -score),
                    channels=frozenset({self.name}),
                    highlights=(str(snippet),) if snippet else (),
                    transaction_time=_transaction_datetime(row[3]),
                )
            )
        return ProviderResult(
            provider=self.name,
            candidates=tuple(candidates),
            status="degraded" if stale_reason is not None else "ready",
            reason=stale_reason,
            manifest_generation=generation,
            elapsed_ms=(perf_counter_ns() - started) / 1_000_000,
        )

    def _unavailable(
        self,
        started: int,
        reason: str = "LEXICAL_UNAVAILABLE",
    ) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            status="unavailable",
            reason=reason,
            elapsed_ms=(perf_counter_ns() - started) / 1_000_000,
        )


def _positive_timeout(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a positive finite number")
    try:
        timeout = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(
            f"{field_name} must be a positive finite number"
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 60:
        raise ValueError(f"{field_name} must be a positive finite number")
    return timeout


def _sqlite_read_factory(
    connection: sqlite3.Connection | None,
    connection_factory: Callable[[], sqlite3.Connection] | None,
) -> Callable[[], sqlite3.Connection]:
    if connection_factory is not None:
        if connection is not None or not callable(connection_factory):
            raise ValueError(
                "provide exactly one SQLite connection or connection_factory"
            )
        return connection_factory
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("a SQLite connection or connection_factory is required")
    database_row = connection.execute(
        "PRAGMA database_list"
    ).fetchone()
    database_path = "" if database_row is None else str(database_row[2])
    if not database_path:
        raise ValueError(
            "in-memory SQLite requires a worker-local connection_factory"
        )

    def open_connection() -> sqlite3.Connection:
        return sqlite3.connect(database_path, timeout=5.0)

    return open_connection


def _open_read_connection(
    factory: Callable[[], sqlite3.Connection],
) -> sqlite3.Connection:
    connection = factory()
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("connection_factory must return a SQLite connection")
    connection.execute("PRAGMA query_only=ON")
    return connection


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _nonempty_string(value: object, field_name: str, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise ValueError(f"{field_name} is invalid")
    return value


def _opaque(value: object, pattern: re.Pattern[str], field_name: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{field_name} is invalid")
    return value


def build_dense_point_payload(
    *,
    workspace_id: str,
    record_id: str,
    content_hash: str,
    projection_generation: int,
    model_id: str,
) -> tuple[str, dict[str, object]]:
    """Return the deterministic point ID and the complete safe payload.

    Text and vector values deliberately have no place in the payload.  Text is
    read only from canonical SQLite records; Qdrant owns the vector itself.
    """

    _opaque(workspace_id, _WORKSPACE_ID, "workspace_id")
    canonical_record_id = _opaque(record_id, _RECORD_ID, "record_id")
    _opaque(content_hash, _CONTENT_HASH, "content_hash")
    generation = _positive_integer(
        projection_generation, "projection_generation"
    )
    selected_model = _nonempty_string(model_id, "model_id")
    point_id = dense_point_id(workspace_id, canonical_record_id)
    return point_id, {
        "workspace_id": workspace_id,
        "record_id": canonical_record_id,
        "content_hash": content_hash,
        "projection_generation": generation,
        "model_id": selected_model,
    }


def dense_point_id(workspace_id: str, record_id: str) -> str:
    """Map canonical opaque evidence to a Qdrant-compatible UUID point ID."""

    _opaque(workspace_id, _WORKSPACE_ID, "workspace_id")
    _opaque(record_id, _RECORD_ID, "record_id")
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"daem0nmcp:{workspace_id}:{record_id}",
        )
    )


def _default_qdrant_client_factory(**kwargs: object) -> object:
    from qdrant_client import QdrantClient

    return QdrantClient(**kwargs)


def create_qdrant_client(
    *,
    qdrant_url: str | None,
    qdrant_api_key: str | None,
    qdrant_path: str | os.PathLike[str] | None,
    timeout_seconds: float,
    client_factory: Callable[..., object] | None = None,
) -> object:
    """Construct a remote or local client without importing Qdrant eagerly."""

    if isinstance(timeout_seconds, bool) or not isinstance(
        timeout_seconds, (int, float)
    ):
        raise ValueError("timeout_seconds must be a positive finite number")
    try:
        timeout = float(timeout_seconds)
    except (OverflowError, ValueError) as exc:
        raise ValueError(
            "timeout_seconds must be a positive finite number"
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be a positive finite number")
    factory = client_factory or _default_qdrant_client_factory
    if not callable(factory):
        raise ValueError("client_factory must be callable")

    if qdrant_url is not None:
        url = _nonempty_string(qdrant_url, "qdrant_url", maximum=2048)
        if qdrant_api_key is not None:
            _nonempty_string(
                qdrant_api_key, "qdrant_api_key", maximum=4096
            )
        return factory(url=url, api_key=qdrant_api_key, timeout=timeout)
    if qdrant_path is None:
        raise RuntimeError("DENSE_PROVIDER_UNCONFIGURED")
    try:
        path = os.fspath(qdrant_path)
    except TypeError as exc:
        raise ValueError("qdrant_path must be path-like") from exc
    _nonempty_string(path, "qdrant_path", maximum=4096)
    return factory(path=path)


def _dense_collection_name(
    *,
    prefix: str,
    workspace_id: str,
    provider_key: str,
    generation: int,
    model_id: str,
) -> str:
    if not isinstance(prefix, str) or _COLLECTION_PREFIX.fullmatch(prefix) is None:
        raise ValueError("collection_prefix is invalid")
    _opaque(workspace_id, _WORKSPACE_ID, "workspace_id")
    if not isinstance(provider_key, str) or _PROVIDER_KEY.fullmatch(provider_key) is None:
        raise ValueError("provider_key is invalid")
    _positive_integer(generation, "generation")
    _nonempty_string(model_id, "model_id")
    model_digest = hashlib.sha256(model_id.encode("utf-8")).hexdigest()[:12]
    return (
        f"{prefix}-{workspace_id}-{provider_key}-g{generation}-{model_digest}"
    )


def dense_manifest_details(
    *,
    workspace_id: str,
    provider_key: str,
    generation: int,
    model_id: str,
    dimension: int,
    collection_prefix: str,
) -> dict[str, object]:
    """Return the provider/storage portion of a dense build contract."""

    dimension_value = _positive_integer(dimension, "dimension")
    configuration: dict[str, object] = {
        "collection_name": _dense_collection_name(
            prefix=collection_prefix,
            workspace_id=workspace_id,
            provider_key=provider_key,
            generation=generation,
            model_id=model_id,
        ),
        "collection_prefix": collection_prefix,
        "dimension": dimension_value,
        "distance": _DENSE_DISTANCE,
        "model_id": model_id,
        "provider_key": provider_key,
        "schema_version": _DENSE_SCHEMA_VERSION,
    }
    config_hash = hashlib.sha256(
        json.dumps(
            configuration,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {**configuration, "build_config_hash": config_hash}


def dense_encoder_contract(
    *,
    encoder: object | None,
    model_id: str,
    dimension: int,
    query_prefix: str | None,
) -> dict[str, object]:
    """Return canonical document/query encoder semantics for dense manifests."""

    model = _nonempty_string(model_id, "model_id")
    output_dimension = _positive_integer(dimension, "dimension")
    if query_prefix is not None and (
        not isinstance(query_prefix, str) or len(query_prefix) > 4_096
    ):
        raise ValueError("encoder query prefix is invalid")
    encoder_type = "none"
    if encoder is not None:
        module_name = getattr(
            encoder, "__module__", type(encoder).__module__
        )
        qualified_name = getattr(
            encoder, "__qualname__", type(encoder).__qualname__
        )
        encoder_type = f"{module_name}.{qualified_name}"
    document_prefix = getattr(encoder, "prefix", None)
    backend = getattr(encoder, "backend", None)
    encoder_model_id = getattr(encoder, "model_id", model)
    truncate_dimension = getattr(encoder, "dimension", None)
    max_sequence_length = getattr(encoder, "max_seq_length", None)
    if max_sequence_length is None:
        max_sequence_length = getattr(
            encoder, "max_sequence_length", None
        )
    if document_prefix is not None and (
        not isinstance(document_prefix, str) or len(document_prefix) > 4_096
    ):
        raise ValueError("encoder document prefix is invalid")
    if backend is not None and (
        not isinstance(backend, str)
        or not backend.strip()
        or len(backend) > 256
    ):
        raise ValueError("encoder backend is invalid")
    if encoder_model_id != model:
        raise ValueError("encoder model_id does not match dense model_id")
    if truncate_dimension is not None and (
        isinstance(truncate_dimension, bool)
        or not isinstance(truncate_dimension, int)
        or truncate_dimension != output_dimension
    ):
        raise ValueError("encoder dimension does not match dense dimension")
    if max_sequence_length is not None and (
        isinstance(max_sequence_length, bool)
        or not isinstance(max_sequence_length, int)
        or max_sequence_length < 1
    ):
        raise ValueError("encoder maximum sequence length is invalid")
    return {
        "backend": backend,
        "document_prefix": document_prefix,
        "encoder_type": encoder_type,
        "input_source": "memory_records.content",
        "max_sequence_length": max_sequence_length,
        "model_id": model,
        "output_dimension": output_dimension,
        "query_prefix": query_prefix,
        "truncate_dimension": truncate_dimension,
    }


def dense_builder_contract(
    *,
    build_config_hash: str,
    encoder: object | None,
    model_id: str,
    dimension: int,
    query_prefix: str | None,
) -> dict[str, object]:
    """Return the exact builder/encoder fields shared by build and query."""

    if (
        not isinstance(build_config_hash, str)
        or _CONTENT_HASH.fullmatch(build_config_hash) is None
    ):
        raise ValueError("build_config_hash is invalid")
    encoder_contract = dense_encoder_contract(
        encoder=encoder,
        model_id=model_id,
        dimension=dimension,
        query_prefix=query_prefix,
    )
    contract = {
        "build_config_hash": build_config_hash,
        "builder_version": DENSE_BUILDER_VERSION,
        "encoder_contract": encoder_contract,
        "projection": "dense",
    }
    contract_hash = hashlib.sha256(
        json.dumps(
            contract,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "builder_contract_hash": contract_hash,
        "encoder_contract": encoder_contract,
    }


def dense_query_encoder_matches_contract(
    *,
    query_encoder: object | None,
    encoder_contract: object,
    model_id: str,
    dimension: int,
    query_prefix: str | None,
) -> bool:
    """Return whether the live query encoder shares the built vector space."""

    if query_encoder is None or not isinstance(encoder_contract, Mapping):
        return False
    try:
        query_contract = dense_encoder_contract(
            encoder=query_encoder,
            model_id=model_id,
            dimension=dimension,
            query_prefix=query_prefix,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    shared_fields = (
        "backend",
        "encoder_type",
        "max_sequence_length",
        "model_id",
        "output_dimension",
        "truncate_dimension",
    )
    return (
        all(
            query_contract.get(field) == encoder_contract.get(field)
            for field in shared_fields
        )
        and query_contract.get("document_prefix")
        == encoder_contract.get("query_prefix")
        == query_prefix
    )


def _point_field(point: object, field_name: str) -> object:
    if isinstance(point, Mapping):
        return point.get(field_name)
    return getattr(point, field_name, None)


def _response_points(response: object) -> object:
    if isinstance(response, Mapping):
        return response.get("points", ())
    points = getattr(response, "points", None)
    return response if points is None and isinstance(response, (list, tuple)) else points


class DenseProvider:
    """Optional Qdrant rank source validated against canonical SQLite state."""

    name = "dense"

    def __init__(
        self,
        connection: sqlite3.Connection | None = None,
        *,
        connection_factory: Callable[[], sqlite3.Connection] | None = None,
        provider_key: str,
        model_id: str,
        dimension: int,
        encoder: object | None = None,
        document_encoder: object | None = None,
        query_prefix: str | None = None,
        client: object | None = None,
        qdrant_path: str | os.PathLike[str] | None = None,
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        timeout_seconds: float = 5.0,
        collection_prefix: str = "daem0nmcp",
        client_factory: Callable[..., object] | None = None,
        worker_pool: BoundedWorkerPool | None = None,
    ) -> None:
        if not isinstance(provider_key, str) or _PROVIDER_KEY.fullmatch(provider_key) is None:
            raise ValueError("provider_key is invalid")
        self._connection_factory = _sqlite_read_factory(
            connection, connection_factory
        )
        self.provider_key = provider_key
        self.model_id = _nonempty_string(model_id, "model_id")
        self.dimension = _positive_integer(dimension, "dimension")
        if not isinstance(collection_prefix, str) or _COLLECTION_PREFIX.fullmatch(
            collection_prefix
        ) is None:
            raise ValueError("collection_prefix is invalid")
        if client_factory is not None and not callable(client_factory):
            raise ValueError("client_factory must be callable")
        if worker_pool is not None and not isinstance(
            worker_pool, BoundedWorkerPool
        ):
            raise ValueError("worker_pool must be a BoundedWorkerPool")
        self.collection_prefix = collection_prefix
        self._encoder = encoder
        self._document_encoder = (
            encoder if document_encoder is None else document_encoder
        )
        self._query_prefix = (
            getattr(encoder, "prefix", None)
            if query_prefix is None
            else query_prefix
        )
        dense_encoder_contract(
            encoder=self._document_encoder,
            model_id=self.model_id,
            dimension=self.dimension,
            query_prefix=self._query_prefix,
        )
        self._client = client
        self._qdrant_path = qdrant_path
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key
        self._timeout_seconds = _positive_timeout(
            timeout_seconds, "timeout_seconds"
        )
        self._client_factory = client_factory
        self._worker_pool = worker_pool or _DENSE_WORKERS

    async def search(
        self,
        query: RetrievalQuery,
        limit: int,
    ) -> ProviderResult:
        started = perf_counter_ns()
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        try:
            return await asyncio.wait_for(
                self._worker_pool.run(
                    lambda: self._search_sync(query, limit, started)
                ),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            return self._result(
                started,
                status="degraded",
                reason="DENSE_PROVIDER_TIMEOUT",
            )
        except BoundedWorkerBusyError:
            return self._result(
                started,
                status="degraded",
                reason="DENSE_PROVIDER_BUSY",
            )
        except Exception:
            return self._result(
                started,
                status="degraded",
                reason="DENSE_PROVIDER_FAILED",
            )

    def _search_sync(
        self,
        query: RetrievalQuery,
        limit: int,
        started_ns: int,
    ) -> ProviderResult:
        connection = _open_read_connection(self._connection_factory)
        try:
            return self._search_connection(
                connection,
                query,
                limit,
                started_ns,
            )
        finally:
            connection.close()

    def _search_connection(
        self,
        connection: sqlite3.Connection,
        query: RetrievalQuery,
        limit: int,
        started_ns: int,
    ) -> ProviderResult:
        started = started_ns
        bounded_limit = min(limit, query.candidate_limit)
        manifest = self._active_manifest(connection, query.workspace_id)
        if manifest is None:
            return self._result(
                started, status="unavailable", reason="DENSE_UNAVAILABLE"
            )
        generation, details, manifest_source = manifest
        if not self._manifest_matches(
            query.workspace_id,
            generation,
            details,
        ):
            return self._result(
                started,
                status="unavailable",
                reason="DENSE_MANIFEST_MISMATCH",
                generation=generation,
            )
        if _DENSE_REBUILD_MARKERS.intersection(details):
            return self._result(
                started,
                status="degraded",
                reason="DENSE_REBUILD_REQUIRED",
                generation=generation,
            )
        try:
            current_source = self._event_snapshot(
                connection, query.workspace_id
            )
        except (sqlite3.Error, TypeError, ValueError):
            return self._result(
                started,
                status="unavailable",
                reason="DENSE_MANIFEST_MISMATCH",
                generation=generation,
            )
        if manifest_source != current_source:
            return self._result(
                started,
                status="degraded",
                reason="DENSE_REBUILD_REQUIRED",
                generation=generation,
            )
        if not self._query_encoder_matches(details):
            return self._result(
                started,
                status="unavailable",
                reason="DENSE_MANIFEST_MISMATCH",
                generation=generation,
            )
        if not query.text.strip():
            return self._result(
                started,
                status="ready",
                generation=generation,
            )

        try:
            vector = self._encode(query.text)
        except Exception:
            return self._result(
                started,
                status="degraded",
                reason="DENSE_ENCODER_FAILED",
                generation=generation,
            )
        if not self._query_encoder_matches(details):
            return self._result(
                started,
                status="unavailable",
                reason="DENSE_MANIFEST_MISMATCH",
                generation=generation,
            )
        try:
            client = self._get_client()
            collection_name = _dense_collection_name(
                prefix=self.collection_prefix,
                workspace_id=query.workspace_id,
                provider_key=self.provider_key,
                generation=generation,
                model_id=self.model_id,
            )
            overfetch = min(
                query.candidate_limit, max(bounded_limit, bounded_limit * 3)
            )
            response = self._query_client(
                client,
                collection_name=collection_name,
                vector=vector,
                limit=overfetch,
            )
            if inspect.isawaitable(response):
                response = asyncio.run(response)
            points = _response_points(response)
            if points is None or isinstance(points, (str, bytes, Mapping)):
                raise TypeError("invalid Qdrant response")
            iterator = iter(points)
        except Exception:
            return self._result(
                started,
                status="degraded",
                reason="DENSE_PROVIDER_FAILED",
                generation=generation,
            )

        candidates: list[Candidate] = []
        seen: set[str] = set()
        scanned = 0
        try:
            for point in iterator:
                if scanned >= overfetch or len(candidates) >= bounded_limit:
                    break
                scanned += 1
                validated = self._validate_point(
                    connection, query.workspace_id, generation, point
                )
                if validated is None:
                    continue
                record_id, content_hash, event_id, updated_at_us, score = validated
                if record_id in seen:
                    continue
                seen.add(record_id)
                candidates.append(
                    Candidate(
                        evidence=EvidenceRef(
                            record_id=record_id,
                            event_id=event_id,
                            content_hash=content_hash,
                            version_id=None,
                            provider=self.name,
                        ),
                        rank=len(candidates) + 1,
                        raw_score=score,
                        channels=frozenset({self.name}),
                        transaction_time=_transaction_datetime(updated_at_us),
                    )
                )
        except Exception:
            return self._result(
                started,
                status="degraded",
                reason="DENSE_PROVIDER_FAILED",
                generation=generation,
            )
        return self._result(
            started,
            candidates=tuple(candidates),
            status="ready",
            generation=generation,
        )

    def _active_manifest(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
    ) -> tuple[
        int,
        Mapping[str, object],
        tuple[int, str, int | None, str | None],
    ] | None:
        try:
            row = connection.execute(
                "SELECT generation,source_event_count,"
                "source_event_root_hash,cursor_recorded_at_us,"
                "cursor_event_id,details_json FROM projection_manifests "
                "WHERE workspace_id=? AND projection_name='dense' "
                "AND status='active' ORDER BY generation DESC LIMIT 1",
                (workspace_id,),
            ).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        try:
            generation = _positive_integer(int(row[0]), "generation")
            source_count = int(row[1])
            source_root = str(row[2])
            cursor_us = None if row[3] is None else int(row[3])
            cursor_event = None if row[4] is None else str(row[4])
            details = json.loads(row[5])
        except (TypeError, ValueError):
            return 1, {}, (0, "", None, None)
        if (
            source_count < 0
            or _CONTENT_HASH.fullmatch(source_root) is None
            or (cursor_us is None) != (cursor_event is None)
        ):
            return generation, {}, (source_count, source_root, None, None)
        if not isinstance(details, Mapping):
            details = {}
        return (
            generation,
            details,
            (source_count, source_root, cursor_us, cursor_event),
        )

    @staticmethod
    def _event_snapshot(
        connection: sqlite3.Connection,
        workspace_id: str,
    ) -> tuple[int, str, int | None, str | None]:
        digest = hashlib.sha256()
        count = 0
        for row in connection.execute(
            "SELECT event_hash FROM memory_events WHERE workspace_id=? "
            "ORDER BY event_id",
            (workspace_id,),
        ):
            digest.update(bytes.fromhex(str(row[0])))
            count += 1
        cursor = connection.execute(
            "SELECT recorded_at_us,event_id FROM memory_events "
            "WHERE workspace_id=? "
            "ORDER BY recorded_at_us DESC,event_id DESC LIMIT 1",
            (workspace_id,),
        ).fetchone()
        if cursor is None:
            return count, digest.hexdigest(), None, None
        return count, digest.hexdigest(), int(cursor[0]), str(cursor[1])

    def _manifest_matches(
        self,
        workspace_id: str,
        generation: int,
        details: Mapping[str, object],
    ) -> bool:
        expected = dense_manifest_details(
            workspace_id=workspace_id,
            provider_key=self.provider_key,
            generation=generation,
            model_id=self.model_id,
            dimension=self.dimension,
            collection_prefix=self.collection_prefix,
        )
        expected.update(
            dense_builder_contract(
                build_config_hash=str(expected["build_config_hash"]),
                encoder=self._document_encoder,
                model_id=self.model_id,
                dimension=self.dimension,
                query_prefix=self._query_prefix,
            )
        )
        expected["projection"] = "dense"
        return all(
            details.get(key) == value for key, value in expected.items()
        )

    def _query_encoder_matches(
        self, details: Mapping[str, object]
    ) -> bool:
        return dense_query_encoder_matches_contract(
            query_encoder=self._encoder,
            encoder_contract=details.get("encoder_contract"),
            model_id=self.model_id,
            dimension=self.dimension,
            query_prefix=self._query_prefix,
        )

    def _encode(self, text: str) -> list[float]:
        encoder = self._encoder
        if encoder is None:
            from sentence_transformers import SentenceTransformer

            encoder = SentenceTransformer(self.model_id)
            self._encoder = encoder
        encode = getattr(encoder, "encode", None)
        if callable(encode):
            vector = encode(text)
        elif callable(encoder):
            vector = encoder(text)
        else:
            raise TypeError("encoder is not callable")
        if isinstance(vector, (str, bytes, Mapping)):
            raise ValueError("encoder returned an invalid vector")
        values = [float(value) for value in vector]
        if len(values) != self.dimension or not all(
            math.isfinite(value) for value in values
        ):
            raise ValueError("encoder returned an invalid vector")
        return values

    def _get_client(self) -> object:
        if self._client is None:
            self._client = create_qdrant_client(
                qdrant_url=self._qdrant_url,
                qdrant_api_key=self._qdrant_api_key,
                qdrant_path=self._qdrant_path,
                timeout_seconds=self._timeout_seconds,
                client_factory=self._client_factory,
            )
        return self._client

    @staticmethod
    def _query_client(
        client: object,
        *,
        collection_name: str,
        vector: list[float],
        limit: int,
    ) -> object:
        query_points = getattr(client, "query_points", None)
        if callable(query_points):
            return query_points(
                collection_name=collection_name,
                query=vector,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        search = getattr(client, "search", None)
        if callable(search):
            return search(
                collection_name=collection_name,
                query_vector=vector,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        raise TypeError("Qdrant client has no supported query method")

    def _validate_point(
        self,
        connection: sqlite3.Connection,
        workspace_id: str,
        generation: int,
        point: object,
    ) -> tuple[str, str, str, object, float | None] | None:
        point_id = _point_field(point, "id")
        payload = _point_field(point, "payload")
        if (
            not isinstance(point_id, str)
            or not isinstance(payload, Mapping)
            or frozenset(payload) != _DENSE_PAYLOAD_KEYS
            or payload.get("workspace_id") != workspace_id
            or payload.get("content_hash") is None
            or payload.get("model_id") != self.model_id
        ):
            return None
        record_id = payload.get("record_id")
        if (
            not isinstance(record_id, str)
            or _RECORD_ID.fullmatch(record_id) is None
            or point_id != dense_point_id(workspace_id, record_id)
        ):
            return None
        payload_generation = payload.get("projection_generation")
        if (
            isinstance(payload_generation, bool)
            or not isinstance(payload_generation, int)
            or payload_generation != generation
        ):
            return None
        payload_hash = payload.get("content_hash")
        if not isinstance(payload_hash, str) or _CONTENT_HASH.fullmatch(payload_hash) is None:
            return None
        row = connection.execute(
            """
            SELECT dense.content_hash,dense.model_id,dense.dimension,dense.state,
                   dense.updated_event_id,record.content_hash,
                   record.source_event_id,record.updated_at_us,record.deleted_at_us
            FROM dense_projection_refs AS dense
            JOIN memory_records AS record
              ON record.record_id=dense.record_id
             AND record.workspace_id=dense.workspace_id
            WHERE dense.workspace_id=? AND dense.provider_key=?
              AND dense.projection_generation=? AND dense.record_id=?
            """,
            (workspace_id, self.provider_key, generation, record_id),
        ).fetchone()
        if row is None or not (
            row[0] == payload_hash
            and row[1] == self.model_id
            and row[2] == self.dimension
            and row[3] == "ready"
            and row[4] == row[6]
            and row[5] == payload_hash
            and row[8] is None
        ):
            return None
        raw_score = _point_field(point, "score")
        score: float | None = None
        if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool):
            converted = float(raw_score)
            if math.isfinite(converted):
                score = converted
        return record_id, payload_hash, str(row[6]), row[7], score

    def _result(
        self,
        started: int,
        *,
        candidates: tuple[Candidate, ...] = (),
        status: ProviderStatus = "ready",
        reason: str | None = None,
        generation: int | None = None,
    ) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            candidates=candidates,
            status=status,
            manifest_generation=generation,
            elapsed_ms=(perf_counter_ns() - started) / 1_000_000,
            reason=reason,
        )


__all__ = [
    "DENSE_BUILDER_VERSION",
    "DenseProvider",
    "LexicalProvider",
    "build_dense_point_payload",
    "create_qdrant_client",
    "dense_builder_contract",
    "dense_encoder_contract",
    "dense_query_encoder_matches_contract",
    "dense_manifest_details",
    "dense_point_id",
]
