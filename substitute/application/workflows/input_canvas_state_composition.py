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

"""Compose focused owners for authoritative Input canvas state."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    InputRouteProjectorPort,
)
from substitute.application.workflows.input_asset_cleanup_service import (
    InputAssetCleanupService,
)
from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.input_image_asset_service import (
    InputImageAssetService,
)
from substitute.application.workflows.input_mask_asset_service import (
    InputMaskAssetService,
)
from substitute.application.workflows.input_mask_restoration_service import (
    InputMaskRestorationService,
)
from substitute.application.workflows.input_mask_visual_state_service import (
    InputMaskVisualStateService,
)
from substitute.application.workflows.input_route_projection_service import (
    InputRouteProjectionService,
)


@dataclass(frozen=True)
class InputCanvasStateComposition:
    """Hold focused Input canvas state owners without forwarding behavior."""

    routes: InputRouteProjectionService
    images: InputImageAssetService
    masks: InputMaskAssetService
    mask_restoration: InputMaskRestorationService
    mask_visuals: InputMaskVisualStateService
    cleanup: InputAssetCleanupService


def compose_input_canvas_state(
    *,
    document: InputCanvasDocumentPort,
    route_projector: InputRouteProjectorPort,
    session_boundary: CanvasRouteSessionBoundaryPort,
    image_registry: CanvasImageRegistry,
) -> InputCanvasStateComposition:
    """Compose focused state owners around shared document infrastructure."""

    routes = InputRouteProjectionService(
        projector=route_projector,
        session_boundary=session_boundary,
    )
    mask_visuals = InputMaskVisualStateService(document)
    masks = InputMaskAssetService(
        document=document,
        routes=routes,
        visuals=mask_visuals,
    )
    return InputCanvasStateComposition(
        routes=routes,
        images=InputImageAssetService(document=document, routes=routes),
        masks=masks,
        mask_restoration=InputMaskRestorationService(
            document=document,
            routes=routes,
            visuals=mask_visuals,
        ),
        mask_visuals=mask_visuals,
        cleanup=InputAssetCleanupService(
            document=document,
            image_registry=image_registry,
            routes=routes,
            masks=masks,
        ),
    )


__all__ = ["InputCanvasStateComposition", "compose_input_canvas_state"]
