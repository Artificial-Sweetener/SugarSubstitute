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

"""Tests for output-canvas thumbnail choice projection."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.shell.output_canvas_thumbnail_choices import (
    ProjectionOutputCanvasThumbnailChoiceProvider,
)


def test_output_thumbnail_choices_return_empty_without_projection() -> None:
    """Missing output projection should produce no thumbnail choices."""

    provider = ProjectionOutputCanvasThumbnailChoiceProvider(lambda: None)

    assert provider.choices() == ()
    assert provider.active_choice() is None


def test_output_thumbnail_choices_project_source_batches() -> None:
    """Non-scene projections should expose source and batch metadata."""

    image_a = uuid4()
    image_b = uuid4()
    projection = OutputCanvasProjection(
        sources=(
            _source(
                "main",
                "Main output",
                (
                    _item(image_a, 1, source_key="main"),
                    _item(image_b, 2, source_key="main"),
                ),
            ),
        ),
        active_source_key="main",
        active_set_index=2,
        active_uuid=image_b,
        set_count=2,
    )
    provider = ProjectionOutputCanvasThumbnailChoiceProvider(lambda: projection)

    choices = provider.choices()

    assert [
        (choice.image_id, choice.source_label, choice.set_index) for choice in choices
    ] == [
        (image_a, "Main output", 1),
        (image_b, "Main output", 2),
    ]
    active_choice = provider.active_choice()
    assert active_choice is not None
    assert active_choice.image_id == image_b


def test_output_thumbnail_choices_project_meaningful_scenes() -> None:
    """Meaningful scene groups should be preserved in choice metadata."""

    scene_a_image = uuid4()
    scene_b_image = uuid4()
    projection = OutputCanvasProjection(
        sources=(
            _source(
                "main",
                "Main output",
                (
                    _item(scene_a_image, 1, source_key="main", scene_key="scene-a"),
                    _item(scene_b_image, 1, source_key="main", scene_key="scene-b"),
                ),
            ),
        ),
        active_source_key="main",
        active_set_index=1,
        active_uuid=scene_b_image,
        set_count=1,
        scene_groups=(
            _scene("scene-a", "Scene A", 1, scene_a_image),
            _scene("scene-b", "Scene B", 2, scene_b_image),
        ),
        scene_count=2,
    )
    provider = ProjectionOutputCanvasThumbnailChoiceProvider(lambda: projection)

    choices = provider.choices()

    assert [(choice.scene_key, choice.scene_title) for choice in choices] == [
        ("scene-a", "Scene A"),
        ("scene-b", "Scene B"),
    ]
    active_choice = provider.active_choice()
    assert active_choice is not None
    assert active_choice.scene_key == "scene-b"


def test_output_thumbnail_choices_collapse_default_single_scene() -> None:
    """Default one-scene metadata should not force scene grouping."""

    image_id = uuid4()
    projection = OutputCanvasProjection(
        sources=(_source("main", "Main output", (_item(image_id, 1),)),),
        active_source_key="main",
        active_set_index=1,
        active_uuid=image_id,
        set_count=1,
        scene_groups=(_scene("", "Scene", 0, image_id),),
        scene_count=1,
    )
    provider = ProjectionOutputCanvasThumbnailChoiceProvider(lambda: projection)

    choices = provider.choices()

    assert len(choices) == 1
    assert choices[0].scene_key == ""
    assert choices[0].scene_title == ""


def test_output_thumbnail_choices_deduplicate_scene_and_source_overlap() -> None:
    """Scene traversal should preserve first occurrence for duplicated image ids."""

    image_id = uuid4()
    scene = OutputCanvasSceneGroup(
        scene_run_id="run",
        scene_key="scene",
        title="Scene",
        order=1,
        sources=(
            _source("main", "Main output", (_item(image_id, 1, source_key="main"),)),
            _source("alt", "Alt output", (_item(image_id, 1, source_key="alt"),)),
        ),
    )
    projection = OutputCanvasProjection(
        sources=scene.sources,
        active_source_key="main",
        active_set_index=1,
        active_uuid=image_id,
        set_count=1,
        scene_groups=(scene,),
        scene_count=1,
    )
    provider = ProjectionOutputCanvasThumbnailChoiceProvider(lambda: projection)

    choices = provider.choices()

    assert len(choices) == 1
    assert choices[0].source_key == "main"


def _source(
    source_key: str,
    label: str,
    items: tuple[OutputCanvasImageItem, ...],
) -> OutputCanvasSourceGroup:
    """Return one source group keyed by set index."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=label,
        images_by_set={item.set_index: item for item in items},
    )


def _scene(
    scene_key: str,
    title: str,
    order: int,
    image_id: UUID,
) -> OutputCanvasSceneGroup:
    """Return one scene group containing a single main output image."""

    return OutputCanvasSceneGroup(
        scene_run_id=f"{scene_key}-run",
        scene_key=scene_key,
        title=title,
        order=order,
        sources=(_source("main", "Main output", (_item(image_id, 1),)),),
    )


def _item(
    image_id: UUID,
    set_index: int,
    *,
    source_key: str = "main",
    scene_key: str = "",
) -> OutputCanvasImageItem:
    """Return one output projection image item."""

    return OutputCanvasImageItem(
        image_id=image_id,
        image_meta=ImageMeta(
            workflow_name="Workflow",
            cube_name="Cube",
            image_number=set_index,
            suffix=".png",
            path=f"C:/outputs/{image_id}.png",
            source_key=source_key,
            source_label=source_key,
            scene_key=scene_key,
            width=512,
            height=384,
            list_index=set_index - 1,
        ),
        set_index=set_index,
    )
