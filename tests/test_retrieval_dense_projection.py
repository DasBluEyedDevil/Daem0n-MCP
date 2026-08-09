"""Dense projection lifecycle contracts with deterministic local fakes."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace


WORKSPACE_ID = "ws_0123456789abcdef01234567"


def _schema_migrations():
    path = (
        Path(__file__).resolve().parents[1]
        / "daem0nmcp"
        / "migrations"
        / "schema.py"
    )
    spec = importlib.util.spec_from_file_location("dense_test_schema", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MIGRATIONS


def _apply_migration(connection: sqlite3.Connection, version: int) -> None:
    migration = next(item for item in _schema_migrations() if item[0] == version)
    for statement in migration[2]:
        connection.execute(statement)


class DeterministicEncoder:
    def encode(self, text: str) -> list[float]:
        return [
            float(len(text)),
            float(sum(text.encode("utf-8")) % 997),
            float(text.count(" ") + 1),
        ]


class ContractEncoder:
    def __init__(self, prefix: str) -> None:
        self.model_id = "deterministic-test-model"
        self.dimension = 3
        self.prefix = prefix
        self.backend = "test-backend"
        self.max_seq_length = 512

    def encode(self, text: str) -> list[float]:
        value = f"{self.prefix}{text}"
        return [
            float(len(value)),
            float(sum(value.encode("utf-8")) % 997),
            float(value.count(" ") + 1),
        ]


class FakeQdrantClient:
    """Small behavioral fake for the Qdrant collection boundary."""

    def __init__(self) -> None:
        self.collections: dict[str, dict[str, object]] = {}
        self.corrupt_retrieval = False
        self.object_retrieval = False

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def delete_collection(self, collection_name: str) -> None:
        self.collections.pop(collection_name, None)

    def create_collection(
        self, *, collection_name: str, vectors_config: object
    ) -> None:
        self.collections[collection_name] = {
            "vectors_config": vectors_config,
            "points": {},
        }

    def upsert(
        self, *, collection_name: str, points: list[dict[str, object]], wait: bool
    ) -> None:
        del wait
        stored = self.collections[collection_name]["points"]
        assert isinstance(stored, dict)
        for point in points:
            stored[str(point["id"])] = {
                "id": point["id"],
                "payload": dict(point["payload"]),
                "vector": list(point["vector"]),
            }

    def retrieve(
        self,
        *,
        collection_name: str,
        ids: list[str],
        with_payload: bool,
        with_vectors: bool,
    ) -> list[object]:
        del with_payload, with_vectors
        stored = self.collections[collection_name]["points"]
        assert isinstance(stored, dict)
        points = [
            copy.deepcopy(stored[point_id])
            for point_id in ids
            if point_id in stored
        ]
        if self.corrupt_retrieval and points:
            payload = points[0]["payload"]
            assert isinstance(payload, dict)
            payload["content_hash"] = "f" * 64
        if self.object_retrieval:
            return [SimpleNamespace(**point) for point in points]
        return points

    def count(self, *, collection_name: str, exact: bool) -> dict[str, int]:
        del exact
        stored = self.collections[collection_name]["points"]
        assert isinstance(stored, dict)
        return {"count": len(stored)}


class FakeDistance:
    COSINE = "Cosine"


class FakeVectorParams:
    def __init__(self, *, size: int, distance: object) -> None:
        self.size = size
        self.distance = distance


class FakePointStruct:
    def __init__(
        self,
        *,
        id: str,
        vector: list[float],
        payload: dict[str, object],
    ) -> None:
        self.id = id
        self.vector = vector
        self.payload = payload


class FakeQdrantModels:
    Distance = FakeDistance
    PointStruct = FakePointStruct
    VectorParams = FakeVectorParams


class LegacyStrictQdrantClient(FakeQdrantClient):
    """Qdrant 1.7-shaped fake that rejects raw model dictionaries."""

    collection_exists = None

    def get_collections(self) -> SimpleNamespace:
        return SimpleNamespace(
            collections=[
                SimpleNamespace(name=name) for name in self.collections
            ]
        )

    def create_collection(
        self, *, collection_name: str, vectors_config: object
    ) -> None:
        if not isinstance(vectors_config, FakeVectorParams):
            raise TypeError("anonymous vectors require VectorParams")
        super().create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
        )

    def upsert(
        self, *, collection_name: str, points: list[object], wait: bool
    ) -> None:
        converted: list[dict[str, object]] = []
        for point in points:
            if not isinstance(point, FakePointStruct):
                raise TypeError("points require PointStruct")
            converted.append(
                {
                    "id": point.id,
                    "vector": point.vector,
                    "payload": point.payload,
                }
            )
        super().upsert(
            collection_name=collection_name,
            points=converted,
            wait=wait,
        )


class DenseProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database_path = Path(directory.name) / "dense.sqlite3"
        self.connection = sqlite3.connect(self.database_path)
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        for version in (16, 17, 18):
            _apply_migration(self.connection, version)
        self.connection.commit()
        self.client = FakeQdrantClient()
        self.encoder = DeterministicEncoder()
        self._record_number = 0

    @staticmethod
    def _record(content: str) -> dict[str, object]:
        return {
            "record_type": "decision",
            "legacy_type": None,
            "content": content,
            "rationale": None,
            "context": {},
            "tags": [],
            "file_path": None,
            "file_path_relative": None,
            "keywords": None,
            "is_permanent": False,
            "pinned": False,
            "archived": False,
            "outcome": None,
            "worked": None,
            "recall_count": 0,
            "surprise_score": None,
            "importance_score": None,
            "source_client": "dense-test",
            "source_model": None,
            "deleted_at_us": None,
        }

    def _append(self, suffix: str, content: str) -> str:
        from daem0nmcp.event_store import EventCommand, EventStore

        self._record_number += 1
        record_id = "mem_" + suffix * 64
        EventStore(self.connection).append_and_project(
            EventCommand(
                workspace_id=WORKSPACE_ID,
                stream_id=record_id,
                stream_kind="memory",
                event_type="memory.created",
                occurred_at_us=100 + self._record_number,
                recorded_at_us=200 + self._record_number,
                actor_type="system",
                payload={"record": self._record(content)},
            )
        )
        self.connection.commit()
        return record_id

    def _builder(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuilder

        return DenseProjectionBuilder(
            self.connection,
            provider_key="local",
            model_id="deterministic-test-model",
            dimension=3,
            encoder=self.encoder,
            client=self.client,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

    def test_build_activates_only_after_points_and_refs_match_canonical_records(self):
        first_id = self._append("1", "first dense record")
        second_id = self._append("2", "second dense record")

        result = self._builder().rebuild(WORKSPACE_ID)

        self.assertEqual("active", result.status)
        self.assertEqual(1, result.generation)
        self.assertEqual(2, result.row_count)
        manifest = self.connection.execute(
            "SELECT status,row_count,source_event_count,source_event_root_hash,"
            "details_json "
            "FROM projection_manifests WHERE manifest_id=?",
            (result.staging_manifest_id,),
        ).fetchone()
        self.assertIsNotNone(manifest)
        self.assertEqual(("active", 2, 2), tuple(manifest[:3]))
        expected_root = hashlib.sha256(
            b"".join(
                bytes.fromhex(str(row[0]))
                for row in self.connection.execute(
                    "SELECT event_hash FROM memory_events "
                    "WHERE workspace_id=? ORDER BY event_id",
                    (WORKSPACE_ID,),
                )
            )
        ).hexdigest()
        self.assertEqual(expected_root, result.source_event_root_hash)
        self.assertEqual(expected_root, manifest[3])
        details = json.loads(str(manifest[4]))
        self.assertEqual(result.content_digest, details["content_digest"])
        self.assertEqual(result.build_config_hash, details["build_config_hash"])
        self.assertEqual(result.collection_name, details["collection_name"])

        refs = self.connection.execute(
            "SELECT record_id,content_hash,model_id,dimension,state,updated_event_id "
            "FROM dense_projection_refs ORDER BY record_id"
        ).fetchall()
        self.assertEqual([first_id, second_id], [row[0] for row in refs])
        self.assertTrue(all(row[2:] and row[4] == "ready" for row in refs))
        dense_columns = {
            str(row[1]).lower()
            for row in self.connection.execute(
                "PRAGMA table_info(dense_projection_refs)"
            )
        }
        self.assertFalse(dense_columns & {"content", "vector", "embedding", "blob"})
        points = self.client.collections[result.collection_name]["points"]
        self.assertIsInstance(points, dict)
        self.assertEqual(2, len(points))
        for point_id, point in points.items():
            self.assertEqual(str(uuid.UUID(point_id)), point_id)
            payload = point["payload"]
            self.assertIn(payload["record_id"], {first_id, second_id})
            self.assertNotIn("content", payload)
            self.assertNotIn("vector", payload)

    def test_dry_run_reports_exact_staging_inventory_without_writes(self):
        self._append("3", "existing record")
        active = self._builder().rebuild(WORKSPACE_ID)
        self._append("4", "new source record")
        before_changes = self.connection.total_changes
        before_collections = copy.deepcopy(self.client.collections)

        preview = self._builder().rebuild(WORKSPACE_ID, dry_run=True)

        self.assertTrue(preview.dry_run)
        self.assertEqual("ready", preview.status)
        self.assertEqual("ready", preview.capability_status)
        self.assertIsNone(preview.capability_reason)
        self.assertEqual(active.staging_manifest_id, preview.active_manifest_id)
        self.assertEqual(1, preview.active_generation)
        self.assertEqual("active", preview.active_status)
        self.assertEqual(1, preview.active_row_count)
        self.assertEqual(1, preview.row_count_delta)
        self.assertEqual(active.content_digest, preview.active_content_digest)
        self.assertTrue(preview.content_digest_changed)
        self.assertEqual(2, preview.generation)
        self.assertEqual(2, preview.source_event_count)
        self.assertEqual(2, preview.row_count)
        self.assertEqual("local", preview.provider_key)
        self.assertEqual("deterministic-test-model", preview.model_id)
        self.assertEqual(3, preview.dimension)
        self.assertRegex(preview.build_config_hash, r"^[0-9a-f]{64}$")
        self.assertRegex(preview.content_digest, r"^[0-9a-f]{64}$")
        self.assertIn("-g2-", preview.collection_name)
        self.assertIsNotNone(preview.staging_manifest_id)
        self.assertEqual(before_changes, self.connection.total_changes)
        self.assertEqual(before_collections, self.client.collections)
        self.assertEqual(
            [(1, "active")],
            [
                tuple(row)
                for row in self.connection.execute(
                    "SELECT generation,status FROM projection_manifests "
                    "WHERE workspace_id=? AND projection_name='dense'",
                    (WORKSPACE_ID,),
                )
            ],
        )

    def test_retry_of_current_source_reuses_validated_active_generation(self):
        self._append("5", "stable source")
        first = self._builder().rebuild(WORKSPACE_ID)
        before_changes = self.connection.total_changes
        before_collections = copy.deepcopy(self.client.collections)

        retried = self._builder().rebuild(WORKSPACE_ID)

        self.assertTrue(retried.reused)
        self.assertEqual(first.generation, retried.generation)
        self.assertEqual(first.staging_manifest_id, retried.staging_manifest_id)
        self.assertEqual("active", retried.status)
        self.assertEqual(before_changes, self.connection.total_changes)
        self.assertEqual(before_collections, self.client.collections)
        self.assertEqual(
            [(1, "active")],
            [
                tuple(row)
                for row in self.connection.execute(
                    "SELECT generation,status FROM projection_manifests "
                    "WHERE projection_name='dense'"
                )
            ],
        )

    def test_manifest_contract_hash_binds_encoder_and_builder_semantics(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuilder

        self._append("5", "contract-bound source")
        encoder = ContractEncoder("search_document: ")
        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="local",
            model_id="deterministic-test-model",
            dimension=3,
            encoder=encoder,
            query_prefix="search_query: ",
            client=self.client,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        result = builder.rebuild(WORKSPACE_ID)

        details = json.loads(
            str(
                self.connection.execute(
                    "SELECT details_json FROM projection_manifests "
                    "WHERE manifest_id=?",
                    (result.staging_manifest_id,),
                ).fetchone()[0]
            )
        )
        expected_encoder_contract = {
            "backend": "test-backend",
            "document_prefix": "search_document: ",
            "encoder_type": (
                f"{ContractEncoder.__module__}."
                f"{ContractEncoder.__qualname__}"
            ),
            "input_source": "memory_records.content",
            "max_sequence_length": 512,
            "model_id": "deterministic-test-model",
            "output_dimension": 3,
            "query_prefix": "search_query: ",
            "truncate_dimension": 3,
        }
        expected_contract_hash = hashlib.sha256(
            json.dumps(
                {
                    "build_config_hash": result.build_config_hash,
                    "builder_version": "retrieval-dense-1",
                    "encoder_contract": expected_encoder_contract,
                    "projection": "dense",
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(expected_encoder_contract, details["encoder_contract"])
        self.assertEqual(
            expected_contract_hash, details["builder_contract_hash"]
        )
        self.assertEqual(expected_contract_hash, result.builder_contract_hash)

        changed = DenseProjectionBuilder(
            self.connection,
            provider_key="local",
            model_id="deterministic-test-model",
            dimension=3,
            encoder=ContractEncoder("search_document: "),
            query_prefix="different_query: ",
            client=self.client,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )
        self.assertFalse(changed.active_is_current(WORKSPACE_ID))
        preview = changed.rebuild(WORKSPACE_ID, dry_run=True)
        self.assertNotEqual(
            result.builder_contract_hash, preview.builder_contract_hash
        )

    def test_encoder_backend_fallback_cannot_activate_false_contract(self):
        from daem0nmcp.retrieval.dense_projection import (
            DenseProjectionBuilder,
            DenseProjectionBuildError,
        )

        self._append("6", "backend-bound source")

        class FallbackEncoder(ContractEncoder):
            def encode(self, text: str) -> list[float]:
                self.backend = "fallback-backend"
                return super().encode(text)

        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="local",
            model_id="deterministic-test-model",
            dimension=3,
            encoder=FallbackEncoder("search_document: "),
            query_prefix="search_query: ",
            client=self.client,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        with self.assertRaises(DenseProjectionBuildError) as raised:
            builder.rebuild(WORKSPACE_ID)

        self.assertEqual("PROJECTION_VALIDATION_FAILED", raised.exception.code)
        self.assertEqual(
            0,
            self.connection.execute(
                "SELECT count(*) FROM projection_manifests "
                "WHERE projection_name='dense'"
            ).fetchone()[0],
        )
    def test_dry_run_sanitizes_optional_dense_capability_unavailable(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuilder

        self._append("6", "lexical remains sufficient")
        before_changes = self.connection.total_changes
        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="optional",
            model_id="missing-model",
            dimension=3,
            encoder=None,
            client=None,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        preview = builder.rebuild(WORKSPACE_ID, dry_run=True)

        self.assertEqual("unavailable", preview.status)
        self.assertEqual("unavailable", preview.capability_status)
        self.assertEqual("DENSE_UNAVAILABLE", preview.capability_reason)
        self.assertEqual(1, preview.row_count)
        self.assertEqual(1, preview.source_event_count)
        self.assertEqual(before_changes, self.connection.total_changes)
        self.assertEqual({}, self.client.collections)

    def test_dry_run_rejects_incomplete_explicit_client_capability(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuilder

        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="invalid-client",
            model_id="test-model",
            dimension=3,
            encoder=self.encoder,
            client=object(),
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        preview = builder.rebuild(WORKSPACE_ID, dry_run=True)

        self.assertEqual("unavailable", preview.capability_status)
        self.assertEqual("DENSE_UNAVAILABLE", preview.capability_reason)

    def test_timeout_overflow_is_rejected_as_a_bounded_validation_error(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuilder

        with self.assertRaises(ValueError) as raised:
            DenseProjectionBuilder(
                self.connection,
                provider_key="local",
                model_id="test-model",
                dimension=3,
                encoder=self.encoder,
                client=self.client,
                timeout_seconds=10**400,
            )

        self.assertEqual(
            "timeout_seconds must be a positive finite number",
            str(raised.exception),
        )

    def test_required_build_fails_with_only_sanitized_unavailable_code(self):
        from daem0nmcp.retrieval.dense_projection import (
            DenseProjectionBuilder,
            DenseProjectionBuildError,
        )

        self._append("7", "source remains canonical")
        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="optional",
            model_id="missing-model",
            dimension=3,
            encoder=None,
            client=None,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        with self.assertRaises(DenseProjectionBuildError) as raised:
            builder.rebuild(WORKSPACE_ID)

        self.assertEqual("DENSE_UNAVAILABLE", raised.exception.code)
        self.assertEqual(
            "DENSE_UNAVAILABLE: dense projection capability is unavailable",
            str(raised.exception),
        )
        self.assertEqual(
            0,
            self.connection.execute(
                "SELECT count(*) FROM projection_manifests "
                "WHERE projection_name='dense'"
            ).fetchone()[0],
        )

    def test_client_factory_preserves_distinct_remote_and_local_semantics(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuilder

        created: list[tuple[dict[str, object], FakeQdrantClient]] = []

        def factory(**kwargs: object) -> FakeQdrantClient:
            client = FakeQdrantClient()
            created.append((dict(kwargs), client))
            return client

        self._append("8", "remote source")
        remote = DenseProjectionBuilder(
            self.connection,
            provider_key="remote",
            model_id="remote-model",
            dimension=3,
            encoder=self.encoder,
            qdrant_url="https://qdrant.invalid",
            qdrant_api_key="test-key",
            timeout_seconds=4.5,
            client_factory=factory,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        ).rebuild(WORKSPACE_ID)
        self.assertEqual(
            {
                "url": "https://qdrant.invalid",
                "api_key": "test-key",
                "timeout": 4.5,
            },
            created[0][0],
        )
        self.assertIn(remote.collection_name, created[0][1].collections)

        local = DenseProjectionBuilder(
            self.connection,
            provider_key="local",
            model_id="local-model",
            dimension=3,
            encoder=self.encoder,
            qdrant_path="isolated-local-qdrant",
            timeout_seconds=2.0,
            client_factory=factory,
            collection_prefix="test-dense",
            clock_us=lambda: 600,
        ).rebuild(WORKSPACE_ID)
        self.assertEqual({"path": "isolated-local-qdrant"}, created[1][0])
        self.assertIn(local.collection_name, created[1][1].collections)

    def test_qdrant_17_adapter_uses_models_without_collection_exists(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuilder

        self._append("f", "legacy client contract")
        client = LegacyStrictQdrantClient()
        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="legacy-local",
            model_id="legacy-model",
            dimension=3,
            encoder=self.encoder,
            client=client,
            qdrant_models=FakeQdrantModels,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        result = builder.rebuild(WORKSPACE_ID)

        collection = client.collections[result.collection_name]
        self.assertIsInstance(collection["vectors_config"], FakeVectorParams)
        self.assertEqual(3, collection["vectors_config"].size)
        self.assertEqual("Cosine", collection["vectors_config"].distance)
        self.assertEqual(1, len(collection["points"]))
        self.assertTrue(builder.active_is_current(WORKSPACE_ID))

    def test_active_is_current_checks_manifest_ref_and_point_bindings(self):
        record_id = self._append("9", "validated evidence")
        builder = self._builder()
        builder.rebuild(WORKSPACE_ID)
        self.assertTrue(builder.active_is_current(WORKSPACE_ID))

        self.connection.execute(
            "UPDATE dense_projection_refs SET state='failed',failure_code='TEST' "
            "WHERE record_id=?",
            (record_id,),
        )
        self.connection.commit()

        self.assertFalse(builder.active_is_current(WORKSPACE_ID))

    def test_failed_staging_validation_retains_prior_active_generation(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuildError

        self._append("a", "prior active evidence")
        builder = self._builder()
        first = builder.rebuild(WORKSPACE_ID)
        first_collection = copy.deepcopy(
            self.client.collections[first.collection_name]
        )
        self._append("b", "new generation evidence")
        self.client.corrupt_retrieval = True

        with self.assertRaises(DenseProjectionBuildError) as raised:
            builder.rebuild(WORKSPACE_ID)

        self.assertEqual("PROJECTION_VALIDATION_FAILED", raised.exception.code)
        self.assertEqual(
            [(1, "active")],
            [
                tuple(row)
                for row in self.connection.execute(
                    "SELECT generation,status FROM projection_manifests "
                    "WHERE projection_name='dense' ORDER BY generation"
                )
            ],
        )
        self.assertEqual(
            [(1, "ready")],
            [
                tuple(row)
                for row in self.connection.execute(
                    "SELECT projection_generation,state FROM dense_projection_refs"
                )
            ],
        )
        self.assertEqual(
            first_collection, self.client.collections[first.collection_name]
        )

    def test_retry_replaces_orphan_staging_collection_at_same_generation(self):
        from daem0nmcp.retrieval.dense_projection import DenseProjectionBuildError

        self._append("c", "prior generation")
        builder = self._builder()
        builder.rebuild(WORKSPACE_ID)
        self._append("d", "retry source")
        self.client.corrupt_retrieval = True
        with self.assertRaises(DenseProjectionBuildError):
            builder.rebuild(WORKSPACE_ID)
        self.client.corrupt_retrieval = False

        retried = builder.rebuild(WORKSPACE_ID)

        self.assertEqual(2, retried.generation)
        self.assertEqual("active", retried.status)
        self.assertEqual(2, retried.row_count)
        self.assertTrue(builder.active_is_current(WORKSPACE_ID))

    def test_validation_accepts_qdrant_record_objects_not_only_mappings(self):
        self._append("e", "object response")
        self.client.object_retrieval = True

        result = self._builder().rebuild(WORKSPACE_ID)

        self.assertEqual("active", result.status)
        self.assertTrue(self._builder().active_is_current(WORKSPACE_ID))

    def test_staging_manifest_tampering_cannot_activate(self):
        from daem0nmcp.retrieval.dense_projection import (
            DenseProjectionBuilder,
            DenseProjectionBuildError,
        )

        self._append("f", "manifest-bound source")
        connection = self.connection

        class TamperingEncoder(DeterministicEncoder):
            def encode(self, text: str) -> list[float]:
                connection.execute(
                    "UPDATE projection_manifests SET source_event_root_hash=? "
                    "WHERE projection_name='dense' AND status='building'",
                    ("f" * 64,),
                )
                return super().encode(text)

        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="local",
            model_id="deterministic-test-model",
            dimension=3,
            encoder=TamperingEncoder(),
            client=self.client,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        with self.assertRaises(DenseProjectionBuildError) as raised:
            builder.rebuild(WORKSPACE_ID)

        self.assertEqual("PROJECTION_VALIDATION_FAILED", raised.exception.code)
        self.assertEqual(
            0,
            self.connection.execute(
                "SELECT count(*) FROM projection_manifests "
                "WHERE projection_name='dense'"
            ).fetchone()[0],
        )

    def test_source_change_during_external_build_cannot_activate_stale_points(self):
        from daem0nmcp.retrieval.dense_projection import (
            DenseProjectionBuilder,
            DenseProjectionBuildError,
        )

        self._append("0", "initial snapshot")
        test_case = self

        class AppendingEncoder(DeterministicEncoder):
            changed = False

            def encode(self, text: str) -> list[float]:
                if not self.changed:
                    self.changed = True
                    test_case._append("1", "arrived during dense build")
                return super().encode(text)

        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="local",
            model_id="deterministic-test-model",
            dimension=3,
            encoder=AppendingEncoder(),
            client=self.client,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        with self.assertRaises(DenseProjectionBuildError) as raised:
            builder.rebuild(WORKSPACE_ID)

        self.assertEqual("PROJECTION_VALIDATION_FAILED", raised.exception.code)
        self.assertEqual(
            0,
            self.connection.execute(
                "SELECT count(*) FROM projection_manifests "
                "WHERE projection_name='dense'"
            ).fetchone()[0],
        )

    def test_external_model_work_allows_writer_then_activation_cas_rejects(self):
        from daem0nmcp.event_store import EventCommand, EventStore
        from daem0nmcp.retrieval.dense_projection import (
            DenseProjectionBuilder,
            DenseProjectionBuildError,
        )

        self._append("2", "captured snapshot")
        test_case = self

        class ConcurrentWriterEncoder(DeterministicEncoder):
            changed = False

            def encode(self, text: str) -> list[float]:
                test_case.assertFalse(test_case.connection.in_transaction)
                if not self.changed:
                    self.changed = True
                    writer = sqlite3.connect(
                        test_case.database_path, timeout=0.05
                    )
                    writer.row_factory = sqlite3.Row
                    writer.execute("PRAGMA foreign_keys=ON")
                    try:
                        EventStore(writer).append_and_project(
                            EventCommand(
                                workspace_id=WORKSPACE_ID,
                                stream_id="mem_" + "3" * 64,
                                stream_kind="memory",
                                event_type="memory.created",
                                occurred_at_us=700,
                                recorded_at_us=701,
                                actor_type="system",
                                payload={
                                    "record": test_case._record(
                                        "concurrent canonical write"
                                    )
                                },
                            )
                        )
                        writer.commit()
                    finally:
                        writer.close()
                return super().encode(text)

        class TransactionAssertingClient(FakeQdrantClient):
            def create_collection(self, **kwargs: object) -> None:
                test_case.assertFalse(test_case.connection.in_transaction)
                super().create_collection(**kwargs)

            def upsert(self, **kwargs: object) -> None:
                test_case.assertFalse(test_case.connection.in_transaction)
                super().upsert(**kwargs)

            def retrieve(self, **kwargs: object) -> object:
                test_case.assertFalse(test_case.connection.in_transaction)
                return super().retrieve(**kwargs)

            def count(self, **kwargs: object) -> object:
                test_case.assertFalse(test_case.connection.in_transaction)
                return super().count(**kwargs)

        client = TransactionAssertingClient()
        builder = DenseProjectionBuilder(
            self.connection,
            provider_key="local",
            model_id="deterministic-test-model",
            dimension=3,
            encoder=ConcurrentWriterEncoder(),
            client=client,
            collection_prefix="test-dense",
            clock_us=lambda: 500,
        )

        with self.assertRaises(DenseProjectionBuildError) as raised:
            builder.rebuild(WORKSPACE_ID)

        self.assertEqual("PROJECTION_VALIDATION_FAILED", raised.exception.code)
        self.assertEqual(
            2,
            self.connection.execute(
                "SELECT count(*) FROM memory_records WHERE workspace_id=?",
                (WORKSPACE_ID,),
            ).fetchone()[0],
        )
        self.assertEqual(
            0,
            self.connection.execute(
                "SELECT count(*) FROM projection_manifests "
                "WHERE projection_name='dense'"
            ).fetchone()[0],
        )
        self.assertEqual({}, client.collections)

    def test_older_staging_generation_cannot_replace_newer_active_build(self):
        from daem0nmcp.retrieval.dense_projection import (
            DenseProjectionBuilder,
            DenseProjectionBuildError,
        )

        self._append("4", "shared unchanged snapshot")
        encoding_started = threading.Event()
        release_encoding = threading.Event()
        first_outcome: dict[str, object] = {}

        class BlockingEncoder(DeterministicEncoder):
            def encode(self, text: str) -> list[float]:
                encoding_started.set()
                if not release_encoding.wait(timeout=5.0):
                    raise RuntimeError("test encoder was not released")
                return super().encode(text)

        def run_first_builder() -> None:
            connection = sqlite3.connect(self.database_path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                builder = DenseProjectionBuilder(
                    connection,
                    provider_key="local",
                    model_id="deterministic-test-model",
                    dimension=3,
                    encoder=BlockingEncoder(),
                    client=self.client,
                    collection_prefix="test-dense",
                    clock_us=lambda: 500,
                )
                first_outcome["result"] = builder.rebuild(WORKSPACE_ID)
            except Exception as exc:  # captured for the test thread
                first_outcome["error"] = exc
            finally:
                connection.close()

        first_thread = threading.Thread(target=run_first_builder)
        first_thread.start()
        self.addCleanup(first_thread.join, 5.0)
        self.addCleanup(release_encoding.set)
        self.assertTrue(encoding_started.wait(timeout=2.0))

        second = self._builder().rebuild(WORKSPACE_ID)
        self.assertEqual(2, second.generation)
        self.assertEqual("active", second.status)
        release_encoding.set()
        first_thread.join(timeout=5.0)

        self.assertFalse(first_thread.is_alive())
        error = first_outcome.get("error")
        self.assertIsInstance(error, DenseProjectionBuildError)
        self.assertEqual("PROJECTION_VALIDATION_FAILED", error.code)
        self.assertNotIn("result", first_outcome)
        self.assertEqual(
            [(2, "active")],
            [
                tuple(row)
                for row in self.connection.execute(
                    "SELECT generation,status FROM projection_manifests "
                    "WHERE projection_name='dense' ORDER BY generation"
                )
            ],
        )
        self.assertEqual({second.collection_name}, set(self.client.collections))


if __name__ == "__main__":
    unittest.main()
