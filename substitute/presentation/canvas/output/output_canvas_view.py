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

"""Render output canvas widget and output-tab interaction affordances."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

from qpane import QPane
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputPreviewCloseIdentity,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewAcceptance,
    OutputPreviewRegistry,
)
from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey as _PreviewSlotKey,  # noqa: F401
    ScenePreviewSlot as _ScenePreviewSlot,  # noqa: F401
    SourcePreviewSlotKey as _SourcePreviewSlotKey,  # noqa: F401
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareState,
)
from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    OutputRouteProjectorPort,
    OutputRouteScope as _OutputRouteScope,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)
from substitute.presentation.canvas.shared.canvas_zoom_indicator import (
    CanvasZoomIndicator,
)
from substitute.presentation.canvas.qpane.canvas_pane_catalog import CanvasPaneCatalog
from substitute.presentation.canvas.output.output_canvas_chrome import (
    install_output_navigation_chrome_theme_refresh,
)
from substitute.presentation.canvas.output.composition.runtime import (
    compose_output_canvas_runtime,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    install_output_preview_registry,
    output_preview_registry,
    output_revision_cache,
)
from substitute.presentation.canvas.output.output_canvas_preview_retirement import (
    retire_output_preview_id,
    retire_output_previews_for_completed_slot,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
    visible_output_source_groups_by_key,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_navigation_widgets import (
    create_output_navigation_widgets,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta

OutputRouteScope = _OutputRouteScope
_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28


class OutputCanvas(QWidget):
    """Host output QPane with overlay tabs and external-editor context actions."""

    activeOutputChanged = Signal(str)
    activeOutputGridChanged = Signal(str)
    activeOutputSceneChanged = Signal(object)
    activeOutputCompareChanged = Signal(object)
    dockActionRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        preview_registry: OutputPreviewRegistry,
        open_single_external_editor: (
            Callable[[object, OutputImageMeta], bool] | None
        ) = None,
        open_all_external_editor: (
            Callable[[list[tuple[object, OutputImageMeta]]], bool] | None
        ) = None,
        reveal_output_asset: Callable[[OutputImageMeta], bool] | None = None,
        final_output_payload_lookup: Callable[[UUID], object | None] | None = None,
        final_output_metadata_lookup: (
            Callable[[UUID], OutputImageMeta | None] | None
        ) = None,
        route_session_boundary: CanvasRouteSessionBoundaryPort | None = None,
    ) -> None:
        """Initialize output pane, segmented tab overlay, and context-menu actions."""

        super().__init__(parent)
        self._unscoped_preview_image_id = uuid4()
        self.setStyleSheet("border: none; background-color: transparent;")
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setMouseTracking(True)
        self._open_single_external_editor = open_single_external_editor
        self._open_all_external_editor = open_all_external_editor
        self._reveal_output_asset = reveal_output_asset
        self._dock_action_text = "Undock canvas"

        self.active_source_key: str | None = None
        self.active_scene_key: str | None = None
        self.active_scene_overview = False
        self.scene_count = 0
        self.active_set_index = 1
        self.last_real_set_index = 1
        self.set_count = 0
        self._suppress_tab_change = False
        self._grid_click_press_pos: QPoint | None = None
        self._revision_cache_key: tuple[str, int] | None = None
        self._preview_registry = preview_registry
        self._revision_cache: object | None = None
        self._visible_compare_state = OutputCompareState()
        self._output_projection: OutputCanvasProjection | None = None

        self.pane = QPane()
        self._zoom_indicator = CanvasZoomIndicator(self.pane)
        self.pane.setControlMode(QPane.CONTROL_MODE_PANZOOM)
        pane_layout = QVBoxLayout(self)
        pane_layout.setContentsMargins(0, 0, 0, 0)
        pane_layout.setSpacing(0)
        pane_layout.addWidget(self.pane)

        navigation_widgets = create_output_navigation_widgets(
            self,
            scene_selector_min_width=_SCENE_SELECTOR_MIN_WIDTH,
            source_selector_min_width=_SOURCE_SELECTOR_MIN_WIDTH,
        )
        self.tabbar_container = navigation_widgets.tabbar_container
        self.tabbar_bg = navigation_widgets.tabbar_bg
        self.scene_selector_button = navigation_widgets.scene_selector_button
        self.set_selector_button = navigation_widgets.set_selector_button
        self.source_selector_button = navigation_widgets.source_selector_button
        self.tabbar = navigation_widgets.tabbar
        self._set_picker = navigation_widgets.set_picker
        self._scene_picker = navigation_widgets.scene_picker
        self._source_picker = navigation_widgets.source_picker
        self.comparison_nav_container = navigation_widgets.comparison_nav_container
        self.comparison_nav_bg = navigation_widgets.comparison_nav_bg
        self.comparison_scene_selector_button = (
            navigation_widgets.comparison_scene_selector_button
        )
        self.comparison_set_selector_button = (
            navigation_widgets.comparison_set_selector_button
        )
        self.comparison_source_selector_button = (
            navigation_widgets.comparison_source_selector_button
        )
        self._source_tabs_collapsed = False
        self._source_tabbar_preferred_width = 0
        self._source_tab_cache_signature: tuple[tuple[str, str], ...] | None = None
        self._source_tab_tooltip_filters: dict[str, object] = {}
        self._projection_workflow_id = ""

        self._runtime = compose_output_canvas_runtime(
            self,
            final_output_payload_lookup=final_output_payload_lookup,
            final_output_metadata_lookup=final_output_metadata_lookup,
            route_session_boundary=route_session_boundary,
        )
        install_output_navigation_chrome_theme_refresh(
            host=self,
            base_background=self.tabbar_bg,
            comparison_background=self.comparison_nav_bg,
        )
        update_output_tabbar_container(self)
        self.pane.installEventFilter(self)

    def set_final_output_lookup(
        self,
        *,
        payload_lookup: Callable[[UUID], object | None],
        metadata_lookup: Callable[[UUID], OutputImageMeta | None],
    ) -> None:
        """Install registry-backed final-output lookup callbacks."""

        self._runtime.core.asset_lookup.set_final_output_lookup(
            payload_lookup=payload_lookup,
            metadata_lookup=metadata_lookup,
        )

    def set_preview_registry(self, registry: OutputPreviewRegistry) -> None:
        """Install the application-owned transient preview registry."""

        install_output_preview_registry(self, registry)

    @property
    def route_projector(self) -> OutputRouteProjectorPort:
        """Return the single Output display route projector for this QPane."""

        return self._runtime.core.route_projector

    @property
    def qpane_catalog(self) -> CanvasPaneCatalog:
        """Return the shared catalog adapter for this output QPane instance."""

        return self._runtime.core.qpane_catalog

    def apply_preview_acceptance(
        self,
        acceptance: OutputPreviewAcceptance,
    ) -> None:
        """Apply a session-authorized preview acceptance to QPane catalog/routes."""

        self._runtime.preview.controller.apply_preview_acceptance(acceptance)

    def close_final_output_preview_lane(
        self,
        identity: OutputPreviewCloseIdentity,
    ) -> None:
        """Retire the active preview lane replaced by a final output."""

        self._runtime.preview.controller.close_final_output_preview_lane(identity)

    def clear_previews(
        self,
        source_key: str | None = None,
    ) -> None:
        """Remove transient preview catalog entries for one source or all sources."""

        self._runtime.preview.controller.clear_previews(source_key)

    def set_dock_action_text(self, text: str) -> None:
        """Set the context-menu label for the manager-owned dock action."""

        self._dock_action_text = text

    def bind_projection_session(
        self,
        session: OutputCanvasSession,
    ) -> None:
        """Bind one projection session and render its authorized Output route."""

        self._runtime.projection.controller.bind_projection_session(
            session,
            retire_completed_preview_slot=lambda slot_key, source_label, reason: (
                retire_output_previews_for_completed_slot(
                    self,
                    slot_key,
                    source_label=source_label,
                    retire_reason=reason,
                )
            ),
        )
        viewport = self.pane.currentViewportRect()
        self._runtime.grid.reflow.present_current_grid(
            CanvasViewportExtent(viewport.width(), viewport.height())
        )

    def eventFilter(self, watched: object, event: object) -> bool:
        """Open batch-grid tiles from pane clicks while preserving pane delivery."""

        return self._runtime.grid.event_controller.handle_event_filter(watched, event)

    def resizeEvent(self, event: object) -> None:
        """Update tabbar overlay geometry when output canvas is resized."""

        update_output_tabbar_container(self)
        super().resizeEvent(event)


__all__ = [
    "OutputCanvas",
    "output_preview_registry",
    "output_revision_cache",
    "output_route_state_snapshot",
    "output_scene_groups_by_key",
    "retire_output_preview_id",
    "retire_output_previews_for_completed_slot",
    "visible_output_source_groups_by_key",
]
