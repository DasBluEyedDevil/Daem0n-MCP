"""Framework-neutral v7 adapters for canonical storage operations.

The adapters in this module deliberately stop at the reviewed v7 seams: the
Task 7 event bundle/store, the Task 8 projection builders, the active format-7
database pointer, and the in-memory Covenant gate.  They never call a retained
v6 tool implementation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from types import MappingProxyType
from typing import Any, Iterator

from ...bounded_workers import BoundedWorkerBusyError, BoundedWorkerPool
from ...covenant import CovenantGate, InvocationScope
from ...event_store import (
    EventBundleError,
    EventStreamConflict,
    canonical_json_bytes,
    deterministic_id,
    event_hash_for,
    event_id_for_hash,
    export_event_bundle,
    import_event_bundle,
    memory_content_hash,
    parse_canonical_json,
    sha256_json,
)
from ...retrieval.operations import ProjectionOperationError, rebuild_projection
from ...schema_version import CURRENT_SCHEMA_VERSION
from ...storage_activation import (
    DatabaseFileLock,
    DatabaseInUseError,
    PointerValidationError,
    resolve_active_database,
)
from ...workspace import Workspace
from .application import AdmittedRequest
from .errors import STABLE_ERROR_CODE_SET
from .models import EvidenceRef, Page, RecordSummary
from .tasks import await_task_terminal
from .tools import (
    CovenantNextStep,
    CovenantStatusData,
    DiagnosticSummary,
    ExportBundle,
    ExportEvent,
    MemoryAtTimeData,
    MemoryVersionView,
    ProjectionManifest,
    ProjectionRebuildData,
    WorkspaceImportData,
)


_SCHEMA_VERSION = CURRENT_SCHEMA_VERSION
_FORMAT_VERSION = 7
_MAX_EXPORT_EVENTS = 10_000
_CURSOR_RE = re.compile(r"^cur_([0-9a-f]{64})$")
_WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\)"
)
_POSIX_ABSOLUTE_PATH = re.compile(
    r"(?:^|[\s\"'=(])/(?!/)[A-Za-z0-9_.-]"
)
_EVENT_COLUMNS = (
    "event_id,workspace_id,stream_id,stream_kind,stream_version,event_type,"
    "event_schema_version,occurred_at_us,recorded_at_us,actor_type,actor_id,"
    "causation_event_id,correlation_id,payload_json,payload_hash,"
    "previous_event_hash,event_hash"
)
_INTERNAL_EVENT_KEYS = frozenset(
    {
        "event_id",
        "workspace_id",
        "stream_id",
        "stream_kind",
        "stream_version",
        "event_type",
        "event_schema_version",
        "occurred_at_us",
        "recorded_at_us",
        "actor_type",
        "actor_id",
        "causation_event_id",
        "correlation_id",
        "payload",
        "payload_hash",
        "previous_event_hash",
        "event_hash",
    }
)
_PUBLIC_ENVELOPE_KEYS = frozenset(
    {
        "actor_id",
        "actor_type",
        "causation_event_id",
        "correlation_id",
        "data",
        "event_schema_version",
        "previous_event_hash",
        "recorded_at_us",
        "stream_id",
        "stream_kind",
        "stream_version",
    }
)
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# This is intentionally not the event loop's default executor.  The semaphore
# remains owned by the concurrent future after an asyncio waiter is cancelled,
# so cancellation cannot release capacity while SQLite still holds a lock.
_CORE_OPERATION_WORKERS = BoundedWorkerPool(
    max_workers=4,
    thread_name_prefix="daem0nmcp-v7-core",
)


class CoreOperationError(RuntimeError):
    """Sanitized operation failure understood by the shared v7 router."""

    def __init__(self, code: str) -> None:
        if code not in STABLE_ERROR_CODE_SET:
            raise ValueError("core operation error code is not stable")
        self.code = code
        super().__init__(code)


class _WorkerCancelledError(RuntimeError):
    """Internal signal proving a mutation rolled back before commit."""


def _default_storage_path(workspace: Workspace) -> Path:
    return workspace.root / ".daem0nmcp" / "storage"


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class CoreOperationDependencies:
    """Reviewed dependencies for the six canonical granular adapters."""

    covenant_gate: CovenantGate
    scope_provider: Callable[[], InvocationScope | None]
    storage_path_resolver: Callable[[Workspace], str | os.PathLike[str]] = (
        _default_storage_path
    )
    clock: Callable[[], datetime] = field(default=_default_clock)
    projection_config: object | None = None
    cursor_secret: bytes = field(default_factory=lambda: secrets.token_bytes(32))

    def __post_init__(self) -> None:
        if not isinstance(self.covenant_gate, CovenantGate):
            raise TypeError("covenant_gate must be a CovenantGate")
        for name in ("scope_provider", "storage_path_resolver", "clock"):
            if not callable(getattr(self, name)):
                raise TypeError(f"{name} must be callable")
        if not isinstance(self.cursor_secret, bytes) or len(self.cursor_secret) < 32:
            raise ValueError("cursor_secret must contain at least 32 bytes")


def _canonical_root(workspace: Workspace) -> str:
    return os.path.normcase(str(workspace.root.resolve()))


def _authorize_workspace(workspace: Workspace, request: AdmittedRequest) -> None:
    if (
        not isinstance(workspace, Workspace)
        or request.workspace_id != workspace.workspace_id
    ):
        raise CoreOperationError("UNAUTHORIZED_WORKSPACE")


def _validated_storage_path(
    dependencies: CoreOperationDependencies,
    workspace: Workspace,
) -> Path:
    try:
        root = workspace.root.resolve(strict=True)
        storage = Path(dependencies.storage_path_resolver(workspace))
        if storage.is_symlink():
            raise ValueError("storage link")
        resolved = storage.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise CoreOperationError("WORKSPACE_PATH_ESCAPE") from exc
    return resolved


def _verify_schema(connection: sqlite3.Connection) -> None:
    try:
        row = connection.execute(
            "SELECT COALESCE(MAX(version),0) FROM schema_version"
        ).fetchone()
    except sqlite3.Error as exc:
        raise CoreOperationError("CAPABILITY_DEGRADED") from exc
    if row is None or type(row[0]) is not int or row[0] != _SCHEMA_VERSION:
        raise CoreOperationError("CAPABILITY_DEGRADED")


@contextmanager
def _active_connection(
    dependencies: CoreOperationDependencies,
    workspace: Workspace,
) -> Iterator[sqlite3.Connection]:
    """Hold one shared generation lock from pointer resolution through I/O."""

    storage = _validated_storage_path(dependencies, workspace)
    try:
        with DatabaseFileLock(storage, "shared"):
            active = resolve_active_database(storage)
            if active.format_version != _FORMAT_VERSION:
                raise CoreOperationError("CAPABILITY_DEGRADED")
            connection = sqlite3.connect(active.path, timeout=5.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                _verify_schema(connection)
                yield connection
            finally:
                connection.close()
    except CoreOperationError:
        raise
    except DatabaseInUseError as exc:
        raise CoreOperationError("DATABASE_IN_USE") from exc
    except PointerValidationError as exc:
        raise CoreOperationError("CAPABILITY_DEGRADED") from exc
    except sqlite3.Error as exc:
        raise CoreOperationError("CAPABILITY_DEGRADED") from exc


async def _run_blocking(operation: Callable[[], Any]) -> Any:
    worker = asyncio.create_task(_CORE_OPERATION_WORKERS.run(operation))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancellation:
        # A thread-pool future cannot be cancelled once it has started.  Keep
        # the coroutine alive until that work reaches a terminal state so a
        # caller never observes cancellation while detached SQLite work can
        # still commit later.
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if worker.done():
            try:
                worker.result()
            except Exception:
                pass
        raise cancellation
    except BoundedWorkerBusyError as exc:
        raise CoreOperationError("TASK_REQUIRED") from exc


async def _run_mutation(
    operation: Callable[[threading.Event], Any],
) -> Any:
    cancelled = threading.Event()
    worker = asyncio.create_task(
        _CORE_OPERATION_WORKERS.run(lambda: operation(cancelled))
    )
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancellation:
        cancelled.set()
        try:
            result = await await_task_terminal(worker)
        except (_WorkerCancelledError, BoundedWorkerBusyError):
            raise cancellation from None
        except Exception:
            raise cancellation from None
        # Once the worker has committed, its receipt wins over late
        # cancellation so callers are never told a durable mutation failed.
        return result
    except BoundedWorkerBusyError as exc:
        raise CoreOperationError("TASK_REQUIRED") from exc


def _raise_if_cancelled(cancelled: threading.Event) -> None:
    if cancelled.is_set():
        raise _WorkerCancelledError()


def _utc_from_us(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CoreOperationError("IMPORT_INVALID")
    try:
        return _UNIX_EPOCH + timedelta(microseconds=value)
    except (OSError, OverflowError, ValueError) as exc:
        raise CoreOperationError("IMPORT_INVALID") from exc


def _us_from_datetime(value: object) -> int:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise CoreOperationError("IMPORT_INVALID")
    try:
        delta = value.astimezone(timezone.utc) - _UNIX_EPOCH
        return (
            delta.days * 86_400_000_000
            + delta.seconds * 1_000_000
            + delta.microseconds
        )
    except (OSError, OverflowError, ValueError) as exc:
        raise CoreOperationError("IMPORT_INVALID") from exc


def _row_event(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    try:
        event["payload"] = parse_canonical_json(event.pop("payload_json"))
    except Exception as exc:
        raise CoreOperationError("IMPORT_INVALID") from exc
    return event


def _verify_event(
    event: Mapping[str, Any],
    workspace_id: str,
    *,
    expected_previous_hash: str | None | object = ...,
) -> None:
    if set(event) != _INTERNAL_EVENT_KEYS or event.get("workspace_id") != workspace_id:
        raise CoreOperationError("IMPORT_INVALID")
    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        raise CoreOperationError("IMPORT_INVALID")
    try:
        payload_hash = sha256_json(payload)
        envelope = {
            key: event[key]
            for key in (
                "actor_id",
                "actor_type",
                "causation_event_id",
                "correlation_id",
                "event_schema_version",
                "event_type",
                "occurred_at_us",
                "payload_hash",
                "previous_event_hash",
                "recorded_at_us",
                "stream_id",
                "stream_kind",
                "stream_version",
                "workspace_id",
            )
        }
        calculated_hash = event_hash_for(envelope)
    except Exception as exc:
        raise CoreOperationError("IMPORT_INVALID") from exc
    if (
        payload_hash != event.get("payload_hash")
        or calculated_hash != event.get("event_hash")
        or event_id_for_hash(calculated_hash) != event.get("event_id")
    ):
        raise CoreOperationError("IMPORT_INVALID")
    if (
        expected_previous_hash is not ...
        and event.get("previous_event_hash") != expected_previous_hash
    ):
        raise CoreOperationError("IMPORT_INVALID")


def _validate_bundle(bundle: Mapping[str, Any], workspace_id: str) -> None:
    if (
        set(bundle) != {"workspace_id", "event_schema_version", "events", "root_hash"}
        or bundle.get("workspace_id") != workspace_id
        or bundle.get("event_schema_version") != 1
        or not isinstance(bundle.get("events"), list)
    ):
        raise CoreOperationError("IMPORT_INVALID")
    events = bundle["events"]
    if len(events) > _MAX_EXPORT_EVENTS:
        raise CoreOperationError("TASK_REQUIRED")
    event_ids: set[str] = set()
    event_hashes: set[str] = set()
    streams: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        if not isinstance(event, Mapping):
            raise CoreOperationError("IMPORT_INVALID")
        _verify_event(event, workspace_id)
        event_id = event["event_id"]
        event_hash = event["event_hash"]
        if event_id in event_ids or event_hash in event_hashes:
            raise CoreOperationError("IMPORT_INVALID")
        event_ids.add(event_id)
        event_hashes.add(event_hash)
        streams.setdefault(str(event["stream_id"]), []).append(event)
    if [event["event_id"] for event in events] != sorted(event_ids):
        raise CoreOperationError("IMPORT_INVALID")
    for stream in streams.values():
        ordered = sorted(stream, key=lambda item: item["stream_version"])
        previous: str | None = None
        for version, event in enumerate(ordered, 1):
            if event["stream_version"] != version:
                raise CoreOperationError("IMPORT_INVALID")
            _verify_event(
                event,
                workspace_id,
                expected_previous_hash=previous,
            )
            previous = str(event["event_hash"])
    if any(
        event.get("causation_event_id") is not None
        and event.get("causation_event_id") not in event_ids
        for event in events
    ):
        raise CoreOperationError("IMPORT_INVALID")
    digest = hashlib.sha256()
    try:
        for event in events:
            digest.update(bytes.fromhex(str(event["event_hash"])))
    except ValueError as exc:
        raise CoreOperationError("IMPORT_INVALID") from exc
    if bundle.get("root_hash") != digest.hexdigest():
        raise CoreOperationError("IMPORT_INVALID")


def _reject_raw_paths(value: object) -> None:
    if isinstance(value, str):
        if (
            _WINDOWS_ABSOLUTE_PATH.search(value) is not None
            or _POSIX_ABSOLUTE_PATH.search(value) is not None
        ):
            raise CoreOperationError("WORKSPACE_PATH_ESCAPE")
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if (
                key in {"file_path", "project_path", "database_path"}
                and item is not None
                and item != ""
            ):
                raise CoreOperationError("WORKSPACE_PATH_ESCAPE")
            _reject_raw_paths(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _reject_raw_paths(item)
    elif isinstance(value, (bytes, bytearray, memoryview)):
        raise CoreOperationError("CAPABILITY_DISABLED")


def _public_event(event: Mapping[str, Any]) -> ExportEvent:
    _reject_raw_paths(event["payload"])
    record_id = event["stream_id"] if event["stream_kind"] == "memory" else None
    return ExportEvent(
        event_id=event["event_id"],
        record_id=record_id,
        event_type=event["event_type"],
        happened_at=_utc_from_us(event["occurred_at_us"]),
        content_hash=event["event_hash"],
        payload={
            "actor_id": event["actor_id"],
            "actor_type": event["actor_type"],
            "causation_event_id": event["causation_event_id"],
            "correlation_id": event["correlation_id"],
            "data": event["payload"],
            "event_schema_version": event["event_schema_version"],
            "previous_event_hash": event["previous_event_hash"],
            "recorded_at_us": event["recorded_at_us"],
            "stream_id": event["stream_id"],
            "stream_kind": event["stream_kind"],
            "stream_version": event["stream_version"],
        },
    )


def _internal_bundle(bundle: ExportBundle) -> dict[str, Any]:
    if bundle.vectors_included:
        raise CoreOperationError("CAPABILITY_DISABLED")
    events: list[dict[str, Any]] = []
    for public in bundle.events:
        envelope = public.payload
        if set(envelope) != _PUBLIC_ENVELOPE_KEYS:
            raise CoreOperationError("IMPORT_INVALID")
        data = envelope.get("data")
        if not isinstance(data, Mapping):
            raise CoreOperationError("IMPORT_INVALID")
        _reject_raw_paths(data)
        event = {
            "event_id": public.event_id,
            "workspace_id": bundle.workspace_id,
            "stream_id": envelope["stream_id"],
            "stream_kind": envelope["stream_kind"],
            "stream_version": envelope["stream_version"],
            "event_type": public.event_type,
            "event_schema_version": envelope["event_schema_version"],
            "occurred_at_us": _us_from_datetime(public.happened_at),
            "recorded_at_us": envelope["recorded_at_us"],
            "actor_type": envelope["actor_type"],
            "actor_id": envelope["actor_id"],
            "causation_event_id": envelope["causation_event_id"],
            "correlation_id": envelope["correlation_id"],
            "payload": dict(data),
            "payload_hash": sha256_json(data),
            "previous_event_hash": envelope["previous_event_hash"],
            "event_hash": public.content_hash,
        }
        expected_record_id = (
            event["stream_id"] if event["stream_kind"] == "memory" else None
        )
        if public.record_id != expected_record_id:
            raise CoreOperationError("IMPORT_INVALID")
        events.append(event)
    internal = {
        "workspace_id": bundle.workspace_id,
        "event_schema_version": 1,
        "events": events,
        "root_hash": bundle.root_hash,
    }
    _validate_bundle(internal, bundle.workspace_id)
    return internal


def _cursor_for(
    secret: bytes,
    workspace_id: str,
    record_id: str,
    event_id: str,
    event_hash: str,
) -> str:
    binding = hmac.new(
        secret,
        canonical_json_bytes(
            [
                "v7-memory-version-cursor",
                workspace_id,
                record_id,
                event_id,
                event_hash,
            ]
        ),
        hashlib.sha256,
    ).hexdigest()
    return f"cur_{binding}"


def _cursor_event(
    connection: sqlite3.Connection,
    secret: bytes,
    workspace_id: str,
    record_id: str,
    cursor: str,
) -> dict[str, Any]:
    match = _CURSOR_RE.fullmatch(cursor)
    if match is None:
        raise CoreOperationError("INVALID_ARGUMENT")
    rows = connection.execute(
        f"SELECT {_EVENT_COLUMNS} FROM memory_events "
        "WHERE workspace_id=? AND stream_id=? AND stream_kind='memory' "
        "ORDER BY stream_version ASC",
        (workspace_id, record_id),
    ).fetchall()
    for row in rows:
        event = _row_event(row)
        _verify_event(event, workspace_id)
        expected = _cursor_for(
            secret,
            workspace_id,
            record_id,
            str(event["event_id"]),
            str(event["event_hash"]),
        )
        if hmac.compare_digest(cursor, expected):
            return event
    raise CoreOperationError("INVALID_ARGUMENT")


def _record_from_event(event: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = event.get("payload")
    record = payload.get("record") if isinstance(payload, Mapping) else None
    if not isinstance(record, Mapping):
        raise CoreOperationError("IMPORT_INVALID")
    if record.get("record_type") == "legacy":
        raise CoreOperationError("CAPABILITY_DEGRADED")
    _reject_raw_paths(record)
    return record


def _version_id(event: Mapping[str, Any]) -> str:
    return "ver_" + sha256_json(
        [
            "v7-memory-version",
            event["workspace_id"],
            event["stream_id"],
            event["event_id"],
            event["stream_version"],
            event["event_hash"],
        ]
    )


def _summary(
    event: Mapping[str, Any],
    *,
    created_at_us: int,
    superseded: bool,
) -> RecordSummary:
    record = _record_from_event(event)
    content = record.get("content")
    tags = record.get("tags", [])
    relative = record.get("file_path_relative")
    if not isinstance(content, str) or not content or not isinstance(tags, list):
        raise CoreOperationError("IMPORT_INVALID")
    if record.get("deleted_at_us") is not None:
        status = "invalidated"
    elif record.get("archived") is True:
        status = "archived"
    elif superseded:
        status = "superseded"
    else:
        status = "current"
    try:
        return RecordSummary(
            record_id=event["stream_id"],
            record_type=record["record_type"],
            excerpt=content[:4000],
            tags=tags,
            relative_file_path=relative,
            current_status=status,
            content_hash=memory_content_hash(record),
            created_at=_utc_from_us(created_at_us),
            updated_at=_utc_from_us(event["recorded_at_us"]),
        )
    except CoreOperationError:
        raise
    except Exception as exc:
        raise CoreOperationError("IMPORT_INVALID") from exc


def _first_occurred_at(
    connection: sqlite3.Connection,
    workspace_id: str,
    record_id: str,
) -> int:
    row = connection.execute(
        "SELECT occurred_at_us FROM memory_events WHERE workspace_id=? "
        "AND stream_id=? AND stream_kind='memory' AND stream_version=1",
        (workspace_id, record_id),
    ).fetchone()
    if row is None or type(row[0]) is not int:
        raise CoreOperationError("NOT_FOUND")
    return row[0]


def _versions_sync(
    dependencies: CoreOperationDependencies,
    workspace: Workspace,
    request: AdmittedRequest,
) -> Page[MemoryVersionView]:
    with _active_connection(dependencies, workspace) as connection:
        created_at_us = _first_occurred_at(
            connection, workspace.workspace_id, request.record_id
        )
        start_version = 0
        previous_hash: str | None = None
        if request.cursor is not None:
            cursor_event = _cursor_event(
                connection,
                dependencies.cursor_secret,
                workspace.workspace_id,
                request.record_id,
                request.cursor,
            )
            start_version = int(cursor_event["stream_version"])
            previous_hash = str(cursor_event["event_hash"])
        rows = connection.execute(
            f"SELECT {_EVENT_COLUMNS} FROM memory_events "
            "WHERE workspace_id=? AND stream_id=? AND stream_kind='memory' "
            "AND stream_version>? ORDER BY stream_version ASC LIMIT ?",
            (
                workspace.workspace_id,
                request.record_id,
                start_version,
                request.limit + 1,
            ),
        ).fetchall()
        events = [_row_event(row) for row in rows]
        expected_version = start_version + 1
        for event in events:
            if event["stream_version"] != expected_version:
                raise CoreOperationError("IMPORT_INVALID")
            _verify_event(
                event,
                workspace.workspace_id,
                expected_previous_hash=previous_hash,
            )
            previous_hash = str(event["event_hash"])
            expected_version += 1
        truncated = len(events) > request.limit
        selected = events[: request.limit]
        items: list[MemoryVersionView] = []
        for index, event in enumerate(selected):
            next_event = events[index + 1] if index + 1 < len(events) else None
            valid_to = None
            if next_event is not None:
                if next_event["occurred_at_us"] <= event["occurred_at_us"]:
                    raise CoreOperationError("IMPORT_INVALID")
                valid_to = _utc_from_us(next_event["occurred_at_us"])
            items.append(
                MemoryVersionView(
                    version_id=_version_id(event),
                    record=_summary(
                        event,
                        created_at_us=created_at_us,
                        superseded=next_event is not None,
                    ),
                    event_id=event["event_id"],
                    valid_from=_utc_from_us(event["occurred_at_us"]),
                    valid_to=valid_to,
                    transaction_time=_utc_from_us(event["recorded_at_us"]),
                )
            )
        next_cursor = None
        if truncated and selected:
            final = selected[-1]
            next_cursor = _cursor_for(
                dependencies.cursor_secret,
                workspace.workspace_id,
                request.record_id,
                str(final["event_id"]),
                str(final["event_hash"]),
            )
        return Page[MemoryVersionView](
            items=items,
            next_cursor=next_cursor,
            truncated=truncated,
        )


def _at_time_sync(
    dependencies: CoreOperationDependencies,
    workspace: Workspace,
    request: AdmittedRequest,
) -> MemoryAtTimeData:
    with _active_connection(dependencies, workspace) as connection:
        created_at_us = _first_occurred_at(
            connection, workspace.workspace_id, request.record_id
        )
        valid_at = _us_from_datetime(request.valid_time)
        transaction_time = request.transaction_time or dependencies.clock()
        transaction_at = _us_from_datetime(transaction_time)
        rows = connection.execute(
            f"SELECT {_EVENT_COLUMNS} FROM memory_events "
            "WHERE workspace_id=? AND stream_id=? AND stream_kind='memory' "
            "AND occurred_at_us<=? AND recorded_at_us<=? "
            "ORDER BY occurred_at_us DESC,stream_version DESC LIMIT 1",
            (
                workspace.workspace_id,
                request.record_id,
                valid_at,
                transaction_at,
            ),
        ).fetchall()
        if not rows:
            raise CoreOperationError("NOT_FOUND")
        event = _row_event(rows[0])
        _verify_event(event, workspace.workspace_id)
        version_id = _version_id(event)
        summary = _summary(event, created_at_us=created_at_us, superseded=False)
        evidence = EvidenceRef(
            record_id=request.record_id,
            event_id=event["event_id"],
            content_hash=summary.content_hash,
            version_id=version_id,
            relation_path=[],
            provider="temporal",
        )
        return MemoryAtTimeData(
            record=summary,
            version_id=version_id,
            evidence_refs=[evidence],
        )


def _manifest_from_row(row: sqlite3.Row | None) -> ProjectionManifest | None:
    if row is None:
        return None
    built_at = row[3] if row[3] is not None else row[4]
    if built_at is None:
        raise CoreOperationError("CAPABILITY_DEGRADED")
    try:
        return ProjectionManifest(
            projection=row[0],
            generation=row[1],
            source_root_hash=row[2],
            built_at=_utc_from_us(built_at),
        )
    except CoreOperationError:
        raise
    except Exception as exc:
        raise CoreOperationError("CAPABILITY_DEGRADED") from exc


def _active_manifest(
    connection: sqlite3.Connection,
    workspace_id: str,
    projection: str,
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT projection_name,generation,source_event_root_hash,"
        "activated_at_us,completed_at_us,row_count,source_event_count "
        "FROM projection_manifests WHERE workspace_id=? AND projection_name=? "
        "AND status='active' LIMIT 1",
        (workspace_id, projection),
    ).fetchone()


def _projection_sync(
    dependencies: CoreOperationDependencies,
    workspace: Workspace,
    request: AdmittedRequest,
    cancelled: threading.Event,
) -> ProjectionRebuildData:
    _raise_if_cancelled(cancelled)
    with _active_connection(dependencies, workspace) as connection:
        _raise_if_cancelled(cancelled)
        previous_row = _active_manifest(
            connection, workspace.workspace_id, request.projection
        )
        try:
            from ...retrieval.runtime import create_projection_builders

            builders = create_projection_builders(
                connection,
                connection.execute("PRAGMA database_list").fetchone()[2],
                config=dependencies.projection_config,
                include_optional=request.projection != "lexical",
            )
            if previous_row is not None and not request.force:
                preview = rebuild_projection(
                    connection,
                    workspace_id=workspace.workspace_id,
                    projection=request.projection,
                    dry_run=True,
                    builders=builders,
                )
                if (
                    preview.get("capability_status") == "ready"
                    and previous_row[2] == preview.get("source_event_root_hash")
                    and previous_row[5] == preview.get("row_count")
                    and previous_row[6] == preview.get("source_event_count")
                ):
                    current = _manifest_from_row(previous_row)
                    if current is None:
                        raise CoreOperationError("CAPABILITY_DEGRADED")
                    _raise_if_cancelled(cancelled)
                    return ProjectionRebuildData(
                        manifest=current,
                        previous_manifest=None,
                        counts={
                            "rows": int(preview["row_count"]),
                            "source_events": int(preview["source_event_count"]),
                            "previous_rows": int(previous_row[5]),
                        },
                        diagnostics=[
                            DiagnosticSummary(
                                code="PROJECTION_CURRENT",
                                message=(
                                    "The active projection already matches the "
                                    "canonical event snapshot."
                                ),
                            )
                        ],
                    )
            _raise_if_cancelled(cancelled)
            result = rebuild_projection(
                connection,
                workspace_id=workspace.workspace_id,
                projection=request.projection,
                dry_run=False,
                builders=builders,
            )
        except ProjectionOperationError as exc:
            if exc.code == "PROJECTION_BUILDER_UNAVAILABLE":
                raise CoreOperationError("CAPABILITY_DISABLED") from exc
            if exc.code in {"LEXICAL_UNAVAILABLE", "FTS5_UNAVAILABLE"}:
                raise CoreOperationError("LEXICAL_UNAVAILABLE") from exc
            raise CoreOperationError("CAPABILITY_DEGRADED") from exc
        except CoreOperationError:
            raise
        except Exception as exc:
            raise CoreOperationError("CAPABILITY_DEGRADED") from exc
        active_row = _active_manifest(
            connection, workspace.workspace_id, request.projection
        )
        manifest = _manifest_from_row(active_row)
        if manifest is None:
            raise CoreOperationError("CAPABILITY_DEGRADED")
        previous = _manifest_from_row(previous_row)
        diagnostics: list[DiagnosticSummary] = []
        if result.get("capability_status") != "ready":
            diagnostics.append(
                DiagnosticSummary(
                    code="PROJECTION_DEGRADED",
                    message="The projection provider reported a degraded build.",
                )
            )
        return ProjectionRebuildData(
            manifest=manifest,
            previous_manifest=previous,
            counts={
                "rows": int(result["row_count"]),
                "source_events": int(result["source_event_count"]),
                "previous_rows": int(result.get("active_row_count", 0)),
            },
            diagnostics=diagnostics,
        )


def _export_sync(
    dependencies: CoreOperationDependencies,
    workspace: Workspace,
    request: AdmittedRequest,
) -> ExportBundle:
    if request.include_vectors:
        raise CoreOperationError("CAPABILITY_DISABLED")
    with _active_connection(dependencies, workspace) as connection:
        try:
            internal = export_event_bundle(connection, workspace.workspace_id)
        except EventBundleError as exc:
            raise CoreOperationError("IMPORT_INVALID") from exc
        _validate_bundle(internal, workspace.workspace_id)
        try:
            return ExportBundle(
                workspace_id=workspace.workspace_id,
                exported_at=dependencies.clock(),
                root_hash=internal["root_hash"],
                events=[_public_event(event) for event in internal["events"]],
                legacy_projection_included=request.include_legacy_projection,
                vectors_included=False,
            )
        except CoreOperationError:
            raise
        except Exception as exc:
            raise CoreOperationError("IMPORT_INVALID") from exc


def _journal_payload(bundle: ExportBundle, merge: bool) -> dict[str, Any]:
    return {
        "api_version": "7",
        "bundle_hash": sha256_json(bundle.model_dump(mode="json")),
        "event_count": len(bundle.events),
        "merge": merge,
        "root_hash": bundle.root_hash,
    }


def _import_sync(
    dependencies: CoreOperationDependencies,
    workspace: Workspace,
    request: AdmittedRequest,
    cancelled: threading.Event,
) -> WorkspaceImportData:
    _raise_if_cancelled(cancelled)
    try:
        bundle = ExportBundle.model_validate(request.bundle)
    except Exception as exc:
        raise CoreOperationError("IMPORT_INVALID") from exc
    if bundle.workspace_id != workspace.workspace_id:
        raise CoreOperationError("CROSS_WORKSPACE_IMPORT_UNSUPPORTED")
    internal = _internal_bundle(bundle)
    payload = _journal_payload(bundle, request.merge)
    payload_text = canonical_json_bytes(payload).decode("utf-8")
    payload_hash = sha256_json(payload)
    event_ids = [event.event_id for event in bundle.events]
    with _active_connection(dependencies, workspace) as connection:
        try:
            _raise_if_cancelled(cancelled)
            connection.execute("BEGIN IMMEDIATE")
            _raise_if_cancelled(cancelled)
            existing = connection.execute(
                "SELECT job_id,payload_json,payload_hash,status FROM background_jobs "
                "WHERE workspace_id=? AND job_type='v7.workspace_import' "
                "AND idempotency_key=?",
                (workspace.workspace_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                expected_job_id = deterministic_id(
                    "job",
                    "v7.workspace_import",
                    workspace.workspace_id,
                    request.idempotency_key,
                )
                if (
                    existing[0] != expected_job_id
                    or existing[1] != payload_text
                    or existing[2] != payload_hash
                    or existing[3] != "succeeded"
                ):
                    raise CoreOperationError("IDEMPOTENCY_CONFLICT")
                _raise_if_cancelled(cancelled)
                connection.commit()
                return WorkspaceImportData(
                    root_hash=bundle.root_hash,
                    imported=0,
                    skipped=len(event_ids),
                    event_ids=event_ids,
                )
            if not request.merge:
                occupied = connection.execute(
                    "SELECT 1 FROM memory_events WHERE workspace_id=? LIMIT 1",
                    (workspace.workspace_id,),
                ).fetchone()
                if occupied is not None:
                    raise CoreOperationError("CONFLICT")
            _raise_if_cancelled(cancelled)
            try:
                result = import_event_bundle(
                    connection,
                    internal,
                    workspace.workspace_id,
                    assume_transaction=True,
                )
            except EventBundleError as exc:
                if exc.code == "CROSS_WORKSPACE_IMPORT_UNSUPPORTED":
                    raise CoreOperationError(
                        "CROSS_WORKSPACE_IMPORT_UNSUPPORTED"
                    ) from exc
                raise CoreOperationError("IMPORT_INVALID") from exc
            except EventStreamConflict as exc:
                raise CoreOperationError("EVENT_STREAM_CONFLICT") from exc
            _raise_if_cancelled(cancelled)
            now = dependencies.clock()
            now_us = _us_from_datetime(now)
            result_payload = {
                "event_ids": event_ids,
                "imported": result.events_imported,
                "root_hash": result.root_hash,
                "skipped": result.events_existing,
            }
            connection.execute(
                "INSERT INTO background_jobs ("
                "job_id,workspace_id,job_type,idempotency_key,payload_json,"
                "payload_hash,status,priority,attempts,max_attempts,available_at_us,"
                "lease_owner,lease_token,lease_expires_at_us,cancel_requested_at_us,"
                "last_error_json,result_json,source_event_id,created_at_us,updated_at_us,"
                "started_at_us,finished_at_us) VALUES (?,?,?,?,?,?,'succeeded',0,1,1,"
                "?,NULL,NULL,NULL,NULL,NULL,?,NULL,?,?,?,?)",
                (
                    deterministic_id(
                        "job",
                        "v7.workspace_import",
                        workspace.workspace_id,
                        request.idempotency_key,
                    ),
                    workspace.workspace_id,
                    "v7.workspace_import",
                    request.idempotency_key,
                    payload_text,
                    payload_hash,
                    now_us,
                    canonical_json_bytes(result_payload).decode("utf-8"),
                    now_us,
                    now_us,
                    now_us,
                    now_us,
                ),
            )
            _raise_if_cancelled(cancelled)
            connection.commit()
            return WorkspaceImportData(
                root_hash=result.root_hash,
                imported=result.events_imported,
                skipped=result.events_existing,
                event_ids=event_ids,
            )
        except CoreOperationError:
            connection.rollback()
            raise
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise CoreOperationError("IDEMPOTENCY_CONFLICT") from exc
        except sqlite3.Error as exc:
            connection.rollback()
            raise CoreOperationError("IMPORT_INVALID") from exc
        except Exception:
            connection.rollback()
            raise


def _covenant_status(
    dependencies: CoreOperationDependencies,
    workspace: Workspace,
    request: AdmittedRequest,
) -> CovenantStatusData:
    _authorize_workspace(workspace, request)
    scope = dependencies.scope_provider()
    briefed = False
    briefed_at: datetime | None = None
    if (
        isinstance(scope, InvocationScope)
        and scope.canonical_workspace == _canonical_root(workspace)
    ):
        try:
            status = dependencies.covenant_gate.state_store.status(scope)
            raw_briefed_at = status.get("briefed_at")
            briefed = status.get("briefed") is True
            if briefed and type(raw_briefed_at) is int:
                briefed_at = datetime.fromtimestamp(
                    raw_briefed_at,
                    tz=timezone.utc,
                )
            elif briefed:
                briefed = False
        except Exception:
            briefed = False
            briefed_at = None
    ttl = dependencies.covenant_gate.authority.ttl_seconds
    if isinstance(ttl, bool) or not isinstance(ttl, int) or not 1 <= ttl <= 3600:
        raise CoreOperationError("CAPABILITY_DEGRADED")
    next_step = None
    if not briefed:
        next_step = CovenantNextStep(
            tool="session_brief",
            reason="Start the scoped Covenant session before protected work.",
        )
    return CovenantStatusData(
        briefed=briefed,
        briefed_at=briefed_at,
        token_ttl_seconds=ttl,
        next_step=next_step,
    )


def build_core_operations(
    dependencies: CoreOperationDependencies,
) -> Mapping[str, Callable[..., Any]]:
    """Return the exact immutable canonical-operation adapter registry."""

    if not isinstance(dependencies, CoreOperationDependencies):
        raise TypeError("dependencies must be CoreOperationDependencies")

    async def covenant_status(
        *, workspace: Workspace, request: AdmittedRequest
    ) -> CovenantStatusData:
        return _covenant_status(dependencies, workspace, request)

    async def memory_versions_list(
        *, workspace: Workspace, request: AdmittedRequest
    ) -> Page[MemoryVersionView]:
        _authorize_workspace(workspace, request)
        return await _run_blocking(
            lambda: _versions_sync(dependencies, workspace, request)
        )

    async def memory_at_time_get(
        *, workspace: Workspace, request: AdmittedRequest
    ) -> MemoryAtTimeData:
        _authorize_workspace(workspace, request)
        return await _run_blocking(
            lambda: _at_time_sync(dependencies, workspace, request)
        )

    async def projection_rebuild(
        *, workspace: Workspace, request: AdmittedRequest
    ) -> ProjectionRebuildData:
        _authorize_workspace(workspace, request)
        return await _run_mutation(
            lambda cancelled: _projection_sync(
                dependencies,
                workspace,
                request,
                cancelled,
            )
        )

    async def workspace_export(
        *, workspace: Workspace, request: AdmittedRequest
    ) -> ExportBundle:
        _authorize_workspace(workspace, request)
        return await _run_blocking(
            lambda: _export_sync(dependencies, workspace, request)
        )

    async def workspace_import(
        *, workspace: Workspace, request: AdmittedRequest
    ) -> WorkspaceImportData:
        _authorize_workspace(workspace, request)
        return await _run_mutation(
            lambda cancelled: _import_sync(
                dependencies,
                workspace,
                request,
                cancelled,
            )
        )

    return MappingProxyType(
        {
            "covenant_status": covenant_status,
            "memory_at_time_get": memory_at_time_get,
            "memory_versions_list": memory_versions_list,
            "projection_rebuild": projection_rebuild,
            "workspace_export": workspace_export,
            "workspace_import": workspace_import,
        }
    )


__all__ = [
    "CoreOperationDependencies",
    "CoreOperationError",
    "build_core_operations",
]
