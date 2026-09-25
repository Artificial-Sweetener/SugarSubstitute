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

"""Expose behavior snapshots and prompt context through the editor panel host."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.prompt_editor.lora.effective_provider import (
    WorkflowPromptContext,
)
from substitute.application.prompt_editor.lora.scheduled import PromptScheduledLora
from substitute.domain.prompt.features.models import PromptEditorFeatureProfile
from substitute.presentation.editor.panel.prompt.context import (
    EditorPanelPromptContextController,
    PromptWorkflowCubeSnapshot,
)
from substitute.presentation.editor.panel.prompt.profile_policy import (
    PanelPromptFieldProfileDecision,
)
from substitute.shared.logging.logger import get_logger, log_warning

from .runtime_access import search_controller_for_panel

_LOGGER = get_logger("presentation.editor.panel.behavior_context_host")


class EditorPanelBehaviorContextHost:
    """Provide the mounted host API for behavior and prompt-context ownership."""

    _prompt_context_controller: EditorPanelPromptContextController
    _workflow_id: str

    def _get_active_buffer(self) -> object:
        """Return the active workflow buffer snapshot used for editor refreshes."""

        try:
            last_buffer = getattr(self, "_last_buffer", None)
            if last_buffer is not None:
                return last_buffer
            return {}
        except AttributeError as error:
            log_warning(
                _LOGGER,
                "Failed to read active editor buffer",
                error_type=type(error).__name__,
            )
            return {}

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return this panel's workflow overrides for behavior snapshots."""

        workflow_overrides = None
        try:
            mainwindow = getattr(self, "mainwindow", None)
            session_service = getattr(mainwindow, "workflow_session_service", None)
            workflows = getattr(session_service, "workflows", None)
            workflow = (
                workflows.get(self._workflow_id)
                if isinstance(workflows, Mapping) and self._workflow_id
                else None
            )
            get_active_workflow = getattr(mainwindow, "get_active_workflow", None)
            if workflow is None and callable(get_active_workflow):
                workflow = get_active_workflow()
            workflow_overrides = getattr(workflow, "global_overrides", None)
        except (AttributeError, RuntimeError, TypeError) as error:
            log_warning(
                _LOGGER,
                "Failed to read workflow overrides for behavior snapshot",
                error_type=type(error).__name__,
            )
            workflow_overrides = None
        return workflow_overrides if isinstance(workflow_overrides, Mapping) else {}

    def _build_behavior_snapshot(
        self,
        *,
        search_hidden_keys: set[object] | None = None,
        override_hidden_field_keys: set[object] | None = None,
        node_search_text: str | None = None,
        search_matching_nodes: set[tuple[str, str]] | None = None,
    ) -> EditorBehaviorSnapshot | None:
        """Resolve and cache the current node-behavior snapshot."""

        return self._prompt_context_controller.behavior.build(
            search_hidden_keys=search_hidden_keys,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=node_search_text,
            search_matching_nodes=search_matching_nodes,
        )

    def begin_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Start an explicit behavior snapshot reuse boundary."""

        self._prompt_context_controller.behavior.begin(reason=reason)

    def end_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Complete the active behavior snapshot reuse boundary."""

        self._prompt_context_controller.behavior.end(reason=reason)

    def invalidate_behavior_refresh_transaction(self, *, reason: str) -> None:
        """Drop the active behavior transaction before state changes."""

        self._prompt_context_controller.behavior.invalidate(reason=reason)

    def _behavior_snapshot_reuse_key(
        self,
        *,
        workflow_overrides: Mapping[str, object],
        search_hidden_keys: set[object] | None,
        override_hidden_field_keys: set[object] | None,
        node_search_text: str | None,
        search_matching_nodes: set[tuple[str, str]] | None,
    ) -> tuple[Hashable, ...]:
        """Return the identity key that makes transaction reuse safe."""

        return self._prompt_context_controller.behavior.reuse_key(
            workflow_overrides=workflow_overrides,
            search_hidden_keys=search_hidden_keys,
            override_hidden_field_keys=override_hidden_field_keys,
            node_search_text=node_search_text,
            search_matching_nodes=search_matching_nodes,
        )

    def current_behavior_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Return the latest behavior snapshot for external rendering."""

        return self._prompt_context_controller.behavior.current()

    def set_current_behavior_snapshot(
        self,
        snapshot: EditorBehaviorSnapshot | None,
    ) -> None:
        """Publish the latest behavior snapshot through context ownership."""

        self._prompt_context_controller.behavior.set_current(snapshot)

    def workflow_prompt_context(self) -> WorkflowPromptContext:
        """Return current workflow context for prompt-field resolvers."""

        return self._prompt_context_controller.workflow_prompt_context()

    def begin_projection_prompt_context(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> None:
        """Capture immutable prompt-analysis state for one projection."""

        self._prompt_context_controller.begin_projection_prompt_context(
            cube_states=cube_states,
            stack_order=stack_order,
            reason=reason,
        )

    def clear_projection_prompt_context(self, *, reason: str) -> None:
        """Clear projection-scoped prompt state before live editing resumes."""

        self._prompt_context_controller.clear_projection_prompt_context(reason=reason)

    def _build_projection_prompt_context(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
        reason: str,
    ) -> WorkflowPromptContext:
        """Return prompt context detached from live cube mutation."""

        return self._prompt_context_controller.build_projection_prompt_context(
            cube_states=cube_states,
            stack_order=stack_order,
            reason=reason,
        )

    def _snapshot_prompt_cube_states(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> dict[str, PromptWorkflowCubeSnapshot]:
        """Return cube snapshots whose buffers do not alias live state."""

        return self._prompt_context_controller.snapshot_prompt_cube_states(
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def _snapshot_prompt_workflow_overrides(self) -> Mapping[str, object]:
        """Return workflow overrides detached from live mutation."""

        return self._prompt_context_controller.snapshot_prompt_workflow_overrides()

    def _prompt_workflow_context_for_feature_profiles(self) -> WorkflowPromptContext:
        """Return active prompt context for feature-profile resolution."""

        return self._prompt_context_controller.prompt_workflow_context_for_feature_profiles()

    def _workflow_prompt_context_key(
        self,
        workflow_overrides: Mapping[str, object],
    ) -> tuple[Hashable, ...]:
        """Return the refresh-scoped prompt workflow context key."""

        return self._prompt_context_controller.workflow_prompt_context_key(
            workflow_overrides
        )

    def scheduled_lora_resolver_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
    ) -> Callable[[str], tuple[PromptScheduledLora, ...]] | None:
        """Return a resolver callable bound to one prompt field context."""

        return self._prompt_context_controller.scheduled_lora_resolver_for_prompt(
            cube_alias,
            prompt_node_name,
            prompt_field_key,
        )

    def prompt_feature_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PromptEditorFeatureProfile | None:
        """Return the resolved prompt feature profile for one field."""

        return self._prompt_context_controller.prompt_feature_profile_for_prompt(
            cube_alias,
            prompt_node_name,
            prompt_field_key,
            field_style,
        )

    def prompt_field_profile_for_prompt(
        self,
        cube_alias: str | None,
        prompt_node_name: str,
        prompt_field_key: str,
        field_style: Mapping[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Return prepared prompt feature and syntax profiles for one field."""

        return self._prompt_context_controller.prompt_field_profile_for_prompt(
            cube_alias,
            prompt_node_name,
            prompt_field_key,
            field_style,
        )

    def build_search_corpus_snapshot(self) -> EditorBehaviorSnapshot | None:
        """Build the unfiltered authoritative search corpus snapshot."""

        return search_controller_for_panel(self).build_search_corpus_snapshot()


__all__ = ["EditorPanelBehaviorContextHost"]
