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

"""Expose cube navigation and search through the mounted panel host API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QWidget

from substitute.application.editor_search import EditorSearchResult

from .cube_registry import EditorCubeRegistry
from .runtime_access import (
    cube_registry_for_panel,
    cube_reveal_controller_for_panel,
    field_sync_controller_for_panel,
    search_controller_for_panel,
)


class EditorPanelNavigationSearchHost:
    """Provide cube reveal, field visibility, and search host callbacks."""

    def clear_search_filters(self) -> None:
        """Clear active search filters through the shared search owner."""

        search_controller_for_panel(self).clear_search_filters()

    def _cube_registry_controller(self) -> EditorCubeRegistry:
        """Return the cube registry controller for this panel host."""

        return cube_registry_for_panel(self)

    def _cube_widget_is_mostly_visible(
        self,
        route_key: str,
        *,
        visibility_threshold: float = 0.65,
    ) -> bool:
        """Return whether the requested cube is already mostly visible."""

        return cube_reveal_controller_for_panel(self).geometry.is_mostly_visible(
            route_key,
            visibility_threshold=visibility_threshold,
        )

    def _cube_reveal_anchor_content_y(self, route_key: str) -> int | None:
        """Return the content-space title anchor for one cube."""

        return cube_reveal_controller_for_panel(self).geometry.anchor_content_y(
            route_key
        )

    def _cube_header_viewport_anchor_y(self) -> int:
        """Return where cube title centers should land in the viewport."""

        return cube_reveal_controller_for_panel(
            self
        ).geometry.header_viewport_anchor_y()

    def _cube_scroll_target_value(self, route_key: str) -> int | None:
        """Return the scroll value that aligns one cube title."""

        return cube_reveal_controller_for_panel(self).geometry.scroll_target_value(
            route_key
        )

    def _cube_scroll_target_content_y(self, route_key: str) -> int | None:
        """Return the unclamped content-space target for one cube."""

        return cube_reveal_controller_for_panel(self).geometry.scroll_target_content_y(
            route_key
        )

    def _emit_current_cube_visible(self, route_key: str) -> None:
        """Emit the visible-cube signal when available."""

        cube_reveal_controller_for_panel(self).emit_current_cube_visible(route_key)

    def scroll_to_cube(
        self,
        route_key: str,
        animated: bool = False,
        duration: int | None = None,
        *,
        only_if_needed: bool = False,
        on_finished: Callable[[], None] | None = None,
    ) -> None:
        """Scroll the panel so the requested cube becomes visible."""

        cube_reveal_controller_for_panel(self).scroll_to_cube(
            route_key,
            animated=animated,
            duration=duration,
            only_if_needed=only_if_needed,
            on_finished=on_finished,
        )

    def reveal_new_cube(self, route_key: str) -> None:
        """Reveal a newly loaded cube with optional navigation."""

        cube_reveal_controller_for_panel(self).reveal_new_cube(route_key)

    def reveal_loaded_cube(self, route_key: str) -> None:
        """Navigate to a loaded cube after layout metrics settle."""

        cube_reveal_controller_for_panel(self).reveal_loaded_cube(route_key)

    def reveal_cube_when_layout_ready(self, route_key: str) -> None:
        """Queue a cube reveal until section geometry is stable."""

        cube_reveal_controller_for_panel(self).reveal_cube_when_layout_ready(route_key)

    def _queue_cube_reveal(self, route_key: str, *, force_navigation: bool) -> None:
        """Queue one cube reveal until scroll metrics are stable."""

        cube_reveal_controller_for_panel(self).queue_cube_reveal(
            route_key,
            force_navigation=force_navigation,
        )

    def _schedule_pending_cube_reveal_metrics_refresh(self) -> None:
        """Request scroll metrics before completing a pending reveal."""

        cube_reveal_controller_for_panel(
            self
        ).schedule_pending_cube_reveal_metrics_refresh()

    def _complete_pending_cube_reveal(self) -> None:
        """Finish a pending reveal after layout and metrics refresh."""

        cube_reveal_controller_for_panel(self).complete_pending_cube_reveal()

    def _cube_section_ready_for_reveal(
        self,
        route_key: str,
        *,
        allow_first_valid: bool = False,
    ) -> bool:
        """Return whether one cube has stable geometry for reveal."""

        return cube_reveal_controller_for_panel(self).cube_section_ready_for_reveal(
            route_key,
            allow_first_valid=allow_first_valid,
        )

    def _cube_reveal_geometry_signature(
        self,
        route_key: str,
    ) -> tuple[int, ...] | None:
        """Return reveal metrics that must stabilize before navigation."""

        return cube_reveal_controller_for_panel(self).geometry.readiness_signature(
            route_key
        )

    def scroll_to_input_widget(
        self,
        widget: QWidget,
        animated: bool = True,
        duration: int | None = None,
    ) -> None:
        """Scroll the panel so one input widget is centered when possible."""

        cube_reveal_controller_for_panel(self).scroll_to_input_widget(
            widget,
            animated=animated,
            duration=duration,
        )

    def set_stack_order(self, stack_order: list[str]) -> None:
        """Update cube order used by navigation and preset context."""

        panel: Any = self
        cube_registry_for_panel(self).set_stack_order(stack_order)
        panel._preset_context_refresh.update_cube_order(stack_order)
        panel._preset_context_refresh.refresh(reason="stack_order_changed")

    def _on_scroll_updated(self, value: int) -> None:
        """Sync the visible cube tab with editor scroll position."""

        cube_reveal_controller_for_panel(self).on_scroll_updated(int(value))

    def update_all_hidden_fields(
        self,
        overrides: object = None,
        search_hidden_keys: set[object] | None = None,
    ) -> None:
        """Recompute hidden fields through field synchronization ownership."""

        field_sync_controller_for_panel(self).update_all_hidden_fields(
            overrides=overrides,
            search_hidden_keys=search_hidden_keys,
        )

    def set_hidden_field_keys(self, hidden_keys: set[object]) -> None:
        """Apply hidden-field visibility through field synchronization."""

        field_sync_controller_for_panel(self).set_hidden_field_keys(hidden_keys)

    def set_search_field_match_keys(
        self,
        match_keys: set[tuple[str, str, str]] | None,
        *,
        active: bool,
    ) -> None:
        """Apply ephemeral field-search matches to row visibility."""

        field_sync_controller_for_panel(self).set_search_field_match_keys(
            match_keys,
            active=active,
        )

    def highlight_inputs_matching(self, text: str) -> None:
        """Highlight prompt-editor matches through search ownership."""

        search_controller_for_panel(self).highlight_inputs_matching(text)

    def apply_search_result(self, result: EditorSearchResult) -> None:
        """Apply one application-owned result to the live panel."""

        search_controller_for_panel(self).apply_search_result(result)

    def filter_node_cards_by_search(self, search_text: str) -> None:
        """Filter node-card visibility through search ownership."""

        search_controller_for_panel(self).filter_node_cards_by_search(search_text)

    def search_and_select(self, search_text: str, direction: str = "next") -> None:
        """Cycle editor search matches through search ownership."""

        search_controller_for_panel(self).search_and_select(
            search_text,
            direction=direction,
        )

    def focus_current_search_match(self) -> None:
        """Focus the current editor search match."""

        search_controller_for_panel(self).focus_current_search_match()


__all__ = ["EditorPanelNavigationSearchHost"]
