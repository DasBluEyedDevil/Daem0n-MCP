"""Production composition root for the exact Daem0nMCP v7 surface."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import re
import secrets
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Literal

from ...capabilities import CapabilityRegistry
from ...config import Settings
from ...covenant import (
    CovenantGate,
    CovenantStateStore,
    authority_from_environment,
    invocation_scope_var,
)
from ...storage_activation import resolve_active_database
from ...transport_security import (
    build_fastmcp_auth,
    validate_transport_security,
)
from ...workspace import Workspace, WorkspaceRegistry
from .code_entity_operations import (
    CodeEntityOperationDependencies,
    build_code_entity_operations,
)
from .composition import V7Surface, build_v7_surface
from .discovery_operations import (
    DiscoveryOperationDependencies,
    build_discovery_operations,
)
from .federation_operations import (
    FederationOperationDependencies,
    build_federation_operations,
)
from .intelligence_operations import (
    IntelligenceOperationDependencies,
    build_intelligence_operations,
)
from .local_state_operations import (
    LocalStateOperationDependencies,
    build_local_state_operations,
)
from .maintenance_operations import (
    MaintenanceOperationDependencies,
    build_maintenance_operations,
)
from .models import CapabilityState
from .opaque_capabilities import OpaqueCapabilityAuthority
from .operations import CoreOperationDependencies, build_core_operations
from .pinned import PinnedDependencies
from .policy import V7_COVENANT_POLICY
from .record_operations import (
    RecordOperationDependencies,
    build_record_operations,
)
from .relationship_operations import (
    RelationshipOperationDependencies,
    build_relationship_operations,
)
from .resource_repository import (
    ResourceRepositoryReaders,
    build_sqlite_resource_readers,
)
from .resources import ResourceReadRequest, ResourceRow
from .responses import ResponseFactory
from .rule_trigger_operations import (
    RuleTriggerOperationDependencies,
    build_rule_trigger_operations,
)
from .runtime_services import (
    BasicBriefingService,
    BasicHealthService,
    BasicPreflightService,
    SQLiteMemoryEventWriter,
    Task8RecallService,
    WorkspaceStorageResolver,
    resolve_workspace_storage,
)
from .tools import build_argument_normalizer
from .utility_operations import (
    UtilityOperationDependencies,
    build_utility_operations,
)


TransportMode = Literal["stdio", "streamable-http"]


class ProductionConfigurationError(RuntimeError):
    """Path-free failure raised before a partially configured server exists."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _ProductionAssembly:
    surface: V7Surface
    auth: object | None
    tasks_enabled: bool
    services: tuple[object, ...]


def _runtime_lifespan(services: tuple[object, ...]):
    """Own and deterministically close per-server runtime services."""

    @asynccontextmanager
    async def lifespan(_server: object):
        try:
            yield {}
        finally:
            for service in reversed(services):
                close = getattr(service, "close", None)
                if callable(close):
                    close()

    return lifespan


def _loopback_host(host: str) -> bool:
    normalized = host.strip()
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    if normalized.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _task_configuration() -> tuple[bool, CapabilityState]:
    # FastMCP 3.0.0b2 queues raw arguments before a tool adapter or middleware
    # can consume the one-use Covenant capability and replace it with a
    # sanitized admission descriptor.  Enabling Docket would persist bearer
    # handles and lose invocation ContextVars in the worker.  Keep this
    # optional profile explicitly disabled until a reviewed acceptance hook is
    # available; build_fastmcp_server independently enforces the same boundary.
    return False, CapabilityState(
        name="tasks",
        status="disabled",
        reason_code="TASKS_UNAVAILABLE",
        remediation="Use the bounded foreground profile for reviewed operations.",
    )


def _capability_states(
    environ: Mapping[str, str],
) -> tuple[CapabilityState, ...]:
    values: list[CapabilityState] = []
    for name, capability in CapabilityRegistry(environ=environ).all().items():
        status = str(capability["status"])
        if status == "ready":
            values.append(CapabilityState(name=name, status="ready"))
            continue
        reason = {
            "disabled": "CAPABILITY_DISABLED",
            "degraded": "CAPABILITY_DEGRADED",
            "failed": "CAPABILITY_CONFIGURATION_INVALID",
        }[status]
        values.append(
            CapabilityState(
                name=name,
                status=status,
                reason_code=reason,
                remediation=f"Review the {name} capability profile.",
            )
        )
    return tuple(values)


def _active_database(workspace: Workspace):
    storage = resolve_workspace_storage(workspace)
    active = resolve_active_database(storage)
    if active.format_version != 7:
        raise ProductionConfigurationError("ACTIVE_V7_UNAVAILABLE")
    return active


def _public_items(rows: object) -> list[object]:
    if not isinstance(rows, list):
        raise TypeError("resource reader returned an invalid result")
    values: list[object] = []
    for row in rows:
        if isinstance(row, ResourceRow):
            if not row.deleted:
                values.append(row.item)
        else:
            values.append(row)
    return values


def _merge_operations(
    *operation_maps: Mapping[str, Any],
) -> Mapping[str, Any]:
    merged: dict[str, Any] = {}
    for operations in operation_maps:
        overlap = set(merged) & set(operations)
        if overlap:
            raise ProductionConfigurationError("DUPLICATE_OPERATION")
        merged.update(operations)
    return MappingProxyType(merged)


_RELEVANCE_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{1,79}")


def _relevance_tokens(*values: object) -> frozenset[str]:
    encoded = json.dumps(
        values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).casefold()
    tokens: set[str] = set()
    for value in _RELEVANCE_TOKEN.findall(encoded):
        tokens.add(value)
        tokens.update(
            component
            for component in value.replace("-", "_").split("_")
            if len(component) >= 2
        )
    return frozenset(tokens)


def _rank_relevant(
    values: list[object],
    query_tokens: frozenset[str],
    *,
    limit: int,
) -> list[object]:
    if not query_tokens:
        return values[:limit]
    ranked: list[tuple[int, int, object]] = []
    for index, value in enumerate(values):
        if hasattr(value, "record_type") and hasattr(value, "excerpt"):
            searchable = {
                "record_type": value.record_type,
                "excerpt": value.excerpt,
                "tags": value.tags,
                "relative_file_path": value.relative_file_path,
            }
        elif hasattr(value, "trigger") and hasattr(value, "must_do"):
            searchable = {
                "trigger": value.trigger,
                "must_do": value.must_do,
                "must_not": value.must_not,
                "ask_first": value.ask_first,
                "warnings": value.warnings,
            }
        elif hasattr(value, "model_dump"):
            searchable = value.model_dump(mode="json")
        else:
            searchable = value
        score = len(query_tokens & _relevance_tokens(searchable))
        if score:
            ranked.append((-score, index, value))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked[:limit]]


def _unique_text(values: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
        if len(result) == limit:
            break
    return result


def _briefing_reader(readers: ResourceRepositoryReaders):
    async def read(workspace: Workspace, request: object) -> dict[str, object]:
        warning_limit = int(getattr(request, "warning_limit"))
        failure_limit = int(getattr(request, "failure_limit"))
        focus_areas = list(getattr(request, "focus_areas", ()))
        focus_tokens = _relevance_tokens(focus_areas)
        snapshot_reader = readers.briefing_snapshot_reader
        if snapshot_reader is not None:
            snapshot = await snapshot_reader(
                workspace,
                warning_limit=warning_limit,
                failure_limit=failure_limit,
                rule_limit=50,
                active_context_limit=50,
            )
            warnings = _public_items(snapshot.warnings)
            failures = _public_items(snapshot.failures)
            rules = _public_items(snapshot.rules)
            active_context = _public_items(snapshot.active_context)
            decisions = _rank_relevant(
                _public_items(snapshot.decisions),
                focus_tokens,
                limit=50,
            )
            git_changes = list(snapshot.git_changes)[:200]
            projection_freshness = list(snapshot.projection_freshness)[:7]
            statistics = dict(snapshot.workspace_statistics)
            stale_projection_count = snapshot.stale_projection_count
        else:
            warnings = []
            if warning_limit:
                warnings = _public_items(
                    await readers.warning_reader(
                        workspace,
                        ResourceReadRequest(
                            "warnings", warning_limit, "updated_at_desc"
                        ),
                    )
                )
            failures = []
            if failure_limit:
                failures = _public_items(
                    await readers.failure_reader(
                        workspace,
                        ResourceReadRequest(
                            "failures", failure_limit, "updated_at_desc"
                        ),
                    )
                )
            rules = _public_items(
                await readers.rule_reader(
                    workspace,
                    ResourceReadRequest(
                        "rules", 50, "priority_desc", enabled_only=True
                    ),
                )
            )
            active_context = _public_items(
                await readers.active_context_reader(
                    workspace,
                    ResourceReadRequest(
                        "active_context", 50, "priority_desc"
                    ),
                )
            )
            decisions = []
            git_changes = []
            projection_freshness = []
            statistics = {
                "warnings": len(warnings),
                "failed_outcomes": len(failures),
                "rules": len(rules),
                "active_context": len(active_context),
            }
            stale_projection_count = 0
        failed_outcomes = [
            {
                "record_id": item.record_id,
                "outcome_excerpt": item.excerpt,
                "worked": False,
                "happened_at": item.updated_at,
            }
            for item in failures
        ]
        next_steps: list[dict[str, str]] = []
        if warnings or failures or rules:
            next_steps.append(
                {
                    "tool": "memory_preflight",
                    "reason": (
                        "Review bound warnings, failed approaches, and rules "
                        "before a protected operation."
                    ),
                }
            )
        if focus_areas:
            next_steps.append(
                {
                    "tool": "memory_recall",
                    "reason": "Retrieve evidence for the requested focus areas.",
                }
            )
        if stale_projection_count:
            next_steps.append(
                {
                    "tool": "projection_rebuild",
                    "reason": "One or more retrieval projections require rebuilding.",
                }
            )
        if not next_steps:
            next_steps.append(
                {
                    "tool": "memory_recall",
                    "reason": "Retrieve task-specific evidence before acting.",
                }
            )
        return {
            "workspace_id": workspace.workspace_id,
            "briefed_at": datetime.now(timezone.utc),
            "workspace_statistics": statistics,
            "recent_decisions": decisions,
            "warnings": warnings,
            "failed_outcomes": failed_outcomes,
            "applicable_rules": rules,
            "active_context": active_context,
            "git_changes": git_changes,
            "projection_freshness": projection_freshness,
            "covenant_next_steps": next_steps,
        }

    return read


def _guidance_reader(readers: ResourceRepositoryReaders):
    async def read(
        workspace: Workspace,
        target_tool: str,
        normalized_arguments: Mapping[str, Any],
        description: str | None,
    ) -> dict[str, object]:
        query_tokens = _relevance_tokens(
            target_tool,
            normalized_arguments,
            description,
        )
        snapshot_reader = readers.briefing_snapshot_reader
        if snapshot_reader is not None:
            snapshot = await snapshot_reader(
                workspace,
                warning_limit=20,
                failure_limit=20,
                rule_limit=50,
                active_context_limit=1,
            )
            candidate_records = [
                *_public_items(snapshot.failures),
                *_public_items(snapshot.warnings),
            ]
            candidate_rules = _public_items(snapshot.rules)
        else:
            warnings = _public_items(
                await readers.warning_reader(
                    workspace,
                    ResourceReadRequest("warnings", 20, "updated_at_desc"),
                )
            )
            failures = _public_items(
                await readers.failure_reader(
                    workspace,
                    ResourceReadRequest("failures", 20, "updated_at_desc"),
                )
            )
            candidate_records = [*failures, *warnings]
            candidate_rules = _public_items(
                await readers.rule_reader(
                    workspace,
                    ResourceReadRequest(
                        "rules", 20, "priority_desc", enabled_only=True
                    ),
                )
            )
        records = _rank_relevant(
            candidate_records,
            query_tokens,
            limit=20,
        )
        rules = _rank_relevant(
            candidate_rules,
            query_tokens,
            limit=20,
        )
        return {
            "records": records,
            "rules": rules,
            "must_do": _unique_text(
                [value for rule in rules for value in rule.must_do],
                limit=50,
            ),
            "must_not": _unique_text(
                [value for rule in rules for value in rule.must_not],
                limit=50,
            ),
            "ask_first": _unique_text(
                [value for rule in rules for value in rule.ask_first],
                limit=50,
            ),
            "warnings": _unique_text(
                [
                    *[value for rule in rules for value in rule.warnings],
                    *[
                        record.excerpt
                        for record in records
                        if record.record_type == "warning"
                    ],
                ],
                limit=50,
            ),
        }

    return read


def _assemble(
    transport_mode: str,
    *,
    host: str | None,
    settings: Settings | None,
    environ: Mapping[str, str] | None,
) -> _ProductionAssembly:
    if transport_mode not in {"stdio", "streamable-http"}:
        raise ValueError("v7 supports stdio or streamable-http")
    env = os.environ if environ is None else environ
    loaded_settings = settings or Settings()
    if not isinstance(loaded_settings, Settings):
        raise TypeError("settings must be Settings")

    auth: object | None = None
    loopback = False
    if transport_mode == "streamable-http":
        selected_host = host or "127.0.0.1"
        auth = build_fastmcp_auth(env)
        validate_transport_security(
            selected_host,
            auth_provider=auth,
            environ=env,
        )
        loopback = _loopback_host(selected_host)

    authority = authority_from_environment(
        local_stdio=transport_mode == "stdio" or loopback,
        environ=env,
    )
    if authority is None:
        raise ProductionConfigurationError(
            "CAPABILITY_AUTHORITY_UNAVAILABLE"
        )
    tasks_enabled, task_state = _task_configuration()
    normalizer = build_argument_normalizer()
    gate = CovenantGate(
        state_store=CovenantStateStore(),
        authority=OpaqueCapabilityAuthority(authority),
        policy=V7_COVENANT_POLICY,
        argument_normalizer=normalizer,
    )
    registry = WorkspaceRegistry.from_settings(loaded_settings)
    resource_readers = build_sqlite_resource_readers(_active_database)
    storage_resolver = WorkspaceStorageResolver()
    operation_secret = secrets.token_bytes(32)
    writer = SQLiteMemoryEventWriter(storage_resolver=storage_resolver)
    recall = Task8RecallService(storage_resolver=storage_resolver)
    discovery_dependencies = DiscoveryOperationDependencies(
        storage_resolver=storage_resolver,
        cursor_secret=operation_secret,
        recall_service=recall,
    )
    relationship_dependencies = RelationshipOperationDependencies(
        storage_resolver=storage_resolver,
    )
    utility_dependencies = UtilityOperationDependencies(
        cursor_secret=operation_secret,
    )
    maintenance_dependencies = MaintenanceOperationDependencies(
        storage_resolver=storage_resolver,
        selection_secret=operation_secret,
    )
    intelligence_dependencies = IntelligenceOperationDependencies(
        storage_resolver=storage_resolver,
    )
    code_entity_dependencies = CodeEntityOperationDependencies(
        operation_secret=operation_secret,
        storage_resolver=storage_resolver,
    )
    federation_dependencies = FederationOperationDependencies(
        workspace_resolver=registry,
        storage_resolver=storage_resolver,
        cursor_secret=operation_secret,
    )
    health = BasicHealthService(
        auth_mode=(
            "process"
            if transport_mode == "stdio"
            else "loopback"
            if auth is None
            else "jwt"
        ),
        task_support=task_state,
        capability_states=_capability_states(env),
    )
    pinned = PinnedDependencies(
        workspace_resolver=registry,
        covenant_gate=gate,
        argument_normalizer=normalizer,
        briefing_service=BasicBriefingService(
            reader=_briefing_reader(resource_readers)
        ),
        preflight_service=BasicPreflightService(
            reader=_guidance_reader(resource_readers)
        ),
        recall_service=recall,
        memory_event_writer=writer,
        health_service=health,
        response_factory=ResponseFactory(),
    )
    operations = _merge_operations(
        build_core_operations(
            CoreOperationDependencies(
                covenant_gate=gate,
                scope_provider=invocation_scope_var.get,
                storage_path_resolver=resolve_workspace_storage,
                projection_config=loaded_settings,
            )
        ),
        build_record_operations(
            RecordOperationDependencies(
                storage_resolver=storage_resolver,
                cursor_secret=operation_secret,
            )
        ),
        build_local_state_operations(
            LocalStateOperationDependencies(
                storage_resolver=storage_resolver,
                token_secret=operation_secret,
            )
        ),
        build_rule_trigger_operations(
            RuleTriggerOperationDependencies(
                storage_resolver=storage_resolver,
                recall_service=recall,
                cursor_secret=operation_secret,
            )
        ),
        build_discovery_operations(discovery_dependencies),
        build_relationship_operations(relationship_dependencies),
        build_utility_operations(utility_dependencies),
        build_maintenance_operations(maintenance_dependencies),
        build_intelligence_operations(intelligence_dependencies),
        build_code_entity_operations(code_entity_dependencies),
        build_federation_operations(federation_dependencies),
    )
    surface = build_v7_surface(
        pinned_dependencies=pinned,
        operations=operations,
        warning_reader=resource_readers.warning_reader,
        failure_reader=resource_readers.failure_reader,
        rule_reader=resource_readers.rule_reader,
        active_context_reader=resource_readers.active_context_reader,
        transport_mode=transport_mode,
        allow_unauthenticated_loopback=(
            transport_mode == "streamable-http" and auth is None
        ),
    )
    return _ProductionAssembly(
        surface=surface,
        auth=auth,
        tasks_enabled=tasks_enabled,
        services=(
            writer,
            recall,
            discovery_dependencies,
            relationship_dependencies,
            utility_dependencies,
            maintenance_dependencies,
            intelligence_dependencies,
            code_entity_dependencies,
            federation_dependencies,
        ),
    )


def build_production_surface(
    transport_mode: str,
    *,
    host: str | None = None,
    settings: Settings | None = None,
    environ: Mapping[str, str] | None = None,
) -> V7Surface:
    """Build the inspectable production surface without registering FastMCP."""

    return _assemble(
        transport_mode,
        host=host,
        settings=settings,
        environ=environ,
    ).surface


def create_v7_server(
    transport_mode: str,
    *,
    host: str | None = None,
    settings: Settings | None = None,
    environ: Mapping[str, str] | None = None,
) -> Any:
    """Create one fresh production FastMCP server from the v7 manifest."""

    assembly = _assemble(
        transport_mode,
        host=host,
        settings=settings,
        environ=environ,
    )
    server = assembly.surface.build_server(
        auth=assembly.auth,
        tasks_enabled=assembly.tasks_enabled,
        lifespan=_runtime_lifespan(assembly.services),
        sync_timeout_seconds=15,
    )
    try:
        setattr(server, "_daem0nmcp_v7_services", assembly.services)
    except (AttributeError, TypeError):
        pass
    return server


__all__ = [
    "ProductionConfigurationError",
    "build_production_surface",
    "create_v7_server",
]
