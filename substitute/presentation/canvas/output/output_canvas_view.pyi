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

"""Typing surface for the public Output canvas widget API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    OutputRouteProjectorPort,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.presentation.canvas.qpane.canvas_pane_catalog import CanvasPaneCatalog
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.canvas.output.composition.runtime_types import (
    OutputCanvasRuntime,
)

class OutputCanvas(QWidget):
    """Expose host-facing Output canvas widget controls and projection binding."""

    activeOutputChanged: Signal
    activeOutputGridChanged: Signal
    activeOutputSceneChanged: Signal
    activeOutputCompareChanged: Signal
    dockActionRequested: Signal
    pane: Any
    tabbar: Any
    scene_selector_button: Any
    set_selector_button: Any
    source_selector_button: Any
    comparison_scene_selector_button: Any
    comparison_set_selector_button: Any
    comparison_source_selector_button: Any
    active_scene_overview: bool
    active_scene_key: str | None
    active_source_key: str | None
    active_set_index: int
    _runtime: OutputCanvasRuntime
    _projection_workflow_id: str
    _source_tabs_collapsed: bool
    _source_tabbar_preferred_width: int
    _source_tab_cache_signature: tuple[tuple[str, str], ...] | None
    _source_tab_tooltip_filters: dict[str, object]
    _canvas_detached: bool
    _open_single_external_editor: Callable[[object, OutputImageMeta], bool]
    _open_all_external_editor: Callable[[list[tuple[object, OutputImageMeta]]], bool]
    _reveal_output_asset: Callable[[OutputImageMeta], bool]

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
    ) -> None: ...
    @property
    def route_projector(self) -> OutputRouteProjectorPort:
        """Return the authorized Output route projector for this widget."""
        ...

    @property
    def qpane_catalog(self) -> CanvasPaneCatalog:
        """Return the QPane catalog adapter owned by this widget."""
        ...

    def set_final_output_lookup(
        self,
        *,
        payload_lookup: Callable[[UUID], object | None],
        metadata_lookup: Callable[[UUID], OutputImageMeta | None],
    ) -> None:
        """Set registry-backed lookup functions for external-editor actions."""
        ...

    def set_preview_registry(self, registry: OutputPreviewRegistry) -> None:
        """Bind the transient preview registry for the active projection surface."""
        ...

    def set_canvas_detached(self, detached: bool) -> None:
        """Set manager-owned canvas attachment state."""
        ...

    def bind_projection_session(self, session: OutputCanvasSession) -> None:
        """Bind the active Output projection session into the widget surface."""
        ...
