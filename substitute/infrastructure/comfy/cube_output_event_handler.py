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

"""Handle validated Comfy cube-output image artifacts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from substitute.infrastructure.comfy.cube_output_event import (
    SubstituteVisualIdentity,
)
from substitute.infrastructure.comfy.cube_output_event_router import (
    CubeOutputDiagnostic,
    CubeOutputRouteContext,
    route_cube_output_event,
)
from substitute.infrastructure.comfy.final_image_event import (
    FinalImageEvent,
    FinalImageScene,
    FinalImageSource,
)
from substitute.infrastructure.comfy.final_image_event_handler import (
    FinalImageEventHandler,
)


@dataclass(frozen=True)
class CubeOutputEventHandler:
    """Adapt validated cube-output events into shared final-image handling."""

    context: CubeOutputRouteContext
    workflow_payload: dict[str, object]
    final_image_handler: FinalImageEventHandler
    identity_acceptor: Callable[
        [SubstituteVisualIdentity | None, str | None, str | None], bool
    ]
    on_diagnostic: Callable[[CubeOutputDiagnostic], None]

    def handle(self, data: Mapping[str, object]) -> None:
        """Handle one cube-output websocket payload."""

        route_result = route_cube_output_event(
            data,
            context=self.context,
            identity_acceptor=self.identity_acceptor,
        )
        if route_result.diagnostic is not None:
            self.on_diagnostic(route_result.diagnostic)
            return
        if route_result.cube_output is None or route_result.source_identity is None:
            return
        cube_output = route_result.cube_output
        if cube_output.node_id is None or cube_output.substitute is None:
            return

        visual_identity = cube_output.substitute
        self.final_image_handler.handle(
            FinalImageEvent(
                workflow_id=visual_identity.workflow_id,
                generation_run_id=visual_identity.generation_run_id,
                prompt_id=self.context.prompt_id,
                client_id=visual_identity.client_id,
                workflow_payload=self.workflow_payload,
                source=FinalImageSource(
                    node_id=route_result.source_identity.node_id,
                    source_key=route_result.source_identity.source_key,
                    source_label=route_result.source_identity.source_label,
                    cube_alias=route_result.source_identity.cube_alias,
                ),
                artifacts=cube_output.artifacts,
                list_index=cube_output.list_index or 0,
                scene=FinalImageScene(
                    run_id=visual_identity.scene_run_id,
                    key=visual_identity.scene_key,
                    title=visual_identity.scene_title,
                    order=visual_identity.scene_order,
                    count=visual_identity.scene_count,
                ),
            )
        )


__all__ = [
    "CubeOutputEventHandler",
]
