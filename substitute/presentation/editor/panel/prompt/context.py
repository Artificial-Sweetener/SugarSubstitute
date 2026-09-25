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
from substitute.application.prompt_editor.lora.effective_provider import (
    ScheduledLoraProvider,
    WorkflowPromptContext,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.panel.behavior_snapshot_controller import (
    BehaviorSnapshotController,
    BehaviorSnapshotHost,
)
from substitute.presentation.editor.panel.prompt.profile_policy import (
    PanelPromptFieldProfileDecision,
)
from substitute.presentation.editor.panel.projection_observability import (
    log_panel_projection_event,
)

from .feature_profile_resolver import (
    PromptFeatureProfileResolver,
    PromptFeatureProfileServiceProtocol,
)
from .scheduled_lora_adapter import build_scheduled_lora_resolver


@dataclass(frozen=True, slots=True)
class PromptWorkflowCubeSnapshot:
    """Store immutable cube data used by projection-scope prompt analysis."""

    cube_id: str
    version: str
    buffer: Mapping[str, object]
    display_name: str
    ui: Mapping[str, object] | None


class EditorPanelPromptContextHost(Protocol):
    """Describe panel state needed to prepare prompt context snapshots."""

    scheduled_lora_provider: ScheduledLoraProvider | None
    prompt_feature_profile_service: PromptFeatureProfileServiceProtocol | None
    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    _last_behavior_snapshot: EditorBehaviorSnapshot | None

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides for prompt context cache keys."""


class EditorPanelPromptContextController:
    """Prepare prompt workflow context and feature-profile state for a panel."""

    def __init__(self, host: EditorPanelPromptContextHost) -> None:
        """Store the host and initialize prompt-context caches."""

        self._host = host
        self.behavior = BehaviorSnapshotController(cast(BehaviorSnapshotHost, host))
        self._workflow_prompt_context_cache_key: tuple[Hashable, ...] | None = None
        self._workflow_prompt_context_cache: WorkflowPromptContext | None = None
        self._projection_prompt_context: WorkflowPromptContext | None = None
        self._feature_profiles = PromptFeatureProfileResolver(
            cast(
                PromptFeatureProfileServiceProtocol | None,
                getattr(host, "prompt_feature_profile_service", None),
            )
        )

    @property
    def projection_prompt_context(self) -> WorkflowPromptContext | None:
        """Return the active projection-scoped prompt context when present."""

        return self._projection_prompt_context

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
        self._feature_profiles.reset_scope_if_needed(context.cache_token)
        log_panel_projection_event(
            "prompt_context.projection_begin",
            reason=reason,
            cube_count=len(context.cube_states),
            stack_order_count=len(context.stack_order),
            override_count=len(context.workflow_overrides),
            behavior_snapshot_present=context.behavior_snapshot is not None,
            cache_entry_count=self._feature_profiles.entry_count,
        )

    def clear_projection_prompt_context(self, *, reason: str) -> None:
        """Clear projection-scoped prompt state before live editing resumes."""

        previous_cache_entries = self._feature_profiles.clear()
        projection_context_present = self._projection_prompt_context is not None
        self._projection_prompt_context = None
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
        return build_scheduled_lora_resolver(
            provider=provider,
            workflow_context=workflow_context,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
        )

    def prompt_feature_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PromptEditorFeatureProfile | None:
        """Return the resolved prompt feature profile for one prompt field."""

        source = "projection" if self._projection_prompt_context is not None else "live"
        workflow_context = self.prompt_workflow_context_for_feature_profiles()
        return self._feature_profiles.resolve(
            workflow_context=workflow_context,
            context_source=source,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
            field_style=field_style,
        )

    def prompt_field_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Return prepared feature and syntax profiles for one prompt field."""

        source = "projection" if self._projection_prompt_context is not None else "live"
        return self._feature_profiles.prepare_field_profile(
            workflow_context=self.prompt_workflow_context_for_feature_profiles(),
            context_source=source,
            cube_alias=cube_alias,
            prompt_node_name=prompt_node_name,
            prompt_field_key=prompt_field_key,
            field_style=field_style,
        )


__all__ = [
    "EditorPanelPromptContextController",
    "EditorPanelPromptContextHost",
    "PromptWorkflowCubeSnapshot",
]
