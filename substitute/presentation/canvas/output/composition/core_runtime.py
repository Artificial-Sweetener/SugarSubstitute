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

"""Compose Output QPane, asset, session, image, and preview foundations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    create_canvas_session_boundary,
)
from substitute.presentation.canvas.output.composition.assets import (
    output_canvas_asset_lookup,
)
from substitute.presentation.canvas.output.composition.preview import (
    output_preview_controller_for_host,
)
from substitute.presentation.canvas.output.composition.qpane import (
    output_qpane_catalog,
    output_qpane_presenter,
    output_route_projector_for,
    output_route_presenter,
)
from substitute.presentation.canvas.output.composition.runtime_types import (
    OutputCoreRuntime,
    OutputPreviewRuntime,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_scene_overview,
)
from substitute.presentation.canvas.output.output_canvas_preview_state import (
    output_preview_registry,
)
from substitute.presentation.canvas.output.output_image_route_controller import (
    OutputImageRouteController,
)
from substitute.presentation.canvas.output.output_route_binding_controller import (
    OutputRouteBindingController,
    OutputRouteBindingState,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)

if TYPE_CHECKING:
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas


@dataclass(frozen=True, slots=True)
class OutputCoreComposition:
    """Group foundations needed by later Output feature composers."""

    runtime: OutputCoreRuntime
    preview: OutputPreviewRuntime
    route_binding: OutputRouteBindingController
    image_routes: OutputImageRouteController


def compose_output_core_runtime(
    host: OutputCanvas,
    *,
    final_output_payload_lookup: Callable[[UUID], object | None] | None,
    final_output_metadata_lookup: Callable[[UUID], OutputImageMeta | None] | None,
    route_session_boundary: CanvasRouteSessionBoundaryPort | None,
) -> OutputCoreComposition:
    """Compose reusable Output foundations without constructing later features."""

    catalog = output_qpane_catalog(host.pane)
    qpane_presenter = output_qpane_presenter(catalog)
    boundary = route_session_boundary or create_canvas_session_boundary()
    projector = output_route_projector_for(host.pane, session_boundary=boundary)
    asset_lookup = output_canvas_asset_lookup(
        payload_lookup=final_output_payload_lookup,
        metadata_lookup=final_output_metadata_lookup,
        preview_image_cache=lambda: output_preview_registry(host).images_by_id(),
    )
    route_binding = OutputRouteBindingController(
        route_projector=projector,
        session_boundary=boundary,
        state=OutputRouteBindingState(
            workflow_id=lambda: str(host._projection_workflow_id or ""),
            projection=lambda: getattr(host, "_output_projection", None),
            session=lambda: getattr(host, "_output_session", None),
            store_session=lambda session: setattr(host, "_output_session", session),
            preview_registry=lambda: output_preview_registry(host),
            active_scene_overview=lambda: host.active_scene_overview,
            active_scene_key=lambda: host.active_scene_key,
        ),
    )
    image_routes = OutputImageRouteController(route_binding, projector)
    preview = output_preview_controller_for_host(
        host,
        asset_lookup=asset_lookup,
        qpane_presenter=qpane_presenter,
        output_session=lambda: getattr(host, "_output_session", None),
        set_current_output_image=lambda image_id: (
            host._runtime.projection.controller.set_current_output_image(image_id)
        ),
        activate_scene_overview=lambda: _activate_scene_overview(host),
    )
    route_presenter = output_route_presenter(
        catalog=lambda: catalog,
        image_registrar=lambda: qpane_presenter,
        layer_payload=asset_lookup.scene_request_layer_payload,
        layer_path=asset_lookup.scene_request_layer_path,
    )
    return OutputCoreComposition(
        runtime=OutputCoreRuntime(
            asset_lookup,
            catalog,
            qpane_presenter,
            route_presenter,
            projector,
            boundary,
        ),
        preview=OutputPreviewRuntime(preview),
        route_binding=route_binding,
        image_routes=image_routes,
    )


def _activate_scene_overview(host: OutputCanvas) -> None:
    """Activate and re-present scene overview after preview membership changes."""

    activate_output_scene_overview(
        host,
        update_tabbar_container=lambda: update_output_tabbar_container(host),
    )
    session = getattr(host, "_output_session", None)
    if session is not None:
        host._runtime.projection.controller.bind_output_route_projector(
            session.active_route
        )
    viewport = host.pane.currentViewportRect()
    host._runtime.grid.reflow.present_current_grid(
        CanvasViewportExtent(viewport.width(), viewport.height())
    )


__all__ = ["OutputCoreComposition", "compose_output_core_runtime"]
