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

"""Build focused Output preview lifecycle test values."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
)
from substitute.domain.workflow import CanvasSessionBoundary, ImageMeta


def build_scene(
    *,
    sources: tuple[OutputCanvasSourceGroup, ...],
    scene_key: str = "portrait",
    scene_run_id: str = "scene-run",
    primary_image_id: UUID | None = None,
    preview_image_id: UUID | None = None,
    representative_source_key: str | None = None,
    representative_set_index: int | None = None,
    status: str = "completed",
) -> OutputCanvasSceneGroup:
    """Return one scene group for lifecycle tests."""

    return OutputCanvasSceneGroup(
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        title=scene_key.title(),
        order=0,
        sources=sources,
        preview_image_id=preview_image_id,
        primary_image_id=primary_image_id,
        representative_source_key=representative_source_key,
        representative_set_index=representative_set_index,
        status=status,
    )


def build_session(
    projection: OutputCanvasProjection,
    *,
    workflow_id: str = "wf",
) -> OutputCanvasSession:
    """Return an Output session wrapper for lifecycle tests."""

    return bind_output_canvas_session(
        CanvasSessionBoundary(),
        workflow_id=workflow_id,
        projection=projection,
        image_metadata_lookup={},
    )


def build_source(
    source_key: str,
    label: str,
    images_by_set: dict[int, UUID],
    *,
    generation_run_id: str = "",
) -> OutputCanvasSourceGroup:
    """Return one source group with placeholder image metadata."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=label,
        images_by_set={
            set_index: OutputCanvasImageItem(
                image_id=image_id,
                image_meta=build_meta(generation_run_id=generation_run_id),
                set_index=set_index,
            )
            for set_index, image_id in images_by_set.items()
        },
    )


def build_meta(*, generation_run_id: str = "") -> ImageMeta:
    """Return minimal image metadata for lifecycle source fixtures."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Output",
        image_number=1,
        suffix="",
        path="E:/out.png",
        generation_run_id=generation_run_id,
    )
