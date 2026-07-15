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

"""Own editor-panel prompt context snapshots and feature-profile caches."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptScheduledLora,
    ScheduledLoraProvider,
    WorkflowPromptContext,
)
from substitute.presentation.editor.panel.prompt_profile_policy import (
    PanelPromptFieldProfileDecision,
    PanelPromptProfilePolicy,
)
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_event,
    log_panel_projection_timing,
    panel_projection_observability_started_at,
)
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("presentation.editor.panel.prompt_context_controller")


@dataclass(slots=True)
class PanelBehaviorRefreshTransaction:
    """Track one explicit editor behavior snapshot reuse boundary."""

    reason: str
    snapshot: EditorBehaviorSnapshot | None = None
    reuse_key: tuple[Hashable, ...] | None = None


@dataclass(frozen=True, slots=True)
class PromptWorkflowCubeSnapshot:
    """Store immutable cube data used by projection-scope prompt analysis."""

    cube_id: str
    version: str
    buffer: Mapping[str, object]
    display_name: str
    ui: Mapping[str, object] | None


class PromptFeatureProfileServiceProtocol(Protocol):
    """Describe prompt feature-profile resolution used by the controller."""

    def build_profile(
        self,
        *,
        field_style: Mapping[str, object],
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> PromptEditorFeatureProfile:
        """Build one prompt feature profile for a field context."""


class NodeBehaviorServiceProtocol(Protocol):
    """Describe behavior snapshot construction used by prompt context."""

    def build_snapshot(
        self,
        *,
        cube_states: Mapping[str, object],
        stack_order: list[str],
        workflow_overrides: Mapping[str, object],
        search_hidden_keys: set[object],
        override_hidden_field_keys: set[object] | None,
        node_search_text: str | None,
        search_matching_nodes: set[tuple[str, str]] | None,
    ) -> EditorBehaviorSnapshot:
        """Build a behavior snapshot for the supplied workflow state."""


class EditorPanelPromptContextHost(Protocol):
    """Describe panel state needed to prepare prompt context snapshots."""

    node_behavior_service: NodeBehaviorServiceProtocol
    scheduled_lora_provider: ScheduledLoraProvider | None
    prompt_feature_profile_service: PromptFeatureProfileServiceProtocol | None
    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    _current_search_hidden_keys: set[object] | None
    _current_node_search_text: str | None
    _current_search_matching_nodes: set[tuple[str, str]] | None
    _last_behavior_snapshot: EditorBehaviorSnapshot | None

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides for prompt context cache keys."""


@dataclass(frozen=True, slots=True)
class _PromptFeatureProfileCacheLogContext:
    """Carry prompt-safe profile-cache diagnostic fields."""

    cube_alias: str
    node_name: str
    field_key: str
    context_source: str
    cache_entry_count: int


def _log_prompt_feature_profile_cache_event(
    event: str,
    *,
    context: _PromptFeatureProfileCacheLogContext,
) -> None:
    """Log one prompt-safe feature-profile cache lifecycle event."""

    log_panel_projection_event(
        event,
        cube_alias=context.cube_alias,
        node_name=context.node_name,
        field_key=context.field_key,
        context_source=context.context_source,
        cache_entry_count=context.cache_entry_count,
    )


def _log_prompt_feature_profile_cache_timing(
    event: str,
    *,
    started_at: float,
    context: _PromptFeatureProfileCacheLogContext,
) -> float:
    """Log timing for one prompt-safe feature-profile cache operation."""

    return log_panel_projection_timing(
        event,
        started_at=started_at,
        cube_alias=context.cube_alias,
        node_name=context.node_name,
        field_key=context.field_key,
        context_source=context.context_source,
        cache_entry_count=context.cache_entry_count,
    )


class EditorPanelPromptContextController:
    """Prepare prompt workflow context and feature-profile state for a panel."""

    def __init__(self, host: EditorPanelPromptContextHost) -> None:
        """Store the host and initialize prompt-context caches."""

        self._host = host
        self._behavior_refresh_transaction: PanelBehaviorRefreshTransaction | None = (
            None
        )
        self._workflow_prompt_context_cache_key: tuple[Hashable, ...] | None = None
        self._workflow_prompt_context_cache: WorkflowPromptContext | None = None
        self._projection_prompt_context: WorkflowPromptContext | None = None
        self._projection_prompt_context_token: tuple[Hashable, ...] | None = None
        self._projection_prompt_context_reason = ""
        self._prompt_feature_profile_cache_scope_key: tuple[Hashable, ...] | None = None
        self._prompt_feature_profile_cache: dict[
            tuple[Hashable, ...],
            PromptEditorFeatureProfile,
        ] = {}
        self._prompt_profile_policy = PanelPromptProfilePolicy()

    @property
    def projection_prompt_context(self) -> WorkflowPromptContext | None:
        """Return the active projection-scoped prompt context when present."""

        return self._projection_prompt_context

    def set_current_behavior_snapshot(
        self,
        snapshot: EditorBehaviorSnapshot | None,
    ) -> None:
        """Publish the latest behavior snapshot through the panel mirror."""

        self._host._last_behavior_snapshot = snapshot

    def build_behavior_snapshot(
        self,
        *,
        search_hidden_keys: set[object] | None = None,
        override_hidden_field_keys: set[object] | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
    ) -> EditorBehaviorSnapshot | None:
        """Resolve and cache the latest node-behavior snapshot for panel state."""

        if not self._host._stack_order or not self._host._cube_states:
            return None
        effective_search_hidden_keys = (
            search_hidden_keys
            if search_hidden_keys is not None
            else (self._host._current_search_hidden_keys or set())
        )
        effective_node_search_text = (
            node_search_text
            if node_search_text is not None
            else self._host._current_node_search_text
        )
        effective_search_matching_nodes = (
            search_matching_nodes
            if search_matching_nodes is not None
            else self._host._current_search_matching_nodes
        )
        workflow_overrides = self._host._workflow_overrides()
        reuse_key = self.behavior_snapshot_reuse_key(
            workflow_overrides=workflow_overrides,
            search_hidden_keys=effective_search_hidden_keys,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=effective_node_search_text,
            search_matching_nodes=effective_search_matching_nodes,
        )
        transaction = self._behavior_refresh_transaction
        if (
            transaction is not None
            and transaction.snapshot is not None
            and transaction.reuse_key == reuse_key
        ):
            self.set_current_behavior_snapshot(transaction.snapshot)
            log_info(
                _LOGGER,
                "Reused editor behavior snapshot from refresh transaction",
                reason=transaction.reason,
                cube_section_count=len(self._host._stack_order),
            )
            return transaction.snapshot
        snapshot = self._host.node_behavior_service.build_snapshot(
            cube_states=self._host._cube_states,
            stack_order=list(self._host._stack_order),
            workflow_overrides=workflow_overrides,
            search_hidden_keys=effective_search_hidden_keys,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=effective_node_search_text,
            search_matching_nodes=effective_search_matching_nodes,
        )
        self.set_current_behavior_snapshot(snapshot)
        if transaction is not None:
            transaction.snapshot = snapshot
            transaction.reuse_key = reuse_key
        return snapshot

    def begin_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Start an explicit behavior snapshot reuse boundary for one refresh flow."""

        self._behavior_refresh_transaction = PanelBehaviorRefreshTransaction(
            reason=reason
        )
        log_info(
            _LOGGER,
            "Started editor behavior snapshot refresh transaction",
            reason=reason,
            cube_section_count=len(self._host._stack_order or []),
        )

    def end_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Complete the active behavior snapshot reuse boundary when present."""

        transaction = self._behavior_refresh_transaction
        if transaction is None:
            return
        self._behavior_refresh_transaction = None
        log_info(
            _LOGGER,
            "Completed editor behavior snapshot refresh transaction",
            reason=reason,
            transaction_reason=transaction.reason,
            reused_snapshot=transaction.snapshot is not None,
        )

    def invalidate_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Drop the active behavior transaction before a state-changing refresh."""

        transaction = self._behavior_refresh_transaction
        if transaction is None:
            return
        self._behavior_refresh_transaction = None
        log_info(
            _LOGGER,
            "Invalidated editor behavior snapshot refresh transaction",
            reason=reason,
            transaction_reason=transaction.reason,
        )

    def behavior_snapshot_reuse_key(
        self,
        *,
        workflow_overrides: Mapping[str, object],
        search_hidden_keys: set[object] | None,
        override_hidden_field_keys: set[object] | None,
        node_search_text: str | None,
        search_matching_nodes: set[tuple[str, str]] | None,
    ) -> tuple[Hashable, ...]:
        """Return the identity key that makes transaction snapshot reuse safe."""

        cube_states = self._host._cube_states or {}
        stack_order = tuple(self._host._stack_order or [])
        cube_tokens = tuple(
            (alias, id(cube_states.get(alias))) for alias in stack_order
        )
        override_tokens = tuple(
            (str(key), repr(value))
            for key, value in sorted(
                workflow_overrides.items(),
                key=lambda item: str(item[0]),
            )
        )
        hidden_tokens = tuple(
            sorted(repr(key) for key in (search_hidden_keys or set()))
        )
        override_hidden_tokens = tuple(
            sorted(repr(key) for key in (override_hidden_field_keys or set()))
        )
        matching_tokens = tuple(
            sorted(repr(key) for key in (search_matching_nodes or set()))
        )
        return (
            stack_order,
            id(cube_states),
            cube_tokens,
            override_tokens,
            hidden_tokens,
            override_hidden_tokens,
            node_search_text,
            matching_tokens,
        )

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the latest cached behavior snapshot for external rendering."""

        return self._host._last_behavior_snapshot

    def workflow_prompt_context(self) -> WorkflowPromptContext:
        """Return the current workflow context used by prompt-field resolvers."""

        workflow_overrides = self._host._workflow_overrides()
        cache_key = self.workflow_prompt_context_key(workflow_overrides)
        if (
            cache_key == self._workflow_prompt_context_cache_key
            and self._workflow_prompt_context_cache is not None
        ):
            return self._workflow_prompt_context_cache
        context = WorkflowPromptContext(
            cube_states=self._host._cube_states or {},
            stack_order=list(self._host._stack_order or []),
            workflow_overrides=workflow_overrides,
            behavior_snapshot=self._host._last_behavior_snapshot,
            cache_token=cache_key,
        )
        self._workflow_prompt_context_cache_key = cache_key
        self._workflow_prompt_context_cache = context
        return context

    def begin_projection_prompt_context(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> None:
        """Capture immutable prompt-analysis workflow state for one projection."""

        context = self.build_projection_prompt_context(
            cube_states=cube_states,
            stack_order=stack_order,
            reason=reason,
        )
        self._projection_prompt_context = context
        self._projection_prompt_context_token = context.cache_token
        self._projection_prompt_context_reason = reason
        self._reset_prompt_feature_profile_cache_if_needed(context.cache_token)
        log_panel_projection_event(
            "prompt_context.projection_begin",
            reason=reason,
            cube_count=len(context.cube_states),
            stack_order_count=len(context.stack_order),
            override_count=len(context.workflow_overrides),
            behavior_snapshot_present=context.behavior_snapshot is not None,
            cache_entry_count=len(self._prompt_feature_profile_cache),
        )

    def clear_projection_prompt_context(self, *, reason: str) -> None:
        """Clear projection-scoped prompt state before live editing resumes."""

        previous_cache_entries = len(self._prompt_feature_profile_cache)
        projection_context_present = self._projection_prompt_context is not None
        self._projection_prompt_context = None
        self._projection_prompt_context_token = None
        self._projection_prompt_context_reason = ""
        self._prompt_feature_profile_cache_scope_key = None
        self._prompt_feature_profile_cache = {}
        log_panel_projection_event(
            "prompt_context.projection_clear",
            reason=reason,
            projection_context_present=projection_context_present,
            cache_entry_count=previous_cache_entries,
        )

    def build_projection_prompt_context(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> WorkflowPromptContext:
        """Return a workflow prompt context detached from live cube mutation."""

        cube_snapshots = self.snapshot_prompt_cube_states(
            cube_states=cube_states,
            stack_order=stack_order,
        )
        override_snapshot = self.snapshot_prompt_workflow_overrides()
        resolved_stack_order = tuple(
            alias
            for alias in (stack_order or tuple(cube_snapshots))
            if alias in cube_snapshots
        )
        cube_tokens = tuple(
            (alias, id(cube_snapshots[alias]), id(cube_snapshots[alias].buffer))
            for alias in resolved_stack_order
        )
        override_tokens = tuple(
            (key, id(value))
            for key, value in sorted(
                override_snapshot.items(),
                key=lambda item: item[0],
            )
        )
        cache_token: tuple[Hashable, ...] = (
            "projection_prompt_context",
            reason,
            resolved_stack_order,
            cube_tokens,
            override_tokens,
            id(self._host._last_behavior_snapshot),
        )
        return WorkflowPromptContext(
            cube_states=cube_snapshots,
            stack_order=resolved_stack_order,
            workflow_overrides=override_snapshot,
            behavior_snapshot=self._host._last_behavior_snapshot,
            cache_token=cache_token,
        )

    def snapshot_prompt_cube_states(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> dict[str, PromptWorkflowCubeSnapshot]:
        """Return cube snapshots whose buffers no longer alias live state."""

        if cube_states is None:
            return {}
        aliases = tuple(stack_order or cube_states.keys())
        snapshots: dict[str, PromptWorkflowCubeSnapshot] = {}
        node_count = 0
        for alias in aliases:
            cube_state = cube_states.get(alias)
            if cube_state is None:
                continue
            raw_buffer = getattr(cube_state, "buffer", {})
            buffer = (
                deepcopy(dict(raw_buffer)) if isinstance(raw_buffer, Mapping) else {}
            )
            raw_ui = getattr(cube_state, "ui", None)
            ui = deepcopy(dict(raw_ui)) if isinstance(raw_ui, Mapping) else None
            cube_id = str(getattr(cube_state, "cube_id", ""))
            snapshot = PromptWorkflowCubeSnapshot(
                cube_id=cube_id,
                version=str(getattr(cube_state, "version", "")),
                buffer=cast(Mapping[str, object], buffer),
                display_name=str(getattr(cube_state, "display_name", cube_id)),
                ui=cast(Mapping[str, object] | None, ui),
            )
            snapshots[alias] = snapshot
            nodes = snapshot.buffer.get("nodes", {})
            if isinstance(nodes, Mapping):
                node_count += len(nodes)
        log_panel_projection_event(
            "prompt_context.snapshot_cubes",
            cube_count=len(snapshots),
            node_count=node_count,
        )
        return snapshots

    def snapshot_prompt_workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides detached from live mutation."""

        overrides: dict[str, object] = {}
        for key, value in self._host._workflow_overrides().items():
            key_text = str(key)
            overrides[key_text] = deepcopy(value)
        log_panel_projection_event(
            "prompt_context.snapshot_overrides",
            override_count=len(overrides),
        )
        return overrides

    def prompt_workflow_context_for_feature_profiles(self) -> WorkflowPromptContext:
        """Return the active prompt context for feature-profile resolution."""

        if self._projection_prompt_context is not None:
            return self._projection_prompt_context
        return self.workflow_prompt_context()

    def workflow_prompt_context_key(
        self,
        workflow_overrides: Mapping[str, object],
    ) -> tuple[Hashable, ...]:
        """Return the refresh-scoped identity key for prompt workflow context reuse."""

        cube_states = self._host._cube_states or {}
        cube_tokens = tuple(
            (
                alias,
                id(cube_state),
                id(getattr(cube_state, "buffer", None)),
                id(getattr(cube_state, "original_cube", None)),
            )
            for alias, cube_state in sorted(
                cube_states.items(), key=lambda item: item[0]
            )
        )
        override_tokens = tuple(
            (key, id(value))
            for key, value in sorted(
                workflow_overrides.items(), key=lambda item: item[0]
            )
        )
        return (
            tuple(self._host._stack_order or []),
            id(cube_states),
            cube_tokens,
            override_tokens,
            id(self._host._last_behavior_snapshot),
        )

    def scheduled_lora_resolver_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> Callable[[str], tuple[PromptScheduledLora, ...]] | None:
        """Return a narrow resolver callable bound to one prompt field context."""

        provider = self._host.scheduled_lora_provider
        if provider is None:
            return None
        workflow_context = self.build_projection_prompt_context(
            cube_states=self._host._cube_states,
            stack_order=self._host._stack_order,
            reason="scheduled_lora_context",
        )

        def resolve(prompt_text: str) -> tuple[PromptScheduledLora, ...]:
            """Resolve scheduled LoRAs for the current prompt text."""

            return provider.scheduled_loras_for_prompt_context(
                workflow_context=workflow_context,
                cube_alias=cube_alias,
                prompt_node_name=prompt_node_name,
                prompt_field_key=prompt_field_key,
                prompt_text=prompt_text,
            )

        setattr(resolve, "scheduled_lora_context_token", workflow_context.cache_token)
        return resolve

    def prompt_feature_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PromptEditorFeatureProfile | None:
        """Return the resolved prompt feature profile for one prompt field."""

        service = self._host.prompt_feature_profile_service
        if service is None:
            return None
        source = "projection" if self._projection_prompt_context is not None else "live"
        workflow_context = self.prompt_workflow_context_for_feature_profiles()
        self._reset_prompt_feature_profile_cache_if_needed(workflow_context.cache_token)
        cache_key = self._prompt_feature_profile_cache_entry_key(
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
            field_style=field_style,
        )
        log_context = _PromptFeatureProfileCacheLogContext(
            cube_alias=cube_alias or "",
            node_name=prompt_node_name,
            field_key=prompt_field_key,
            context_source=source,
            cache_entry_count=len(self._prompt_feature_profile_cache),
        )
        cached = self._prompt_feature_profile_cache.get(cache_key)
        if cached is not None:
            _log_prompt_feature_profile_cache_event(
                "prompt_context.profile_cache_hit",
                context=log_context,
            )
            return cached
        _log_prompt_feature_profile_cache_event(
            "prompt_context.profile_cache_miss",
            context=log_context,
        )
        profile_started_at = panel_projection_observability_started_at()
        profile = service.build_profile(
            field_style=field_style,
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
        )
        _log_prompt_feature_profile_cache_timing(
            "prompt_context.profile_cache_build",
            started_at=profile_started_at,
            context=log_context,
        )
        self._prompt_feature_profile_cache[cache_key] = profile
        return profile

    def prompt_field_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Return prepared feature and syntax profiles for one prompt field."""

        feature_profile = self.prompt_feature_profile_for_prompt(
            cube_alias,
            prompt_node_name,
            prompt_field_key,
            field_style,
        )
        return self._prompt_profile_policy.prepare_prompt_field_profile(
            field_style=field_style,
            feature_profile=feature_profile,
        )

    def _reset_prompt_feature_profile_cache_if_needed(
        self,
        scope_key: tuple[Hashable, ...],
    ) -> None:
        """Clear prompt feature-profile entries when the render scope changes."""

        if self._prompt_feature_profile_cache_scope_key == scope_key:
            return
        previous_entry_count = len(self._prompt_feature_profile_cache)
        self._prompt_feature_profile_cache_scope_key = scope_key
        self._prompt_feature_profile_cache = {}
        log_panel_projection_event(
            "prompt_context.profile_cache_reset",
            previous_entry_count=previous_entry_count,
        )

    def _prompt_feature_profile_cache_entry_key(
        self,
        *,
        workflow_context: WorkflowPromptContext,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> tuple[Hashable, ...]:
        """Return the cache key for one resolved prompt feature profile."""

        return (
            workflow_context.cache_token,
            cube_alias or "",
            prompt_node_name,
            prompt_field_key,
            self._normalized_prompt_field_style_token(field_style),
        )

    def _normalized_prompt_field_style_token(
        self,
        value: object,
    ) -> Hashable:
        """Return a deterministic hashable token for prompt field style data."""

        if value is None or isinstance(value, bool | int | float | str):
            return value
        if isinstance(value, Mapping):
            return tuple(
                (str(key), self._normalized_prompt_field_style_token(item))
                for key, item in sorted(
                    value.items(),
                    key=lambda current: str(current[0]),
                )
            )
        if isinstance(value, tuple | list):
            return tuple(
                self._normalized_prompt_field_style_token(item) for item in value
            )
        if isinstance(value, set | frozenset):
            return tuple(
                sorted(
                    (self._normalized_prompt_field_style_token(item) for item in value),
                    key=repr,
                )
            )
        return repr(value)


__all__ = [
    "EditorPanelPromptContextController",
    "EditorPanelPromptContextHost",
    "PanelBehaviorRefreshTransaction",
    "PromptWorkflowCubeSnapshot",
]
