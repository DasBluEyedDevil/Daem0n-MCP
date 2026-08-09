"""Dependency-free end-to-end coverage for the v7 retrieval runtime."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


WORKSPACE_ID = "ws_0123456789abcdef01234567"


def _apply_retrieval_schema(connection: sqlite3.Connection) -> None:
    from daem0nmcp.migrations.schema import MIGRATIONS

    connection.execute(
        "CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT)"
    )
    for version, _description, statements in MIGRATIONS:
        if version < 16 or version > 18:
            continue
        for statement in statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_version(version,applied_at) VALUES (?,'now')",
            (version,),
        )
    connection.commit()


def _record(content: str) -> dict[str, object]:
    return {
        "record_type": "decision",
        "legacy_type": None,
        "content": content,
        "rationale": "runtime integration evidence",
        "context": {},
        "tags": ["runtime"],
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
        "source_client": "test",
        "source_model": None,
        "deleted_at_us": None,
    }


def _append(connection: sqlite3.Connection, suffix: str, content: str, at: int) -> str:
    from daem0nmcp.event_store import EventCommand, EventStore

    record_id = "mem_" + suffix * 64
    EventStore(connection).append_and_project(
        EventCommand(
            workspace_id=WORKSPACE_ID,
            stream_id=record_id,
            stream_kind="memory",
            event_type="memory.created",
            occurred_at_us=at,
            recorded_at_us=at,
            actor_type="system",
            payload={"record": _record(content)},
        )
    )
    return record_id


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        embedding_backend="torch",
        embedding_dimension=256,
        embedding_document_prefix="search_document: ",
        embedding_model="nomic-ai/modernbert-embed-base",
        embedding_query_prefix="search_query: ",
        qdrant_api_key=None,
        qdrant_collection_prefix="daem0nmcp",
        qdrant_path=None,
        qdrant_timeout_seconds=1.0,
        qdrant_url=None,
        retrieval_candidate_limit=50,
        retrieval_graph_max_branching=25,
        retrieval_graph_max_depth=2,
        retrieval_rerank_candidate_limit=25,
        retrieval_rerank_enabled=False,
        retrieval_rrf_weights={
            "lexical": 1.0,
            "dense": 1.0,
            "graph": 0.7,
            "temporal": 0.85,
            "procedure": 0.8,
            "outcome": 0.9,
        },
        rrf_k=60,
    )


class RetrievalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "runtime.db"
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        _apply_retrieval_schema(connection)
        self.first_id = _append(connection, "1", "durable runtime baseline", 100)
        from daem0nmcp.retrieval.projections import LexicalProjectionBuilder

        LexicalProjectionBuilder(connection, clock_us=lambda: 200).rebuild(
            WORKSPACE_ID
        )
        connection.commit()
        connection.close()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    async def test_factory_runs_real_lexical_policy_repository_and_composer(self):
        from daem0nmcp.retrieval.runtime import create_retrieval_service
        from daem0nmcp.retrieval.types import RetrievalQuery

        service = create_retrieval_service(
            self.path,
            config=_settings(),
        )
        result = await service.retrieve(
            RetrievalQuery(
                workspace_id=WORKSPACE_ID,
                text="durable runtime",
                token_budget=200,
            )
        )

        self.assertFalse(result.abstained)
        self.assertEqual(self.first_id, result.items[0].evidence_refs[0].record_id)
        self.assertEqual("lexical", result.providers[0].provider)
        self.assertIn("durable runtime baseline", result.context.text)

    async def test_durable_lexical_job_is_drained_off_loop_and_refreshes_search(self):
        connection = sqlite3.connect(self.path)
        second_id = _append(connection, "2", "novel queued projection term", 300)
        connection.commit()
        connection.close()

        from daem0nmcp.retrieval.runtime import drain_projection_jobs
        from daem0nmcp.retrieval.providers import LexicalProvider
        from daem0nmcp.retrieval.repository import sqlite_read_connection_factory
        from daem0nmcp.retrieval.types import RetrievalQuery

        runs = await drain_projection_jobs(
            self.path,
            config=_settings(),
            max_jobs=1,
            include_optional=False,
        )
        self.assertEqual(1, len(runs))
        self.assertEqual("succeeded", runs[0].status)
        self.assertEqual(("lexical",), runs[0].projections)

        result = await LexicalProvider(
            connection_factory=sqlite_read_connection_factory(self.path)
        ).search(
            RetrievalQuery(workspace_id=WORKSPACE_ID, text="novel queued"),
            10,
        )
        self.assertEqual("ready", result.status)
        self.assertEqual(
            [second_id],
            [candidate.evidence.record_id for candidate in result.candidates],
        )

    async def test_legacy_date_filter_resolves_only_canonical_opaque_ids(self):
        connection = sqlite3.connect(self.path)
        second_id = _append(connection, "2", "newer filter target", 300)
        connection.commit()
        connection.close()

        from daem0nmcp.retrieval.runtime import resolve_legacy_record_filter

        selected = await resolve_legacy_record_filter(
            self.path,
            workspace_id=WORKSPACE_ID,
            since=datetime.fromtimestamp(0, timezone.utc).replace(
                microsecond=250
            ),
        )
        self.assertEqual(frozenset({second_id}), selected)

    def test_include_warnings_does_not_narrow_an_unfiltered_legacy_recall(self):
        from daem0nmcp.retrieval.runtime import normalize_legacy_category_filter

        self.assertIsNone(normalize_legacy_category_filter(None, True))
        self.assertIsNone(normalize_legacy_category_filter([], True))
        self.assertEqual(
            frozenset({"decision", "warning"}),
            normalize_legacy_category_filter(["decision"], True),
        )
        self.assertEqual(
            frozenset({"decision"}),
            normalize_legacy_category_filter(["decision"], False),
        )
        with self.assertRaises(ValueError):
            normalize_legacy_category_filter(1, True)

    def test_configured_embedding_backend_never_silently_changes_contract(self):
        from daem0nmcp.retrieval.runtime import ConfiguredEmbeddingEncoder

        calls: list[dict[str, object]] = []
        fake = types.ModuleType("sentence_transformers")

        def sentence_transformer(_model_id, **kwargs):
            calls.append(kwargs)
            if "backend" in kwargs:
                raise RuntimeError("configured backend unavailable")
            return object()

        fake.SentenceTransformer = sentence_transformer
        previous = sys.modules.get("sentence_transformers")
        sys.modules["sentence_transformers"] = fake
        try:
            encoder = ConfiguredEmbeddingEncoder(
                model_id="test/model",
                dimension=2,
                prefix="query: ",
                backend="onnx",
            )
            with self.assertRaisesRegex(RuntimeError, "DENSE_ENCODER_UNAVAILABLE"):
                encoder.encode("text")
        finally:
            if previous is None:
                sys.modules.pop("sentence_transformers", None)
            else:
                sys.modules["sentence_transformers"] = previous

        self.assertEqual(1, len(calls))
        self.assertEqual("onnx", calls[0]["backend"])

    def test_runtime_builds_distinct_query_and_document_encoder_contracts(self):
        from daem0nmcp.retrieval.runtime import _embedding_encoder

        query_encoder = _embedding_encoder(_settings(), "query")
        document_encoder = _embedding_encoder(_settings(), "document")

        self.assertEqual("search_query: ", query_encoder.prefix)
        self.assertEqual("search_document: ", document_encoder.prefix)
        self.assertEqual(query_encoder.model_id, document_encoder.model_id)
        self.assertEqual(query_encoder.dimension, document_encoder.dimension)

    def test_v6_hybrid_weight_adapter_emits_a_deprecation_warning(self):
        from daem0nmcp.retrieval.runtime import warn_legacy_hybrid_weight

        with self.assertWarnsRegex(
            DeprecationWarning,
            "hybrid_vector_weight is a v6-only compatibility setting",
        ):
            warn_legacy_hybrid_weight()

    async def test_optional_projection_drain_scheduler_coalesces_by_database(self):
        from unittest.mock import patch

        from daem0nmcp.retrieval.runtime import schedule_projection_job_drain

        started = __import__("asyncio").Event()
        release = __import__("asyncio").Event()
        calls: list[dict[str, object]] = []

        async def fake_drain(database_path, **kwargs):
            calls.append({"database_path": database_path, **kwargs})
            started.set()
            await release.wait()
            return ()

        with patch(
            "daem0nmcp.retrieval.runtime.drain_projection_jobs",
            new=fake_drain,
        ):
            first = schedule_projection_job_drain(
                self.path,
                config=_settings(),
                max_jobs=5,
            )
            second = schedule_projection_job_drain(
                self.path,
                config=_settings(),
                max_jobs=5,
            )
            self.assertIs(first, second)
            await started.wait()
            release.set()
            await first

            third = schedule_projection_job_drain(
                self.path,
                config=_settings(),
                max_jobs=5,
            )
            await third

        self.assertEqual(2, len(calls))
        self.assertTrue(all(call["include_optional"] for call in calls))
        self.assertTrue(all(call["max_jobs"] == 5 for call in calls))


if __name__ == "__main__":
    unittest.main()
