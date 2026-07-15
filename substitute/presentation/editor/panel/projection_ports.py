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

"""Define editor projection ports shared by coordinator collaborators."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Mapping as MappingABC, Sequence
from typing import Protocol

from substitute.application.node_behavior import (
    LiveNodeDefinitionError,
    ResolvedFieldSpec,
)
from substitute.application.workflows import CubeRuntimeIssueSource

from .projection_preparation import BehaviorRefreshReason


class WidgetProtocol(Protocol):
    """Describe the widget methods used during editor refreshes."""

    def setParent(self, parent: object | None) -> None:
        """Detach the widget from its current parent."""

    def deleteLater(self) -> None:
        """Schedule the widget for Qt-owned deletion."""


class CubeSectionSessionWidgetProtocol(WidgetProtocol, Protocol):
    """Describe cube-section widget methods used by build sessions."""

    def defer_update_cube_height(self) -> None:
        """Schedule a cube-section height refresh."""

    def defer_string_line_edit_width_group_sync(self) -> None:
        """Schedule a cube-section string-width sync."""


class LayoutItemProtocol(Protocol):
    """Describe layout-item access used during reattachment."""

    def widget(self) -> object | None:
        """Return the contained widget when present."""

    def spacerItem(self) -> object | None:
        """Return the spacer marker when present."""

    def layout(self) -> object | None:
        """Return the nested layout when present."""


class LayoutProtocol(Protocol):
    """Describe the layout surface used by the refresh coordinator."""

    def count(self) -> int:
        """Return number of items currently tracked by the layout."""

    def takeAt(self, index: int) -> LayoutItemProtocol:
        """Remove and return one layout item."""

    def itemAt(self, index: int) -> LayoutItemProtocol:
        """Return one layout item without removing it."""

    def addSpacing(self, spacing: int) -> None:
        """Append one spacing item to the layout."""

    def addWidget(self, widget: object) -> None:
        """Append one widget to the layout."""


class SignalProtocol(Protocol):
    """Describe the signal methods used by the scroll tracking refresh."""

    def connect(self, callback: Callable[[int], None]) -> None:
        """Connect one callback."""

    def disconnect(self, callback: Callable[[int], None]) -> None:
        """Disconnect one callback."""


class ScrollBarProtocol(Protocol):
    """Describe the vertical-scrollbar surface used by the coordinator."""

    valueChanged: SignalProtocol

    def value(self) -> int:
        """Return the current scrollbar value."""


class ScrollAreaProtocol(Protocol):
    """Describe the scroll-area access used by the coordinator."""

    def verticalScrollBar(self) -> ScrollBarProtocol:
        """Return the live vertical scrollbar."""


class EditorRefreshPanelProtocol(Protocol):
    """Describe the editor-panel state coordinated during refresh operations."""

    CUBE_SPACING: int
    cube_widgets: dict[str, object]
    cube_sections: dict[str, object]
    cube_headers: dict[str, object]
    card_wrappers: dict[tuple[str, str], object]
    cube_positions: dict[str, object]
    input_widgets_by_field_key: dict[tuple[str, str, str], object]
    row_widgets: dict[object, object]
    col_widgets: dict[object, object]
    node_link_widgets: dict[object, object]
    node_link_title_surfaces: dict[object, object]
    meta_registry: object
    _cube_visibility_btns: dict[str, object]
    _cube_visibility_menus: dict[str, object]
    _cube_states: dict[str, object] | None
    _stack_order: list[str] | None
    _layout: LayoutProtocol
    scroll: ScrollAreaProtocol
    node_definition_gateway: object
    _current_search_hidden_keys: set[object] | None
    _current_search_matching_nodes: set[object] | None
    _current_node_search_text: str | None

    def _refresh_sampler_scheduler_link_state(self) -> None:
        """Refresh sampler and scheduler link metadata."""

    def sanitize_prompt_link_state(self) -> None:
        """Normalize prompt and whole-node link state for the current panel stack order."""

    def reconcile_prompt_link_state(
        self,
        *,
        previous_cube_states: dict[str, object] | None,
        previous_stack_order: list[str] | None,
        cube_states: dict[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Reconcile prompt and whole-node link state across one workflow transition."""

    def _refresh_link_widgets(self) -> None:
        """Refresh prompt, node, sampler, and scheduler link widgets."""

    def refresh_link_widgets_for_cube(self, cube_alias: str) -> None:
        """Refresh link widgets after one cube changes."""

    def sync_prompt_editor_values_from_buffers(self) -> None:
        """Restore prompt-editor widget values from the current workflow buffers."""

    def sync_prompt_editor_values_for_cube(self, cube_alias: str) -> None:
        """Restore prompt-editor widget values for one cube."""

    def _remove_cube_widget_from_layout(self, widget: object) -> None:
        """Detach and dispose one cube widget."""

    def _cube_registry_controller(self) -> object:
        """Return the cube registry controller."""

    def clear_model_field_load_progress(self) -> None:
        """Clear model-load progress from tracked field widgets."""

    def _clear_layout_recursive(self, layout: object) -> None:
        """Delete widgets from one nested layout tree."""

    def _build_cube_widget(self, route_key: str, cube_state: object) -> object:
        """Build one cube widget for a missing alias."""

    def _begin_build_cube_widget(self, route_key: str, cube_state: object) -> object:
        """Begin incremental cube widget construction for a missing alias."""

    def _prepare_cube_section_widget(self, route_key: str) -> object:
        """Build passive cube-section widgets for projection-owned sessions."""

    def _begin_projection_busy(self, message: str = "Loading") -> object | None:
        """Begin shell-owned busy presentation for staged full projection."""

    def _end_projection_busy(self, token: object | None) -> None:
        """End shell-owned busy presentation for staged full projection."""

    def _build_behavior_snapshot(self, **kwargs: object) -> object:
        """Prime the cached behavior snapshot for the current cube state."""

    def _workflow_overrides(self) -> MappingABC[str, object]:
        """Return active workflow override values for projection signatures."""

    def hydrate_node_definitions_for_projection(self, *, reason: str) -> None:
        """Hydrate live node definitions before projection builds widgets."""

    def register_projection_live_node_definition_error(
        self,
        error: LiveNodeDefinitionError,
        *,
        reason: str,
        source: CubeRuntimeIssueSource,
    ) -> bool:
        """Register a cube-attributed live metadata error as recoverable."""

    def clear_projection_runtime_issues(self) -> None:
        """Clear projection-owned cube runtime issues."""

    def cube_runtime_error_aliases(self) -> tuple[str, ...]:
        """Return aliases that should render as errored sections."""

    def _build_error_cube_widget(self, route_key: str, cube_state: object) -> object:
        """Build one error-mode cube widget without unsafe controls."""

    def build_node_card(
        self,
        node_name: str,
        inputs: dict[str, object],
        node_type: str,
        field_specs: Mapping[str, ResolvedFieldSpec],
        cube_state: dict[str, object],
        resolved_behavior: object,
        display_decision: object | None = None,
        *,
        alias: str | None = None,
        parent: object | None = None,
    ) -> object:
        """Build one node card for a cube-section build session."""

    def register_card_wrapper(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Register the current live wrapper for one cube node card."""

    def remove_card_wrapper_if_current(
        self,
        cube_alias: str,
        node_name: str,
        wrapper: object,
    ) -> None:
        """Remove a card wrapper only while it still owns the registry entry."""

    def _on_scroll_updated(self, value: int) -> None:
        """Update current-visible-cube tracking after a scroll change."""

    def refresh_node_behavior_state(
        self,
        *,
        reason: BehaviorRefreshReason = "full_workflow_projection",
        use_cached_snapshot: bool = False,
    ) -> None:
        """Recompute card visibility and enabled state."""
