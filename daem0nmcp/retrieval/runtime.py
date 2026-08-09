"""Production assembly and durable projection work for v7 retrieval."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import sqlite3
import threading
import warnings
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..bounded_workers import BoundedWorkerPool
from .composer import EvidenceComposer
from .jobs import ProjectionJobRun, ProjectionJobRunner
from .planner import RetrievalPlanner
from .providers import DenseProvider, LexicalProvider
from .rerank import EmbeddingSimilarityReranker
from .repository import SQLiteRetrievalRepository, sqlite_read_connection_factory
from .service import RetrievalService
from .specialized import (
    GraphProvider,
    OutcomeProvider,
    ProcedureProvider,
    TemporalProvider,
)


_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_WORKSPACE_ID = re.compile(r"^ws_[0-9a-f]{24}$")
_RUNTIME_JOB_WORKERS = BoundedWorkerPool(
    max_workers=1,
    thread_name_prefix="daem0nmcp-projection-runtime",
)
_RUNTIME_FILTER_WORKERS = BoundedWorkerPool(
    max_workers=2,
    thread_name_prefix="daem0nmcp-retrieval-filter",
)
_PROJECTION_DRAIN_TASKS: dict[Path, asyncio.Task[None]] = {}
logger = logging.getLogger(__name__)


class CoreTokenizer:
    """Dependency-free deterministic tokenizer used by the base profile."""

    def count_tokens(self, text: str) -> int:
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        return len(_TOKEN.findall(text))


def warn_legacy_hybrid_weight() -> None:
    """Mark the retained v6-only hybrid scoring setting as deprecated."""

    warnings.warn(
        "hybrid_vector_weight is a v6-only compatibility setting and is "
        "ignored by v7 retrieval",
        DeprecationWarning,
        stacklevel=2,
    )


class ConfiguredEmbeddingEncoder:
    """Lazy SentenceTransformer adapter with explicit v7 prefixes/dimension."""

    def __init__(
        self,
        *,
        model_id: str,
        dimension: int,
        prefix: str,
        backend: str,
    ) -> None:
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("model_id must be non-empty")
        if (
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension < 1
        ):
            raise ValueError("dimension must be positive")
        if not isinstance(prefix, str) or len(prefix) > 256:
            raise ValueError("embedding prefix is invalid")
        if not isinstance(backend, str) or not backend.strip():
            raise ValueError("embedding backend is invalid")
        self.model_id = model_id
        self.dimension = dimension
        self.prefix = prefix
        self.backend = backend
        self._model: object | None = None
        self._lock = threading.Lock()

    def encode(self, text: str) -> list[float]:
        if not isinstance(text, str):
            raise ValueError("embedding text must be a string")
        with self._lock:
            model = self._model
            if model is None:
                from sentence_transformers import SentenceTransformer

                try:
                    model = SentenceTransformer(
                        self.model_id,
                        truncate_dim=self.dimension,
                        backend=self.backend,
                        model_kwargs={"file_name": "onnx/model_quantized.onnx"}
                        if self.backend == "onnx"
                        else {},
                    )
                except Exception as exc:
                    raise RuntimeError("DENSE_ENCODER_UNAVAILABLE") from exc
                self._model = model
            encode = getattr(model, "encode", None)
            if not callable(encode):
                raise RuntimeError("DENSE_ENCODER_UNAVAILABLE")
            raw = encode(f"{self.prefix}{text}", convert_to_numpy=True)
        if isinstance(raw, (str, bytes, Mapping)):
            raise RuntimeError("DENSE_ENCODER_INVALID")
        try:
            values = [float(value) for value in raw]
        except (OverflowError, TypeError, ValueError) as exc:
            raise RuntimeError("DENSE_ENCODER_INVALID") from exc
        if len(values) != self.dimension or not all(map(math.isfinite, values)):
            raise RuntimeError("DENSE_ENCODER_INVALID")
        return values


def _database_path(value: str | os.PathLike[str]) -> Path:
    try:
        path = Path(value).resolve()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("database_path must identify a SQLite file") from exc
    if not path.is_file():
        raise ValueError("database_path must identify a SQLite file")
    return path


def _datetime_us(value: datetime | None, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    try:
        delta = value.astimezone(timezone.utc) - datetime(
            1970, 1, 1, tzinfo=timezone.utc
        )
        result = (
            (delta.days * 86_400 + delta.seconds) * 1_000_000
            + delta.microseconds
        )
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field_name} is outside the supported range") from exc
    if result < -(2**63) or result > 2**63 - 1:
        raise ValueError(f"{field_name} is outside the supported range")
    return result


def _resolve_legacy_record_filter_sync(
    path: Path,
    workspace_id: str,
    file_paths: tuple[str, ...],
    since_us: int | None,
    until_us: int | None,
) -> frozenset[str]:
    clauses = ["workspace_id=?", "deleted_at_us IS NULL"]
    parameters: list[object] = [workspace_id]
    if since_us is not None:
        clauses.append("created_at_us>=?")
        parameters.append(since_us)
    if until_us is not None:
        clauses.append("created_at_us<=?")
        parameters.append(until_us)
    connection = sqlite3.connect(path, timeout=2.0)
    try:
        rows = connection.execute(
            "SELECT record_id,file_path,file_path_relative FROM memory_records "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY created_at_us DESC,record_id ASC LIMIT 256",
            tuple(parameters),
        ).fetchall()
    finally:
        connection.close()
    normalized_paths = tuple(path.replace("\\", "/") for path in file_paths)

    def path_matches(row: tuple[object, ...]) -> bool:
        if not normalized_paths:
            return True
        values = tuple(
            str(value).replace("\\", "/")
            for value in row[1:]
            if value is not None
        )
        return any(
            candidate == requested
            or candidate.endswith(requested)
            or requested.endswith(candidate)
            for candidate in values
            for requested in normalized_paths
        )

    return frozenset(str(row[0]) for row in rows if path_matches(row))


async def resolve_legacy_record_filter(
    database_path: str | os.PathLike[str],
    *,
    workspace_id: str,
    file_paths: tuple[str, ...] = (),
    since: datetime | None = None,
    until: datetime | None = None,
) -> frozenset[str]:
    """Resolve legacy path/date filters to bounded canonical record IDs."""

    path = _database_path(database_path)
    if not isinstance(workspace_id, str) or _WORKSPACE_ID.fullmatch(
        workspace_id
    ) is None:
        raise ValueError("workspace_id is invalid")
    if (
        not isinstance(file_paths, tuple)
        or len(file_paths) > 2
        or any(
            not isinstance(value, str)
            or not value
            or len(value) > 4096
            for value in file_paths
        )
    ):
        raise ValueError("file_paths are invalid")
    since_us = _datetime_us(since, "since")
    until_us = _datetime_us(until, "until")
    if since_us is not None and until_us is not None and since_us > until_us:
        raise ValueError("since must not be later than until")
    return await _RUNTIME_FILTER_WORKERS.run(
        lambda: _resolve_legacy_record_filter_sync(
            path,
            workspace_id,
            file_paths,
            since_us,
            until_us,
        )
    )


def _configured_qdrant_path(path: Path, config: object) -> Path | str | None:
    if getattr(config, "qdrant_url", None) is not None:
        return None
    configured = getattr(config, "qdrant_path", None)
    return configured if configured is not None else path.parent / "qdrant"


def _embedding_encoder(
    config: object,
    purpose: Literal["query", "document"],
) -> ConfiguredEmbeddingEncoder:
    prefix_name = (
        "embedding_query_prefix"
        if purpose == "query"
        else "embedding_document_prefix"
    )
    return ConfiguredEmbeddingEncoder(
        model_id=getattr(config, "embedding_model"),
        dimension=getattr(config, "embedding_dimension"),
        prefix=getattr(config, prefix_name),
        backend=getattr(config, "embedding_backend"),
    )


def normalize_legacy_category_filter(
    categories: list[str] | tuple[str, ...] | None,
    include_warnings: bool,
) -> frozenset[str] | None:
    """Preserve legacy 'include warnings' semantics without narrowing all recalls."""

    if not isinstance(include_warnings, bool):
        raise ValueError("include_warnings must be boolean")
    if categories is None:
        return None
    if not isinstance(categories, (list, tuple)):
        raise ValueError("categories must contain non-empty strings")
    if not categories:
        return None
    if any(
        not isinstance(category, str) or not category.strip()
        for category in categories
    ):
        raise ValueError("categories must contain non-empty strings")
    selected = set(categories)
    if include_warnings:
        selected.add("warning")
    return frozenset(selected)


def create_retrieval_service(
    database_path: str | os.PathLike[str],
    *,
    config: object | None = None,
) -> RetrievalService:
    """Assemble every v7 provider around worker-local canonical SQLite reads."""

    if config is None:
        from ..config import settings

        config = settings
    path = _database_path(database_path)
    timeout = getattr(config, "qdrant_timeout_seconds")
    connection_factory = sqlite_read_connection_factory(
        path,
        busy_timeout_seconds=min(float(timeout), 60.0),
    )
    query_encoder = _embedding_encoder(config, "query")
    document_encoder = _embedding_encoder(config, "document")
    providers = {
        "lexical": LexicalProvider(
            connection_factory=connection_factory,
            timeout_seconds=min(float(timeout), 60.0),
        ),
        "dense": DenseProvider(
            connection_factory=connection_factory,
            provider_key="qdrant",
            model_id=getattr(config, "embedding_model"),
            dimension=getattr(config, "embedding_dimension"),
            encoder=query_encoder,
            document_encoder=document_encoder,
            query_prefix=getattr(config, "embedding_query_prefix"),
            qdrant_path=_configured_qdrant_path(path, config),
            qdrant_url=getattr(config, "qdrant_url"),
            qdrant_api_key=getattr(config, "qdrant_api_key"),
            timeout_seconds=timeout,
            collection_prefix=getattr(config, "qdrant_collection_prefix"),
        ),
        "graph": GraphProvider(
            connection_factory=connection_factory,
            max_depth=getattr(config, "retrieval_graph_max_depth"),
            max_branching=getattr(config, "retrieval_graph_max_branching"),
        ),
        "temporal": TemporalProvider(connection_factory=connection_factory),
        "procedure": ProcedureProvider(connection_factory=connection_factory),
        "outcome": OutcomeProvider(connection_factory=connection_factory),
    }
    reranker = None
    if getattr(config, "retrieval_rerank_enabled"):
        from ..capabilities import CapabilityRegistry

        if CapabilityRegistry().get("models-local")["status"] == "ready":
            reranker = EmbeddingSimilarityReranker(
                query_encoder=query_encoder,
                document_encoder=document_encoder,
            )
    return RetrievalService(
        providers=providers,
        repository=SQLiteRetrievalRepository(
            connection_factory=connection_factory,
        ),
        composer=EvidenceComposer(tokenizer=CoreTokenizer()),
        planner=RetrievalPlanner(
            optional_candidate_limit=getattr(
                config, "retrieval_candidate_limit"
            )
        ),
        reranker=reranker,
        rerank_enabled=getattr(config, "retrieval_rerank_enabled"),
        rerank_candidate_limit=getattr(
            config, "retrieval_rerank_candidate_limit"
        ),
        provider_timeout_seconds=timeout,
        weights=getattr(config, "retrieval_rrf_weights"),
        rrf_k=getattr(config, "rrf_k"),
    )


def create_projection_builders(
    connection: sqlite3.Connection,
    database_path: str | os.PathLike[str],
    *,
    config: object | None = None,
    include_optional: bool = True,
) -> dict[str, Any]:
    """Build the complete operator/job registry for one active v7 database."""

    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be a SQLite connection")
    if not isinstance(include_optional, bool):
        raise ValueError("include_optional must be boolean")
    if config is None:
        from ..config import settings

        config = settings
    path = _database_path(database_path)
    from .projections import LexicalProjectionBuilder

    builders: dict[str, Any] = {
        "lexical": LexicalProjectionBuilder(connection).rebuild,
    }
    if not include_optional:
        return builders

    from .dense_projection import DenseProjectionBuilder
    from .specialized_projection import SpecializedProjectionBuilder

    dense = DenseProjectionBuilder(
        connection,
        provider_key="qdrant",
        model_id=getattr(config, "embedding_model"),
        dimension=getattr(config, "embedding_dimension"),
        encoder=_embedding_encoder(config, "document"),
        qdrant_path=_configured_qdrant_path(path, config),
        qdrant_url=getattr(config, "qdrant_url"),
        qdrant_api_key=getattr(config, "qdrant_api_key"),
        timeout_seconds=getattr(config, "qdrant_timeout_seconds"),
        collection_prefix=getattr(config, "qdrant_collection_prefix"),
        query_prefix=getattr(config, "embedding_query_prefix"),
    )
    specialized = SpecializedProjectionBuilder(connection)
    builders["dense"] = dense.rebuild
    for projection_name in ("graph", "temporal", "procedure", "outcome"):
        builders[projection_name] = (
            lambda workspace_id, dry_run=False, name=projection_name: (
                specialized.rebuild(
                    workspace_id,
                    name,
                    dry_run=dry_run,
                )
            )
        )
    return builders


def _drain_projection_jobs_sync(
    path: Path,
    config: object,
    max_jobs: int,
    include_optional: bool,
) -> tuple[ProjectionJobRun, ...]:
    connection = sqlite3.connect(path, timeout=5.0)
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        runner = ProjectionJobRunner(
            connection,
            builders=create_projection_builders(
                connection,
                path,
                config=config,
                include_optional=include_optional,
            ),
        )
        runs: list[ProjectionJobRun] = []
        for _ in range(max_jobs if include_optional else 1):
            result = runner.run_once()
            if result is None:
                break
            runs.append(result)
        return tuple(runs)
    finally:
        connection.close()


async def drain_projection_jobs(
    database_path: str | os.PathLike[str],
    *,
    config: object | None = None,
    max_jobs: int = 1,
    include_optional: bool = False,
) -> tuple[ProjectionJobRun, ...]:
    """Run bounded durable projection work outside the event-loop thread."""

    if (
        isinstance(max_jobs, bool)
        or not isinstance(max_jobs, int)
        or max_jobs < 1
        or max_jobs > 100
    ):
        raise ValueError("max_jobs must be between 1 and 100")
    if not isinstance(include_optional, bool):
        raise ValueError("include_optional must be boolean")
    if config is None:
        from ..config import settings

        config = settings
    path = _database_path(database_path)
    return await _RUNTIME_JOB_WORKERS.run(
        lambda: _drain_projection_jobs_sync(
            path,
            config,
            max_jobs,
            include_optional,
        )
    )


async def _run_scheduled_projection_drain(
    path: Path,
    config: object | None,
    max_jobs: int,
) -> None:
    try:
        await drain_projection_jobs(
            path,
            config=config,
            max_jobs=max_jobs,
            include_optional=True,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        # Jobs are durable and remain eligible for the next scheduled drain or
        # an operator rebuild.  Never turn optional refresh failure into an
        # unhandled background-task exception.
        logger.warning("Optional retrieval projection refresh remains queued")


def schedule_projection_job_drain(
    database_path: str | os.PathLike[str],
    *,
    config: object | None = None,
    max_jobs: int = 5,
) -> asyncio.Task[None]:
    """Start one coalesced, off-loop optional projection drain per database."""

    if (
        isinstance(max_jobs, bool)
        or not isinstance(max_jobs, int)
        or not 1 <= max_jobs <= 100
    ):
        raise ValueError("max_jobs must be between 1 and 100")
    path = _database_path(database_path)
    active = _PROJECTION_DRAIN_TASKS.get(path)
    if active is not None and not active.done():
        return active
    task = asyncio.create_task(
        _run_scheduled_projection_drain(path, config, max_jobs),
        name="daem0nmcp-projection-drain",
    )
    _PROJECTION_DRAIN_TASKS[path] = task

    def discard(completed: asyncio.Task[None]) -> None:
        if _PROJECTION_DRAIN_TASKS.get(path) is completed:
            _PROJECTION_DRAIN_TASKS.pop(path, None)

    task.add_done_callback(discard)
    return task


__all__ = [
    "ConfiguredEmbeddingEncoder",
    "CoreTokenizer",
    "create_projection_builders",
    "create_retrieval_service",
    "drain_projection_jobs",
    "normalize_legacy_category_filter",
    "resolve_legacy_record_filter",
    "schedule_projection_job_drain",
    "warn_legacy_hybrid_weight",
]
