#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Build shell-side generation request policy from presentation state."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast

from substitute.application.generation import (
    GenerationRequest,
    WorkflowIssuePruningService,
)
from substitute.application.node_behavior import LiveNodeDefinitionError
from substitute.application.workflows import (
    CubeRuntimeIssueSource,
    WorkflowLinkReconciliationService,
    live_node_definition_error_to_cube_issues,
)

if TYPE_CHECKING:
    from substitute.application.node_behavior import EditorBehaviorSnapshot


@dataclass(frozen=True)
class GenerationWorkflowPruneReport:
    """Describe errored-cube omission performed for generation."""

    workflow_id: str
    workflow_name: str
    omitted_cube_aliases: tuple[str, ...]
    remaining_cube_count: int


class GenerationRequestInputMaskPreflight(Protocol):
    """Describe dirty Input mask persistence required before generation."""

    def flush_dirty_associated_masks_before_generation(self) -> bool:
        """Persist dirty associated Input masks before generation starts."""


class GenerationRequestWorkflowNameResolver(Protocol):
    """Describe workflow-name lookup required for generation metadata."""

    def resolve_workflow_name(self, workflow_id: str) -> str:
        """Resolve one workflow display name."""


class GenerationRequestBuildView(Protocol):
    """Describe shell collaborators required to build a generation request."""

    input_mask_save_controller: GenerationRequestInputMaskPreflight
    input_canvas_shell_adapter: GenerationRequestWorkflowNameResolver

    def get_active_workflow(self) -> object:
        """Return the active workflow state."""


def active_behavior_snapshot(
    view: object,
    workflow_id: str,
) -> "EditorBehaviorSnapshot | None":
    """Return the active workflow behavior snapshot when available."""

    panel = editor_panel_for_workflow(view, workflow_id)
    snapshot_getter = getattr(panel, "current_behavior_snapshot", None)
    if not callable(snapshot_getter):
        return None
    return cast("EditorBehaviorSnapshot | None", snapshot_getter())


def editor_panel_for_workflow(view: object, workflow_id: str) -> object | None:
    """Return the editor panel responsible for one workflow when available."""

    editor_panels = getattr(view, "editor_panels", None)
    if isinstance(editor_panels, Mapping):
        panel = editor_panels.get(workflow_id)
        if panel is not None:
            return cast(object, panel)
    return cast("object | None", getattr(view, "active_editor_panel", None))


def active_global_override_scopes(
    view: object,
    *,
    legacy_scope_logger: Callable[[str], None] | None = None,
) -> Mapping[str, object] | None:
    """Return active override serialization scopes from the shell manager."""

    manager = getattr(view, "active_override_manager", None)
    if manager is None:
        _log_legacy_scope(
            legacy_scope_logger,
            reason="missing_active_override_manager",
        )
        return None
    scope_getter = getattr(manager, "current_serialization_scopes", None)
    if not callable(scope_getter):
        _log_legacy_scope(legacy_scope_logger, reason="missing_scope_getter")
        return None
    scopes = scope_getter()
    if not isinstance(scopes, Mapping):
        return None
    return scopes


def errored_cube_aliases(view: object, workflow_id: str) -> tuple[str, ...]:
    """Return issue-state aliases that should be omitted from generation."""

    issue_state = getattr(view, "workflow_issue_state", None)
    issue_aliases = getattr(issue_state, "errored_aliases", None)
    if callable(issue_aliases):
        return cast("tuple[str, ...]", tuple(issue_aliases(workflow_id)))
    panel = editor_panel_for_workflow(view, workflow_id)
    panel_aliases = getattr(panel, "cube_runtime_error_aliases", None)
    if callable(panel_aliases):
        return cast("tuple[str, ...]", tuple(panel_aliases()))
    return ()


def workflow_issue_pruning_service(view: object) -> WorkflowIssuePruningService:
    """Build the workflow pruning service from shell-owned collaborators."""

    node_behavior_service = getattr(view, "node_behavior_service", None)
    link_reconciliation_service = (
        WorkflowLinkReconciliationService(
            prompt_endpoint_provider=node_behavior_service,
            node_link_endpoint_provider=node_behavior_service,
        )
        if node_behavior_service is not None
        else None
    )
    return WorkflowIssuePruningService(
        link_reconciliation_service=link_reconciliation_service
    )


def build_generation_request_for_view(
    *,
    view: GenerationRequestBuildView,
    workflow_id: str,
    reconcile_active_input_canvas_image: Callable[[], None],
    dirty_mask_error: Callable[[], Exception],
    live_node_preflight_error: Callable[[LiveNodeDefinitionError], Exception],
    empty_workflow_error: Callable[[], Exception],
    missing_panel_logger: Callable[[str], None] | None = None,
    omission_logger: Callable[[GenerationWorkflowPruneReport], None] | None = None,
    legacy_scope_logger: Callable[[str], None] | None = None,
) -> GenerationRequest:
    """Build a generation request from live shell presentation state."""

    dirty_masks_flushed = (
        view.input_mask_save_controller.flush_dirty_associated_masks_before_generation()
    )
    if not dirty_masks_flushed:
        raise dirty_mask_error()
    preflight_live_node_definitions(
        view=view,
        workflow_id=workflow_id,
        preflight_error=live_node_preflight_error,
        missing_panel_logger=missing_panel_logger,
    )
    reconcile_active_input_canvas_image()
    behavior_snapshot = active_behavior_snapshot(view, workflow_id)
    workflow = view.get_active_workflow()
    errored_aliases = errored_cube_aliases(view, workflow_id)
    workflow_name = view.input_canvas_shell_adapter.resolve_workflow_name(workflow_id)
    workflow_for_generation = workflow
    if errored_aliases:
        workflow_for_generation = pruned_workflow_for_generation(
            view=view,
            workflow=workflow,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            errored_aliases=errored_aliases,
            empty_workflow_error=empty_workflow_error,
            omission_logger=omission_logger,
        )
    return generation_request_from_workflow_state(
        view=view,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        workflow=workflow_for_generation,
        behavior_snapshot=behavior_snapshot,
        errored_aliases=errored_aliases,
        legacy_scope_logger=legacy_scope_logger,
    )


def generation_request_from_workflow_state(
    *,
    view: object,
    workflow_id: str,
    workflow_name: str,
    workflow: object,
    behavior_snapshot: "EditorBehaviorSnapshot | None",
    errored_aliases: tuple[str, ...],
    legacy_scope_logger: Callable[[str], None] | None = None,
) -> GenerationRequest:
    """Build a generation request from collected shell workflow state."""

    enabled_nodes, disabled_nodes = activation_node_keys_by_alias(
        behavior_snapshot,
        workflow,
    )
    pruner = workflow_issue_pruning_service(view)
    enabled_nodes = pruner.pruned_activation_overrides(
        enabled_nodes,
        errored_aliases=errored_aliases,
    )
    disabled_nodes = pruner.pruned_activation_overrides(
        disabled_nodes,
        errored_aliases=errored_aliases,
    )
    active_override_scopes = active_global_override_scopes(
        view,
        legacy_scope_logger=legacy_scope_logger,
    )
    global_override_scopes = pruner.pruned_global_override_scopes(
        active_override_scopes,
        errored_aliases=errored_aliases,
    )
    return GenerationRequest(
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        workflow=cast(Any, workflow),
        enabled_node_keys_by_alias=enabled_nodes,
        disabled_node_keys_by_alias=disabled_nodes,
        global_override_scopes=cast(Any, global_override_scopes),
    )


def pruned_workflow_for_generation(
    *,
    view: object,
    workflow: object,
    workflow_id: str,
    workflow_name: str,
    errored_aliases: tuple[str, ...],
    empty_workflow_error: Callable[[], Exception],
    omission_logger: Callable[[GenerationWorkflowPruneReport], None] | None = None,
) -> object:
    """Return a generation workflow snapshot with errored cubes omitted."""

    remaining_aliases = [
        alias
        for alias in workflow_stack_order(workflow)
        if alias not in set(errored_aliases)
    ]
    if not remaining_aliases:
        raise empty_workflow_error()

    pruned_workflow = workflow_issue_pruning_service(view).pruned_for_generation(
        workflow=cast(Any, workflow),
        errored_aliases=errored_aliases,
    )
    if omission_logger is not None:
        omission_logger(
            GenerationWorkflowPruneReport(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                omitted_cube_aliases=errored_aliases,
                remaining_cube_count=len(workflow_stack_order(pruned_workflow)),
            )
        )
    return pruned_workflow


def preflight_live_node_definitions(
    *,
    view: object,
    workflow_id: str,
    preflight_error: Callable[[LiveNodeDefinitionError], Exception],
    missing_panel_logger: Callable[[str], None] | None = None,
) -> None:
    """Hydrate required live node definitions immediately before generation."""

    panel = editor_panel_for_workflow(view, workflow_id)
    hydrate = getattr(panel, "hydrate_node_definitions_for_projection", None)
    if not callable(hydrate):
        if missing_panel_logger is not None:
            missing_panel_logger(workflow_id)
        return
    try:
        hydrate(reason="generation_preflight")
    except LiveNodeDefinitionError as error:
        register = getattr(
            panel,
            "register_projection_live_node_definition_error",
            None,
        )
        issues = live_node_definition_error_to_cube_issues(
            error,
            workflow_id=workflow_id,
            source=CubeRuntimeIssueSource.PROJECTION,
        )
        has_unowned_definition = any(
            not item.cube_aliases for item in error.missing_definitions
        )
        if (
            issues
            and not has_unowned_definition
            and not error.missing_fields
            and callable(register)
        ):
            register(
                error,
                reason="generation_preflight",
                source=CubeRuntimeIssueSource.PROJECTION,
            )
            return
        raise preflight_error(error) from error


def workflow_stack_order(workflow: object) -> tuple[str, ...]:
    """Return workflow stack aliases as an immutable tuple."""

    stack_order = getattr(workflow, "stack_order", ()) or ()
    return cast("tuple[str, ...]", tuple(stack_order))


def _log_legacy_scope(
    legacy_scope_logger: Callable[[str], None] | None,
    *,
    reason: str,
) -> None:
    """Log a legacy global override fallback through the shell logger callback."""

    if legacy_scope_logger is not None:
        legacy_scope_logger(reason)


def activation_node_keys_by_alias(
    behavior_snapshot: object | None,
    workflow: object,
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    """Return Sugar activation override deltas grouped by cube alias."""

    if behavior_snapshot is None:
        return {}, {}
    decisions_by_alias = getattr(behavior_snapshot, "card_decisions_by_alias", {})
    if not isinstance(decisions_by_alias, Mapping):
        return {}, {}

    enabled: dict[str, tuple[str, ...]] = {}
    disabled: dict[str, tuple[str, ...]] = {}
    for alias, decisions in decisions_by_alias.items():
        if not isinstance(alias, str) or not isinstance(decisions, Mapping):
            continue
        nodes = workflow_buffer_nodes_for_alias(workflow, alias)
        enabled_nodes: list[str] = []
        disabled_nodes: list[str] = []
        for node_name, decision in decisions.items():
            if not isinstance(node_name, str):
                continue
            authored_bypass = node_payload_has_authored_bypass(nodes.get(node_name))
            decision_enabled = bool(getattr(decision, "enabled", False))
            if authored_bypass and decision_enabled:
                enabled_nodes.append(node_name)
            elif not authored_bypass and not decision_enabled:
                disabled_nodes.append(node_name)
        if enabled_nodes:
            enabled[alias] = tuple(enabled_nodes)
        if disabled_nodes:
            disabled[alias] = tuple(disabled_nodes)
    return enabled, disabled


def workflow_buffer_nodes_for_alias(
    workflow: object,
    alias: str,
) -> Mapping[str, object]:
    """Return serialized node payloads for one workflow alias when available."""

    cubes = getattr(workflow, "cubes", None)
    if not isinstance(cubes, Mapping):
        return {}
    cube_state = cubes.get(alias)
    buffer = getattr(cube_state, "buffer", None)
    if not isinstance(buffer, Mapping):
        return {}
    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return {}
    return nodes


def node_payload_has_authored_bypass(node_payload: object) -> bool:
    """Return whether a workflow node payload carries authored bypass mode."""

    if not isinstance(node_payload, Mapping):
        return False
    mode = node_payload.get("mode")
    return isinstance(mode, int) and not isinstance(mode, bool) and mode == 4


__all__ = [
    "activation_node_keys_by_alias",
    "active_behavior_snapshot",
    "active_global_override_scopes",
    "build_generation_request_for_view",
    "editor_panel_for_workflow",
    "errored_cube_aliases",
    "GenerationWorkflowPruneReport",
    "generation_request_from_workflow_state",
    "node_payload_has_authored_bypass",
    "preflight_live_node_definitions",
    "pruned_workflow_for_generation",
    "workflow_issue_pruning_service",
    "workflow_buffer_nodes_for_alias",
    "workflow_stack_order",
]
