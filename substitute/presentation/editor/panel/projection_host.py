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

"""Expose projection lifecycle operations through the mounted editor panel."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.shared.logging.logger import get_logger, log_debug

from .cube_section_build_session import CubeSectionBuildSession
from .projection_session_models import InsertCompletionPhase
from .projection_surface_state import EditorSurfaceProjectionSignature
from .runtime_access import (
    cube_registry_for_panel,
    projection_coordinator_for_panel,
    projection_stack_order,
)
from .widgets.cube_section_builder import (
    CubeSectionWidgetParts,
    cube_section_builder_for_panel,
)

_LOGGER = get_logger("presentation.editor.panel.projection_host")


class EditorPanelProjectionHost:
    """Provide the panel-facing projection and cube registry lifecycle API."""

    def reorder_cube_widgets(self) -> None:
        """Reattach persistent cube widgets in active stack order."""

        projection_coordinator_for_panel(self).reorder_cube_widgets()

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> EditorSurfaceProjectionSignature:
        """Return the structural signature required by a full projection."""

        return projection_coordinator_for_panel(self).current_projection_signature(
            workflow_id=workflow_id,
            cube_entries=cube_entries,
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def is_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> bool:
        """Return whether the surface already renders the signature."""

        return projection_coordinator_for_panel(self).is_projection_clean(signature)

    def mark_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> None:
        """Record that the surface fully renders the supplied signature."""

        projection_coordinator_for_panel(self).mark_projection_clean(signature)

    def invalidate_projection(self, *, reason: str) -> None:
        """Mark the surface as requiring full projection before reuse."""

        projection_coordinator_for_panel(self).invalidate_projection(reason=reason)

    def refresh_clean_projection(
        self,
        *,
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Refresh cheap active-state affordances for a clean surface."""

        projection_coordinator_for_panel(self).refresh_clean_projection(
            cube_states=cube_states,
            stack_order=stack_order,
        )

    def load_all_cubes(
        self,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: dict[str, object] | None = None,
        stack_order: Sequence[str] | None = None,
        projection_signature: EditorSurfaceProjectionSignature | None = None,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Reconcile rendered cube widgets to latest workflow state."""

        panel: Any = self
        coordinator = projection_coordinator_for_panel(self)
        panel._preset_context_refresh.begin_projection(
            cube_entries=cube_entries,
            cube_states=cube_states,
            stack_order=projection_stack_order(
                stack_order=stack_order,
                cube_states=cube_states,
            ),
        )

        def projection_completed() -> None:
            """Refresh preset consumers after projection records model fields."""

            panel._preset_context_refresh.refresh(reason="workflow_projection_loaded")
            if on_complete is not None:
                on_complete()

        coordinator.load_all_cubes(
            cube_entries,
            cube_states=cube_states,
            stack_order=stack_order,
            projection_signature=projection_signature,
            on_complete=projection_completed,
        )

    def mark_cube_sections_stale(
        self,
        cube_aliases: Sequence[str],
        *,
        reason: str,
    ) -> bool:
        """Mark rendered cube sections stale before targeted replacement."""

        return projection_coordinator_for_panel(self).mark_cube_sections_stale(
            cube_aliases,
            reason=reason,
        )

    def has_pending_visible_projection_commit(self) -> bool:
        """Return whether a background projection awaits visible reveal."""

        return projection_coordinator_for_panel(
            self
        ).has_pending_visible_projection_commit()

    def finalize_pending_visible_projection(self) -> bool:
        """Reveal a completed background projection when this panel is active."""

        return projection_coordinator_for_panel(
            self
        ).finalize_pending_visible_projection()

    def is_projection_active(self) -> bool:
        """Return whether the panel still owns full-projection work."""

        return projection_coordinator_for_panel(self).is_projection_active()

    def insert_cube_section(
        self,
        cube_alias: str,
        cube_state: object,
        cube_states: dict[str, object] | None = None,
        stack_order: Sequence[str] | None = None,
        on_complete: Callable[[], None] | None = None,
        completion_phase: InsertCompletionPhase = "first_usable",
    ) -> None:
        """Insert one cube section without rebuilding existing sections."""

        panel: Any = self
        coordinator = projection_coordinator_for_panel(self)
        panel._preset_context_refresh.begin_cube_projection(
            cube_alias=cube_alias,
            cube_state=cube_state,
            stack_order=projection_stack_order(
                stack_order=stack_order,
                cube_states=cube_states,
            ),
        )

        def cube_projection_completed() -> None:
            """Refresh preset consumers after incremental projection."""

            panel._preset_context_refresh.refresh(reason="cube_section_inserted")
            if on_complete is not None:
                on_complete()

        coordinator.insert_cube(
            cube_alias,
            cube_state,
            cube_states=cube_states,
            stack_order=stack_order,
            on_complete=cube_projection_completed,
            completion_phase=completion_phase,
        )

    def remove_cube(self, route_key: str) -> None:
        """Remove one cube section from the live editor surface."""

        panel: Any = self
        projection_coordinator_for_panel(self).remove_cube(route_key)
        panel._preset_context_refresh.remove_cube(route_key)

    def rename_cube(self, old_key: str, new_key: str) -> None:
        """Rename one cube across registries and live link controls."""

        panel: Any = self
        projection_coordinator_for_panel(self).rename_cube(old_key, new_key)
        panel._preset_context_refresh.rename_cube(old_key, new_key)

    def refresh_cube_header(self, alias: str) -> None:
        """Refresh one cube title from workflow-owned state."""

        cube_registry_for_panel(self).refresh_cube_header(alias)

    def clear_layout(self) -> None:
        """Dispose rendered cubes and reset panel tracking maps."""

        projection_coordinator_for_panel(self).clear_layout()

    def _remove_cube_widget_from_layout(self, widget: QWidget | None) -> None:
        """Detach and dispose one cube widget, then prune dead link controls."""

        if widget is None:
            return
        panel: Any = self
        log_debug(
            _LOGGER,
            "Removing cube widget from editor layout",
            widget_type=type(widget).__name__,
        )
        widget.setParent(None)
        widget.deleteLater()
        cleanup_dead_node_link_widgets = getattr(
            panel.meta_registry,
            "cleanup_dead_node_link_widgets",
            None,
        )
        if callable(cleanup_dead_node_link_widgets):
            cleanup_dead_node_link_widgets()

    def _build_cube_widget(self, route_key: str, cube_state: object) -> object:
        """Build one cube widget through projection-owned lifecycle."""

        return projection_coordinator_for_panel(self).build_cube_widget(
            route_key,
            cube_state,
        )

    def _begin_build_cube_widget(
        self,
        route_key: str,
        cube_state: object,
    ) -> CubeSectionBuildSession:
        """Return an incremental cube-section build session."""

        return projection_coordinator_for_panel(self).begin_build_cube_widget(
            route_key,
            cube_state,
        )

    def _prepare_cube_section_widget(
        self,
        route_key: str,
    ) -> CubeSectionWidgetParts:
        """Build passive cube-section widgets for projection sessions."""

        panel: Any = self
        builder = getattr(panel, "_cube_section_builder", None)
        if builder is None:
            builder = cube_section_builder_for_panel(panel)
            setattr(panel, "_cube_section_builder", builder)
        return builder.build_cube_section(route_key)

    def _begin_projection_busy(self, message: str = "Loading") -> object | None:
        """Begin shell-owned busy presentation for staged projection."""

        mainwindow = getattr(self, "mainwindow", None)
        editor_busy = getattr(mainwindow, "editor_busy", None)
        begin_busy = getattr(editor_busy, "begin", None)
        workflow_session_service = getattr(mainwindow, "workflow_session_service", None)
        workflow_id = str(getattr(workflow_session_service, "active_workflow_id", ""))
        if not workflow_id or not callable(begin_busy):
            return None
        return cast(object, begin_busy(workflow_id, message=message))

    def _end_projection_busy(self, token: object | None) -> None:
        """End shell-owned busy presentation for staged projection."""

        if token is None:
            return
        mainwindow = getattr(self, "mainwindow", None)
        editor_busy = getattr(mainwindow, "editor_busy", None)
        end_busy = getattr(editor_busy, "end", None)
        if callable(end_busy):
            end_busy(token)

    def register_card_wrapper(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Register the current live wrapper for one cube node card."""

        cube_registry_for_panel(self).register_card_wrapper(
            cube_alias,
            node_name,
            wrapper,
        )

    def remove_card_wrapper_if_current(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Remove a card wrapper while it still owns the registry entry."""

        cube_registry_for_panel(self).remove_card_wrapper_if_current(
            cube_alias,
            node_name,
            wrapper,
        )


__all__ = ["EditorPanelProjectionHost"]
