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

"""Define immutable lifetime bundles for composed Output canvas features."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
)
from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
)
from substitute.presentation.canvas.output.output_canvas_compare_rendering_controller import (
    OutputCanvasCompareRenderingController,
)
from substitute.presentation.canvas.output.output_canvas_context_menu_controller import (
    OutputCanvasContextMenuController,
)
from substitute.presentation.canvas.output.output_canvas_grid_event_controller import (
    OutputCanvasGridEventController,
)
from substitute.presentation.canvas.output.output_canvas_interaction_controller import (
    OutputCanvasInteractionController,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)
from substitute.presentation.canvas.output.output_canvas_picker_controller import (
    OutputCanvasPickerController,
)
from substitute.presentation.canvas.output.output_canvas_projection_controller import (
    OutputCanvasProjectionController,
)
from substitute.presentation.canvas.output.output_canvas_route_presenter import (
    OutputCanvasRoutePresenter,
)
from substitute.presentation.canvas.output.output_canvas_source_tabs_controller import (
    OutputCanvasSourceTabsController,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
)
from substitute.presentation.canvas.output.output_compare_material_gap import (
    OutputCompareMaterialGapOverlay,
)
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresenter,
)
from substitute.presentation.canvas.output.output_grid_reflow_controller import (
    OutputGridReflowController,
)
from substitute.presentation.canvas.output.output_grid_route_application_controller import (
    OutputGridRouteApplicationController,
)
from substitute.presentation.canvas.output.output_preview_controller import (
    OutputPreviewController,
)
from substitute.presentation.canvas.output.output_scene_overview_composer import (
    OutputSceneOverviewComposer,
)
from substitute.presentation.canvas.output.output_source_grid_composer import (
    OutputSourceGridComposer,
)
from substitute.presentation.canvas.qpane.canvas_pane_catalog import CanvasPaneCatalog
from substitute.presentation.canvas.qpane.canvas_route_projector import (
    OutputRouteProjector,
)
from substitute.presentation.canvas.qpane.output_qpane_presenter import (
    OutputCanvasQPanePresenter,
)


@dataclass(frozen=True, slots=True)
class OutputCoreRuntime:
    """Own Output asset, QPane, route, and session-boundary collaborators."""

    asset_lookup: OutputCanvasAssetLookup
    qpane_catalog: CanvasPaneCatalog
    qpane_presenter: OutputCanvasQPanePresenter
    route_presenter: OutputCanvasRoutePresenter
    route_projector: OutputRouteProjector
    session_boundary: CanvasRouteSessionBoundaryPort


@dataclass(frozen=True, slots=True)
class OutputGridRuntime:
    """Own source/scene grid composition and pointer routing collaborators."""

    source_composer: OutputSourceGridComposer
    scene_composer: OutputSceneOverviewComposer
    route_application: OutputGridRouteApplicationController
    reflow: OutputGridReflowController
    event_controller: OutputCanvasGridEventController


@dataclass(frozen=True, slots=True)
class OutputPreviewRuntime:
    """Own transient preview presentation collaborators."""

    controller: OutputPreviewController


@dataclass(frozen=True, slots=True)
class OutputCompareRuntime:
    """Own compare selection, rendering, and material-gap collaborators."""

    presenter: OutputComparePresenter
    controller: OutputCompareController
    rendering_controller: OutputCanvasCompareRenderingController
    material_gap_overlay: OutputCompareMaterialGapOverlay


@dataclass(frozen=True, slots=True)
class OutputNavigationRuntime:
    """Own Output navigation, tabs, and picker collaborators."""

    picker: OutputCanvasPickerController
    source_tabs: OutputCanvasSourceTabsController
    controller: OutputCanvasNavigationController


@dataclass(frozen=True, slots=True)
class OutputInteractionRuntime:
    """Own general pointer and context-menu interaction collaborators."""

    pointer: OutputCanvasInteractionController
    context_menu: OutputCanvasContextMenuController


@dataclass(frozen=True, slots=True)
class OutputProjectionRuntime:
    """Own the Output projection lifecycle facade."""

    controller: OutputCanvasProjectionController


@dataclass(frozen=True, slots=True)
class OutputCanvasRuntime:
    """Group all Output collaborators under one widget-owned lifetime."""

    core: OutputCoreRuntime
    grid: OutputGridRuntime
    preview: OutputPreviewRuntime
    compare: OutputCompareRuntime
    navigation: OutputNavigationRuntime
    interaction: OutputInteractionRuntime
    projection: OutputProjectionRuntime


__all__ = [
    "OutputCanvasRuntime",
    "OutputCompareRuntime",
    "OutputCoreRuntime",
    "OutputGridRuntime",
    "OutputInteractionRuntime",
    "OutputNavigationRuntime",
    "OutputPreviewRuntime",
    "OutputProjectionRuntime",
]
