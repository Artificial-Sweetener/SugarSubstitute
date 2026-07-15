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

"""Prepare panel projections and their freshness identity."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Literal, Protocol, TypeVar

from substitute.application.node_behavior import LiveNodeDefinitionError
from substitute.shared.logging.logger import get_logger, log_timing
from substitute.shared.logging.logger import log_info

from .projection_observability import (
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)

_LOGGER = get_logger("presentation.editor.panel.projection_preparation")
_T = TypeVar("_T")

BehaviorRefreshReason = Literal[
    "full_workflow_projection",
    "cube_added",
    "cube_removed",
    "cube_renamed",
    "stack_reordered",
    "global_override_changed",
    "search_changed",
    "node_activation_changed",
    "node_link_changed",
    "prompt_link_changed",
    "node_definition_changed",
]
CubeDefinitionIdentity = tuple[str, str, str, str, str, str, str]


class ProjectionPreparationPanelPort(Protocol):
    """Describe panel state and operations used while preparing projections."""

    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    _current_search_hidden_keys: set[object] | None
    _current_search_matching_nodes: set[object] | None
    _current_node_search_text: str | None

    def reconcile_prompt_link_state(
        self,
        *,
        previous_cube_states: dict[str, object] | None,
        previous_stack_order: list[str] | None,
        cube_states: dict[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Reconcile prompt links for one workflow transition."""

    def _build_behavior_snapshot(self, **kwargs: object) -> object:
        """Return the current behavior snapshot for panel projection."""

    def _refresh_sampler_scheduler_link_state(self) -> None:
        """Refresh sampler and scheduler link metadata."""


class ProjectionPromptContextPort(Protocol):
    """Describe optional projection-scoped prompt context operations."""

    def begin_projection_prompt_context(
        self,
        *,
        cube_states: dict[str, object] | None,
        stack_order: Sequence[str],
        reason: BehaviorRefreshReason,
    ) -> None:
        """Begin projection-scoped prompt context for preparation."""

    def clear_projection_prompt_context(self, *, reason: str) -> None:
        """Clear projection-scoped prompt context for preparation."""


class ProjectionRuntimeIssuePort(Protocol):
    """Describe stale-safe runtime issue integration used during preparation."""

    def hydrate_node_definitions_for_projection(
        self,
        *,
        reason: BehaviorRefreshReason,
        workflow_id: str,
    ) -> None:
        """Hydrate live node definitions before projection builds widgets."""

    def cube_runtime_error_aliases(self) -> frozenset[str]:
        """Return aliases that should render as errored sections."""

    def run_projection_metadata_step(
        self,
        *,
        workflow_id: str,
        reason: str,
        action: Callable[[frozenset[str]], _T],
    ) -> _T:
        """Run one metadata step with recoverable runtime issue handling."""

    def run_with_pruned_panel_state(
        self,
        errored_aliases: frozenset[str],
        action: Callable[[], _T],
    ) -> _T:
        """Run one action while errored aliases are absent from panel state."""


def begin_behavior_refresh_transaction(
    panel: object,
    *,
    reason: BehaviorRefreshReason,
    workflow_id: str,
) -> bool:
    """Start a panel-owned behavior snapshot transaction when supported."""

    begin_transaction = getattr(
        panel,
        "begin_behavior_refresh_transaction",
        None,
    )
    if not callable(begin_transaction):
        return False
    begin_transaction(reason=reason)
    log_info(
        _LOGGER,
        "Started editor refresh behavior transaction",
        workflow_id=workflow_id,
        reason=reason,
    )
    return True


def end_behavior_refresh_transaction(
    panel: object,
    *,
    reason: BehaviorRefreshReason,
    workflow_id: str,
    transaction_started: bool,
) -> None:
    """Complete a panel-owned behavior snapshot transaction when one was started."""

    if not transaction_started:
        return
    end_transaction = getattr(
        panel,
        "end_behavior_refresh_transaction",
        None,
    )
    if callable(end_transaction):
        end_transaction(reason=reason)
    log_info(
        _LOGGER,
        "Completed editor refresh behavior transaction",
        workflow_id=workflow_id,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class EditorProjectionPreparationRequest:
    """Describe one projection preparation request and its stable inputs."""

    cube_entries: tuple[tuple[str, object], ...]
    cube_states: dict[str, object] | None
    stack_order: tuple[str, ...]
    previous_cube_states: dict[str, object] | None
    previous_stack_order: tuple[str, ...] | None
    reason: BehaviorRefreshReason
    workflow_id: str
    prompt_context_required: bool


@dataclass(frozen=True, slots=True)
class EditorProjectionPreparationIdentity:
    """Identify the prepared projection state consumed by later build stages."""

    workflow_id: str
    reason: BehaviorRefreshReason
    stack_order: tuple[str, ...]
    cube_state_map_id: int
    cube_state_tokens: tuple[tuple[Hashable, ...], ...]
    cube_definition_identities: tuple[CubeDefinitionIdentity, ...]
    errored_aliases: frozenset[str]
    behavior_snapshot_id: int
    behavior_snapshot_type: str
    runtime_issue_identity: tuple[str, ...]
    search_identity: tuple[str | None, tuple[str, ...]]
    hidden_field_identity: tuple[str, ...]
    prompt_context_identity: tuple[object, ...]
    projection_mode: str


@dataclass(frozen=True, slots=True)
class EditorProjectionPreparation:
    """Describe a hydrated editor projection ready for widget construction."""

    request: EditorProjectionPreparationRequest
    identity: EditorProjectionPreparationIdentity
    cube_entries: tuple[tuple[str, object], ...]
    cube_states: dict[str, object] | None
    stack_order: tuple[str, ...]
    behavior_snapshot: object
    hydration_result: object | None
    errored_aliases: frozenset[str]
    reason: BehaviorRefreshReason
    snapshot_identity: object
    behavior_transaction_started: bool
    prompt_context_started: bool


class EditorProjectionPreparationController:
    """Own panel projection preparation and its stale-check identity."""

    def __init__(
        self,
        *,
        panel: ProjectionPreparationPanelPort,
        prompt_context: ProjectionPromptContextPort | None,
        runtime_issues: ProjectionRuntimeIssuePort,
        begin_behavior_transaction: Callable[
            [BehaviorRefreshReason, str],
            bool,
        ],
        end_behavior_transaction: Callable[
            [BehaviorRefreshReason, str, bool],
            None,
        ],
    ) -> None:
        """Store typed collaborators used to prepare projection snapshots."""

        self._panel = panel
        self._prompt_context = prompt_context
        self._runtime_issues = runtime_issues
        self._begin_behavior_transaction = begin_behavior_transaction
        self._end_behavior_transaction = end_behavior_transaction

    def prepare_projection(
        self,
        cube_entries: Sequence[tuple[str, object]],
        *,
        cube_states: dict[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: BehaviorRefreshReason,
        workflow_id: str,
        previous_cube_states: dict[str, object] | None,
        previous_stack_order: list[str] | None,
        prompt_context_required: bool = False,
    ) -> EditorProjectionPreparation:
        """Install state, hydrate definitions, and build a behavior snapshot."""

        panel = self._panel
        request = EditorProjectionPreparationRequest(
            cube_entries=tuple(cube_entries),
            cube_states=cube_states,
            stack_order=tuple(stack_order or ()),
            previous_cube_states=previous_cube_states,
            previous_stack_order=(
                tuple(previous_stack_order)
                if previous_stack_order is not None
                else None
            ),
            reason=reason,
            workflow_id=workflow_id,
            prompt_context_required=prompt_context_required,
        )
        panel._cube_states = cube_states
        panel._stack_order = list(stack_order) if stack_order is not None else None

        phase_started_at = panel_projection_observability_started_at()
        self._runtime_issues.hydrate_node_definitions_for_projection(
            reason=reason,
            workflow_id=workflow_id,
        )
        hydration_result = None
        errored_aliases = self._runtime_issues.cube_runtime_error_aliases()
        log_panel_projection_timing(
            "preparation.hydrate_node_definitions",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_section_count=len(cube_entries),
            errored_cube_count=len(errored_aliases),
            reason=reason,
        )

        phase_started_at = panel_projection_observability_started_at()

        def reconcile_prompt_links(aliases: frozenset[str]) -> None:
            """Reconcile prompt links against the non-errored cube set."""

            panel.reconcile_prompt_link_state(
                previous_cube_states=without_cube_aliases(
                    previous_cube_states,
                    aliases,
                ),
                previous_stack_order=without_stack_aliases(
                    previous_stack_order,
                    aliases,
                ),
                cube_states=without_cube_aliases(cube_states, aliases),
                stack_order=without_stack_aliases(stack_order, aliases),
            )

        self._runtime_issues.run_projection_metadata_step(
            workflow_id=workflow_id,
            reason="prompt_link_reconciliation",
            action=reconcile_prompt_links,
        )
        errored_aliases = self._runtime_issues.cube_runtime_error_aliases()
        log_panel_projection_timing(
            "preparation.prompt_link_reconciliation",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_section_count=len(cube_entries),
            reason=reason,
        )

        behavior_transaction_started = self._begin_behavior_transaction(
            reason,
            workflow_id,
        )
        try:
            phase_started_at = panel_projection_observability_started_at()
            behavior_snapshot = self._runtime_issues.run_projection_metadata_step(
                workflow_id=workflow_id,
                reason="behavior_snapshot",
                action=lambda aliases: self._runtime_issues.run_with_pruned_panel_state(
                    aliases,
                    panel._build_behavior_snapshot,
                ),
            )
            log_panel_projection_timing(
                "preparation.behavior_snapshot",
                started_at=phase_started_at,
                workflow_id=workflow_id,
                cube_section_count=len(cube_entries),
                reason=reason,
            )
        except (LiveNodeDefinitionError, RuntimeError, TypeError, ValueError):
            self._end_behavior_transaction(
                reason,
                workflow_id,
                behavior_transaction_started,
            )
            raise
        errored_aliases = self._runtime_issues.cube_runtime_error_aliases()

        phase_started_at = perf_counter()

        def refresh_link_state(aliases: frozenset[str]) -> None:
            """Refresh snapshot-backed link affordances for non-errored cubes."""

            self._runtime_issues.run_with_pruned_panel_state(
                aliases,
                panel._refresh_sampler_scheduler_link_state,
            )

        self._runtime_issues.run_projection_metadata_step(
            workflow_id=workflow_id,
            reason="link_state_refresh",
            action=refresh_link_state,
        )
        errored_aliases = self._runtime_issues.cube_runtime_error_aliases()
        log_timing(
            _LOGGER,
            "Refreshed editor link state before cube widget reconciliation",
            started_at=phase_started_at,
            workflow_id=workflow_id,
            cube_section_count=len(cube_entries),
            reason=reason,
            level="debug",
        )
        prompt_context_started = self.begin_prompt_context(request)
        preparation_identity = self.preparation_identity(
            request,
            errored_aliases=errored_aliases,
            behavior_snapshot=behavior_snapshot,
        )

        return EditorProjectionPreparation(
            request=request,
            identity=preparation_identity,
            cube_entries=request.cube_entries,
            cube_states=cube_states,
            stack_order=request.stack_order,
            behavior_snapshot=behavior_snapshot,
            hydration_result=hydration_result,
            errored_aliases=errored_aliases,
            reason=reason,
            snapshot_identity=preparation_identity,
            behavior_transaction_started=behavior_transaction_started,
            prompt_context_started=prompt_context_started,
        )

    def preparation_identity(
        self,
        request: EditorProjectionPreparationRequest,
        *,
        errored_aliases: frozenset[str],
        behavior_snapshot: object,
    ) -> EditorProjectionPreparationIdentity:
        """Return the validation identity for one prepared editor projection."""

        panel = self._panel
        state_map = request.cube_states or {}
        cube_state_tokens = tuple(
            cube_projection_token(alias, state_map.get(alias))
            for alias in request.stack_order
        )
        cube_definition_identities = tuple(
            cube_definition_identity(alias, state_map[alias])
            for alias in request.stack_order
            if alias in state_map
        )
        hidden_keys = getattr(panel, "_current_search_hidden_keys", None) or set()
        matching_nodes = getattr(panel, "_current_search_matching_nodes", None) or set()
        hidden_field_identity = tuple(sorted(repr(key) for key in hidden_keys))
        search_identity = (
            getattr(panel, "_current_node_search_text", None),
            tuple(sorted(repr(key) for key in matching_nodes)),
        )
        prompt_context_identity = (
            request.prompt_context_required,
            id(request.cube_states),
            request.stack_order,
            request.reason,
        )
        runtime_issue_identity = tuple(sorted(errored_aliases))
        return EditorProjectionPreparationIdentity(
            workflow_id=request.workflow_id,
            reason=request.reason,
            stack_order=request.stack_order,
            cube_state_map_id=id(request.cube_states),
            cube_state_tokens=cube_state_tokens,
            cube_definition_identities=cube_definition_identities,
            errored_aliases=errored_aliases,
            behavior_snapshot_id=id(behavior_snapshot),
            behavior_snapshot_type=type(behavior_snapshot).__name__,
            runtime_issue_identity=runtime_issue_identity,
            search_identity=search_identity,
            hidden_field_identity=hidden_field_identity,
            prompt_context_identity=prompt_context_identity,
            projection_mode="live",
        )

    def begin_prompt_context(
        self,
        request: EditorProjectionPreparationRequest,
    ) -> bool:
        """Begin projection-scoped prompt context for full projection preparation."""

        if not request.prompt_context_required:
            return False
        prompt_context = self._prompt_context
        if prompt_context is None:
            return False
        begin_projection_prompt_context = getattr(
            prompt_context,
            "begin_projection_prompt_context",
            None,
        )
        if not callable(begin_projection_prompt_context):
            return False
        begin_projection_prompt_context(
            cube_states=request.cube_states,
            stack_order=request.stack_order,
            reason=request.reason,
        )
        return True

    def clear_prompt_context(
        self,
        preparation: EditorProjectionPreparation,
        *,
        reason: str,
    ) -> None:
        """Clear projection-scoped prompt context for a prepared projection."""

        if not preparation.prompt_context_started:
            return
        if self._prompt_context is None:
            return
        clear_projection_prompt_context = getattr(
            self._prompt_context,
            "clear_projection_prompt_context",
            None,
        )
        if callable(clear_projection_prompt_context):
            clear_projection_prompt_context(reason=reason)

    def end_behavior_transaction(
        self,
        preparation: EditorProjectionPreparation,
        *,
        reason: BehaviorRefreshReason,
    ) -> None:
        """End the behavior transaction started for one projection preparation."""

        self._end_behavior_transaction(
            reason,
            preparation.request.workflow_id,
            preparation.behavior_transaction_started,
        )


def cube_projection_token(
    alias: str,
    cube_state: object | None,
) -> tuple[Hashable, ...]:
    """Return a structural token for one cube state's rendered card shape."""

    buffer = getattr(cube_state, "buffer", None)
    if not isinstance(buffer, dict):
        return (alias, id(cube_state), id(buffer))
    nodes = buffer.get("nodes", {})
    if not isinstance(nodes, dict):
        return (alias, id(cube_state), id(buffer), "invalid_nodes")
    node_tokens: list[tuple[str, str, tuple[str, ...]]] = []
    for node_name, node_data in sorted(nodes.items(), key=lambda item: str(item[0])):
        if not isinstance(node_data, dict):
            node_tokens.append((str(node_name), "", ()))
            continue
        inputs = node_data.get("inputs", {})
        input_keys = (
            tuple(sorted(str(key) for key in inputs))
            if isinstance(inputs, dict)
            else ()
        )
        node_tokens.append(
            (
                str(node_name),
                str(node_data.get("class_type", "")),
                input_keys,
            )
        )
    return (alias, id(cube_state), id(buffer), tuple(node_tokens))


def without_cube_aliases(
    cube_states: dict[str, object] | Sequence[tuple[str, object]] | None,
    aliases: frozenset[str],
) -> dict[str, object] | None:
    """Return cube-state mapping with errored aliases removed."""

    if cube_states is None:
        return None
    if isinstance(cube_states, dict):
        return {
            alias: state for alias, state in cube_states.items() if alias not in aliases
        }
    return {alias: state for alias, state in cube_states if alias not in aliases}


def cube_definition_identity(
    alias: str,
    cube_state: object,
) -> CubeDefinitionIdentity:
    """Return the rendered-definition identity for one cube state."""

    cube_id = _text(getattr(cube_state, "cube_id", None))
    version = _text(getattr(cube_state, "version", None))
    structural_source = getattr(cube_state, "original_cube", None)
    if not isinstance(structural_source, dict):
        structural_source = getattr(cube_state, "buffer", None)
    return (
        alias,
        cube_id,
        version,
        "",
        "",
        _stable_hash(_surface_identity_payload(structural_source)),
        _stable_hash(_node_behavior_identity_payload(structural_source)),
    )


def without_stack_aliases(
    stack_order: Sequence[str] | None,
    aliases: frozenset[str],
) -> list[str] | None:
    """Return stack order with errored aliases removed."""

    if stack_order is None:
        return None
    return [alias for alias in stack_order if alias not in aliases]


def _surface_identity_payload(source: object) -> object:
    """Return surface-bearing sections used for editor widget reuse checks."""

    if not isinstance(source, dict):
        return {}
    return {
        key: source.get(key)
        for key in ("surface", "subgraphs", "layout", "inputs", "outputs")
        if key in source
    }


def _node_behavior_identity_payload(source: object) -> object:
    """Return node class metadata used for editor behavior reuse checks."""

    if not isinstance(source, dict):
        return {}
    nodes = source.get("nodes")
    if not isinstance(nodes, dict):
        return {}
    return {
        str(node_name): (
            node.get("class_type") if isinstance(node, dict) else None,
            node.get("type") if isinstance(node, dict) else None,
        )
        for node_name, node in nodes.items()
    }


def _stable_hash(value: object) -> str:
    """Return a deterministic digest for JSON-like identity payloads."""

    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except TypeError:
        encoded = repr(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text(value: object) -> str:
    """Return stripped text for identity fields."""

    return value.strip() if isinstance(value, str) else ""
