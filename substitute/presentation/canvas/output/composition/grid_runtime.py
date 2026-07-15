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

"""Compose responsive Output grid planning and reflow collaborators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer

from substitute.presentation.canvas.output.composition.grid import (
    output_scene_overview_composer,
    output_source_grid_composer,
)
from substitute.presentation.canvas.output.output_canvas_asset_lookup import (
    OutputCanvasAssetLookup,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_revision_cache,
)
from substitute.presentation.canvas.output.output_canvas_route_presenter import (
    OutputCanvasRoutePresenter,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
    visible_output_source_groups_by_key,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    visible_output_compare_state,
)
from substitute.presentation.canvas.output.output_grid_reflow_context import (
    OutputGridReflowContextResolver,
)
from substitute.presentation.canvas.output.output_grid_reflow_controller import (
    OutputGridReflowController,
)
from substitute.presentation.canvas.output.output_grid_route_application_controller import (
    OutputGridRouteApplicationController,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridSceneBuilder,
)
from substitute.presentation.canvas.output.output_scene_overview_composer import (
    OutputSceneOverviewComposer,
    scene_overview_preview_for_scene,
)
from substitute.presentation.canvas.output.output_source_grid_composer import (
    OutputSourceGridComposer,
)
from substitute.presentation.canvas.qpane.canvas_route_projector import (
    OutputRouteProjector,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)

if TYPE_CHECKING:
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas


@dataclass(frozen=True, slots=True)
class OutputGridComposition:
    """Group responsive grid collaborators before pointer events are composed."""

    source_composer: OutputSourceGridComposer
    scene_composer: OutputSceneOverviewComposer
    route_application: OutputGridRouteApplicationController
    reflow: OutputGridReflowController


def compose_output_grid_runtime(
    host: OutputCanvas,
    *,
    asset_lookup: OutputCanvasAssetLookup,
    route_presenter: OutputCanvasRoutePresenter,
    route_projector: OutputRouteProjector,
) -> OutputGridComposition:
    """Compose scene building, prepared application, and coalesced reflow."""

    builder = OutputGridSceneBuilder()

    def viewport_extent() -> CanvasViewportExtent:
        """Return the current physical QPane viewport extent."""

        viewport = host.pane.currentViewportRect()
        return CanvasViewportExtent(viewport.width(), viewport.height())

    source_composer = output_source_grid_composer(
        asset_lookup.final_output_payload,
        scene_builder=builder,
        viewport_extent=viewport_extent,
    )
    scene_composer = output_scene_overview_composer(
        payload_lookup=asset_lookup.final_output_payload,
        scene_builder=builder,
        viewport_extent=viewport_extent,
        preview_lookup=lambda scene: scene_overview_preview_for_scene(
            scene,
            preview_image_cache=asset_lookup.preview_images(),
            scene_preview_slots=(
                output_revision_cache(host).scene_preview_slots_by_key
            ),
            completed_preview_slots=output_revision_cache(host).completed_preview_slots,
        ),
    )
    route_application = OutputGridRouteApplicationController(
        route_projector=route_projector,
        ensure_scene_request_images_cached=(
            route_presenter.ensure_scene_request_images_cached
        ),
    )
    context = OutputGridReflowContextResolver(
        output_session=lambda: getattr(host, "_output_session", None),
        scene_groups=lambda: output_scene_groups_by_key(
            output_route_state_snapshot(host)
        ),
        source_groups=lambda: visible_output_source_groups_by_key(
            output_route_state_snapshot(host)
        ),
        compare_enabled=lambda: visible_output_compare_state(host).enabled,
        scene_overview_active=lambda: host.active_scene_overview,
        active_scene_key=lambda: host.active_scene_key,
        active_source_key=lambda: host.active_source_key,
        active_set_index=lambda: host.active_set_index,
    )
    timer = QTimer(host)
    timer.setSingleShot(True)
    reflow = OutputGridReflowController(
        timer=timer,
        context_resolver=context,
        source_composer=source_composer,
        scene_composer=scene_composer,
        route_application=route_application,
    )
    timer.timeout.connect(reflow.deliver_pending)
    host.pane.viewportRectChanged.connect(reflow.on_viewport_rect_changed)
    return OutputGridComposition(
        source_composer,
        scene_composer,
        route_application,
        reflow,
    )


def current_output_viewport_extent(host: OutputCanvas) -> CanvasViewportExtent:
    """Return the physical viewport used for immediate grid presentation."""

    viewport = host.pane.currentViewportRect()
    return CanvasViewportExtent(viewport.width(), viewport.height())


__all__ = [
    "OutputGridComposition",
    "compose_output_grid_runtime",
    "current_output_viewport_extent",
]
