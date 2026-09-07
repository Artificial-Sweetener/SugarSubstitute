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

"""Characterize transient preview placeholders in Output navigation projections."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows.output_automatic_frontier_projection import (
    automatic_frontier_image_ids,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_preview_projection import (
    overlay_preview_sources,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLaneKey,
    OutputPreviewLanePlacement,
)
from substitute.domain.workflow import CanvasSessionRevision, ImageMeta


def test_preview_only_cube_creates_source_tab_placeholder() -> None:
    """Append a preview-only cube after existing finalized cube sources."""

    text_id = uuid4()
    preview_id = uuid4()
    sources = overlay_preview_sources(
        (_source("text", "Text to Image", {1: text_id}),),
        (_preview("upscale", "Diffusion Upscale", preview_id),),
        scene_key=None,
    )

    assert tuple(source.source_key for source in sources) == ("text", "upscale")
    assert sources[1].label == "Diffusion Upscale"
    assert sources[1].images_by_set[1].image_id == preview_id


def test_automatic_frontier_replaces_downstream_slots_progressively() -> None:
    """Retain preceding batch members until the downstream source supplies them."""

    text_ids = {1: uuid4(), 2: uuid4()}
    upscale_zero = uuid4()
    sources = (
        _source("text", "Text to Image", text_ids),
        _source("upscale", "Diffusion Upscale", {1: upscale_zero}),
    )

    incomplete = automatic_frontier_image_ids(sources, source_key="upscale")
    upscale_one = uuid4()
    completed = automatic_frontier_image_ids(
        (
            sources[0],
            _source(
                "upscale",
                "Diffusion Upscale",
                {1: upscale_zero, 2: upscale_one},
            ),
        ),
        source_key="upscale",
    )

    assert incomplete == (upscale_zero, text_ids[2])
    assert completed == (upscale_zero, upscale_one)


def test_automatic_frontier_keeps_a_lone_preview_as_the_only_item() -> None:
    """Avoid manufacturing a grid when no preceding CubeOutput exists."""

    preview_id = uuid4()
    sources = (_source("text", "Text to Image", {1: preview_id}),)

    assert automatic_frontier_image_ids(sources, source_key="text") == (preview_id,)


def test_preview_replaces_only_first_batch_slot_and_keeps_other_finals() -> None:
    """Overlay the live frame on set one while retaining later finalized sets."""

    final_ids = {1: uuid4(), 2: uuid4(), 3: uuid4()}
    preview_id = uuid4()
    sources = overlay_preview_sources(
        (_source("detail", "Detailer", final_ids),),
        (_preview("detail", "Detailer", preview_id),),
        scene_key=None,
    )

    images = sources[0].images_by_set
    assert images[1].image_id == preview_id
    assert images[2].image_id == final_ids[2]
    assert images[3].image_id == final_ids[3]


def test_new_queued_run_preview_appends_after_prior_run_result() -> None:
    """Place a later queued run preview beside its prior batch result."""

    final_id = uuid4()
    preview_id = uuid4()
    sources = overlay_preview_sources(
        (
            _source(
                "detail",
                "Detailer",
                {1: final_id},
                generation_run_id="run-1",
            ),
        ),
        (_preview("detail", "Detailer", preview_id, generation_run_id="run-2"),),
        scene_key=None,
    )

    images = sources[0].images_by_set
    assert tuple(images) == (1, 2)
    assert images[1].image_id == final_id
    assert images[2].image_id == preview_id


def test_scene_preview_placeholder_is_scoped_to_its_scene() -> None:
    """Keep independent scene previews from crossing source projections."""

    first_preview_id = uuid4()
    second_preview_id = uuid4()
    lanes = (
        _preview("upscale", "Upscale", first_preview_id, scene_key="first"),
        _preview("upscale", "Upscale", second_preview_id, scene_key="second"),
    )

    first_sources = overlay_preview_sources((), lanes, scene_key="first")
    second_sources = overlay_preview_sources((), lanes, scene_key="second")

    assert first_sources[0].images_by_set[1].image_id == first_preview_id
    assert second_sources[0].images_by_set[1].image_id == second_preview_id


def test_source_lane_takes_precedence_over_duplicate_scene_lane() -> None:
    """Use the source-view identity when one frame owns both preview placements."""

    scene_preview_id = uuid4()
    source_preview_id = uuid4()
    lanes = (
        _preview(
            "detail",
            "Detailer",
            scene_preview_id,
            scene_key="portrait",
            placement=OutputPreviewLanePlacement.SCENE,
        ),
        _preview(
            "detail",
            "Detailer",
            source_preview_id,
            scene_key="portrait",
            placement=OutputPreviewLanePlacement.SOURCE,
        ),
    )

    sources = overlay_preview_sources((), lanes, scene_key="portrait")

    assert sources[0].images_by_set[1].image_id == source_preview_id


def _source(
    source_key: str,
    label: str,
    image_ids: dict[int, UUID],
    *,
    generation_run_id: str = "",
) -> OutputCanvasSourceGroup:
    """Build one finalized source group."""

    return OutputCanvasSourceGroup(
        source_key,
        label,
        {
            set_index: OutputCanvasImageItem(
                image_id=image_id,
                image_meta=_meta(
                    source_key,
                    label,
                    set_index,
                    generation_run_id=generation_run_id,
                ),
                set_index=set_index,
            )
            for set_index, image_id in image_ids.items()
        },
    )


def _preview(
    source_key: str,
    label: str,
    preview_id: UUID,
    *,
    scene_key: str | None = None,
    placement: OutputPreviewLanePlacement = OutputPreviewLanePlacement.SOURCE,
    generation_run_id: str = "run",
) -> OutputPreviewLane:
    """Build one accepted transient lane."""

    key = (
        OutputPreviewLaneKey.scene(
            workflow_id="workflow",
            generation_run_id=generation_run_id,
            prompt_id="prompt",
            source_key=source_key,
            scene_run_id="scene-run",
            scene_key=scene_key or "scene",
        )
        if placement is OutputPreviewLanePlacement.SCENE
        else OutputPreviewLaneKey.source(
            workflow_id="workflow",
            generation_run_id=generation_run_id,
            prompt_id="prompt",
            source_key=source_key,
            scene_run_id="scene-run" if scene_key else None,
            scene_key=scene_key,
        )
    )
    return OutputPreviewLane(
        key=key,
        preview_id=preview_id,
        image=object(),
        source_label=label,
        client_id="client",
        session_revision=CanvasSessionRevision(1),
    )


def _meta(
    source_key: str,
    label: str,
    set_index: int,
    *,
    generation_run_id: str = "",
) -> ImageMeta:
    """Build minimal final metadata for an Output source slot."""

    return ImageMeta(
        workflow_name="workflow",
        cube_name=label,
        image_number=set_index,
        suffix="",
        path="",
        source_key=source_key,
        source_label=label,
        generation_run_id=generation_run_id,
    )
