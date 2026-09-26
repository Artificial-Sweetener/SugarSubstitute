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

"""Synchronize editor link selectors and prompt fields with workflow state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtWidgets import QWidget

from substitute.application.overrides import SamplerSchedulerLinkStateService
from substitute.application.workflows import NodeLinkIdentity
from substitute.shared.logging.logger import get_logger, log_debug

from .factories.meta_factories import (
    sanitize_sampler_link_selection,
    sanitize_scheduler_link_selection,
)
from .runtime_access import cube_registry_for_panel, field_state_controller_for_panel

_LOGGER = get_logger("presentation.editor.panel.link_synchronization")


class EditorPanelLinkSynchronization:
    """Provide link and prompt synchronization through the panel host API."""

    def _ordered_buffers(self) -> dict[str, dict[str, object]]:
        """Return workflow buffers in current stack order for link refreshes."""

        return cube_registry_for_panel(self).ordered_buffers()

    def _refresh_sampler_scheduler_link_state(self) -> None:
        """Refresh sampler and scheduler link metadata using one shared path."""

        panel: Any = self
        all_buffers = self._ordered_buffers()
        if not all_buffers:
            return
        current_behavior_snapshot = getattr(panel, "current_behavior_snapshot", None)
        if not callable(current_behavior_snapshot):
            log_debug(
                _LOGGER,
                "Skipped sampler/scheduler link refresh without snapshot accessor",
            )
            return
        behavior_snapshot = current_behavior_snapshot()
        if behavior_snapshot is None:
            log_debug(
                _LOGGER,
                "Skipped sampler/scheduler link refresh without behavior snapshot",
            )
            return
        link_snapshot = SamplerSchedulerLinkStateService().build_snapshot(
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            stack_order=panel._stack_order,
        )
        sanitize_sampler_link_selection(
            all_buffers,
            link_snapshot.sampler_option_map(),
        )
        sanitize_scheduler_link_selection(
            all_buffers,
            link_snapshot.scheduler_option_map(),
        )

    def sanitize_prompt_link_state(self) -> None:
        """Normalize prompt-link groups against current editor stack order."""

        panel: Any = self
        panel._workflow_link_reconciliation_service.sanitize_current_state(
            cube_states=panel._cube_states,
            stack_order=panel._stack_order,
        )

    def reconcile_prompt_link_state(
        self,
        *,
        previous_cube_states: Mapping[str, object] | None,
        previous_stack_order: list[str] | None,
        cube_states: Mapping[str, object] | None,
        stack_order: list[str] | None,
    ) -> None:
        """Reconcile prompt links across one cube-load or reorder transition."""

        panel: Any = self
        panel._workflow_link_reconciliation_service.reconcile_transition(
            previous_cube_states=previous_cube_states,
            previous_stack_order=previous_stack_order,
            current_cube_states=cube_states,
            current_stack_order=stack_order,
        )

    def apply_manual_node_link_selection(
        self,
        cube_alias: str,
        identity: NodeLinkIdentity,
        from_cube: str | None,
        from_node: str | None,
    ) -> None:
        """Apply one whole-node link selection through the link service."""

        panel: Any = self
        if not panel._stack_order or not panel._cube_states:
            return
        panel._workflow_link_reconciliation_service.apply_manual_node_selection(
            cube_states=panel._cube_states,
            stack_order=list(panel._stack_order),
            cube_alias=cube_alias,
            identity=identity,
            from_cube=from_cube,
            from_node=from_node,
        )

    def _refresh_link_widgets(self) -> None:
        """Refresh node, sampler, and scheduler link widgets."""

        panel: Any = self
        update_node_link_widgets = getattr(
            panel.meta_registry,
            "update_node_link_widgets",
            None,
        )
        if callable(update_node_link_widgets):
            update_node_link_widgets()
        panel.meta_registry.update_sampler_link_widgets()
        panel.meta_registry.update_scheduler_link_widgets()

    def refresh_link_widgets_for_cube(self, cube_alias: str) -> None:
        """Refresh stack-wide node links and cube-scoped scalar links."""

        panel: Any = self
        panel.meta_registry.update_node_link_widgets()
        panel.meta_registry.update_sampler_link_widgets_for_cube(cube_alias)
        panel.meta_registry.update_scheduler_link_widgets_for_cube(cube_alias)

    def sync_prompt_editor_values_from_buffers(self) -> None:
        """Restore prompt editors from authoritative workflow buffers."""

        field_state_controller_for_panel(self).sync_prompt_editor_values_from_buffers()

    def sync_prompt_editor_values_for_cube(self, cube_alias: str) -> None:
        """Restore prompt editors for one cube from workflow buffers."""

        field_state_controller_for_panel(self).sync_prompt_editor_values_for_cube(
            cube_alias
        )

    def _sync_prompt_editor_values_for_widget(self, cube_widget: QWidget) -> None:
        """Restore prompt editors mounted under one cube widget."""

        field_state_controller_for_panel(self).sync_prompt_editor_values_for_widget(
            cube_widget
        )


__all__ = ["EditorPanelLinkSynchronization"]
