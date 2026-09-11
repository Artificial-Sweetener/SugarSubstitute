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

"""Prove preview overlays cannot pair one final image with another route."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.domain.workflow import CanvasRouteIdentity, ImageMeta
from substitute.presentation.canvas.output.output_preview_navigation_presenter import (
    OutputPreviewNavigationPresenter,
)


@dataclass
class _RouteProjector:
    """Record final image route applications."""

    calls: list[tuple[CanvasRouteIdentity, UUID]] = field(default_factory=list)

    def apply_final_image_route(
        self,
        route: CanvasRouteIdentity,
        image_id: UUID,
    ) -> bool:
        """Record one route and image pair."""

        self.calls.append((route, image_id))
        return route.primary_image_id == image_id


def test_final_presentation_uses_projection_image_when_preview_selection_is_stale() -> (
    None
):
    """Never apply the active projection route to a stale overlaid image."""

    active_id = uuid4()
    stale_id = uuid4()
    active_source = _source("text", active_id)
    stale_source = _source("upscale", stale_id)
    projection = OutputCanvasProjection(
        sources=(active_source, stale_source),
        active_source_key="text",
        active_set_index=1,
        active_uuid=active_id,
        set_count=1,
    )
    projector = _RouteProjector()
    navigation = SimpleNamespace(
        visible_sources=lambda: {"text": active_source, "upscale": stale_source}
    )
    host = SimpleNamespace(
        _preview_registry=OutputPreviewRegistry(),
        _document_navigation=navigation,
        active_source_key="upscale",
        active_set_index=1,
        route_projector=projector,
    )

    presented = OutputPreviewNavigationPresenter(host).present_active_item(projection)

    assert presented is True
    assert len(projector.calls) == 1
    route, image_id = projector.calls[0]
    assert image_id == active_id
    assert route.primary_image_id == active_id
    assert "source:text" in route.route_key


def _source(source_key: str, image_id: UUID) -> OutputCanvasSourceGroup:
    """Build one single-image final source."""

    metadata = ImageMeta(
        workflow_name="Workflow",
        cube_name=source_key,
        image_number=1,
        suffix="",
        path="output.png",
        source_key=source_key,
        source_label=source_key,
    )
    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=source_key,
        images_by_set={
            1: OutputCanvasImageItem(
                image_id=image_id,
                image_meta=metadata,
                set_index=1,
            )
        },
    )
