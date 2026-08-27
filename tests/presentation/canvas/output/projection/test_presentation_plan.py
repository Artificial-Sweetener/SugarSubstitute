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

"""Verify pure Output projection mode resolution."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_projection_presentation_plan import (
    OutputProjectionMode,
    resolve_output_projection_presentation,
)


@pytest.mark.parametrize(
    ("mode", "projection_factory"),
    (
        (OutputProjectionMode.IMAGE, lambda: _projection()),
        (
            OutputProjectionMode.SOURCE_GRID,
            lambda: _projection(active_set_index=0),
        ),
        (
            OutputProjectionMode.SCENE_OVERVIEW,
            lambda: _projection(scene_count=2, active_scene_overview=True),
        ),
        (
            OutputProjectionMode.COMPARE,
            lambda: _projection(
                compare_state=OutputCompareState(
                    enabled=True,
                    base=OutputCompareSelection("scene-a", 1, "source-a"),
                    comparison=OutputCompareSelection("scene-a", 1, "source-b"),
                )
            ),
        ),
        (
            OutputProjectionMode.EMPTY,
            lambda: _projection(active_uuid=False),
        ),
    ),
)
def test_resolver_selects_exactly_one_visible_mode(
    mode: OutputProjectionMode,
    projection_factory: Callable[[], OutputCanvasProjection],
) -> None:
    """Each complete or incomplete projection should resolve deterministically."""

    projection = projection_factory()
    scenes = {scene.scene_key: scene for scene in projection.scene_groups}

    plan = resolve_output_projection_presentation(projection, scene_groups=scenes)

    assert plan.mode is mode


def test_invalid_compare_state_falls_back_to_image_mode() -> None:
    """An enabled compare state without valid selections should reconcile closed."""

    projection = OutputCanvasProjection(
        sources=(),
        active_source_key=None,
        active_set_index=1,
        active_uuid=None,
        set_count=0,
        compare_state=OutputCompareState(enabled=True),
    )

    plan = resolve_output_projection_presentation(
        projection,
        scene_groups={scene.scene_key: scene for scene in projection.scene_groups},
    )

    assert plan.mode is OutputProjectionMode.EMPTY
    assert plan.compare_state.enabled is False


def _projection(
    *,
    active_set_index: int = 1,
    scene_count: int = 1,
    active_scene_overview: bool = False,
    compare_state: OutputCompareState | None = None,
    active_uuid: bool = True,
) -> OutputCanvasProjection:
    """Build one source-backed projection with configurable visible intent."""

    image_id = uuid4()
    item = OutputCanvasImageItem(
        image_id=image_id,
        image_meta=ImageMeta(
            workflow_name="Workflow",
            cube_name="Output",
            image_number=1,
            suffix="",
            path="E:/output.png",
            source_key="source-a",
            source_label="Source A",
            scene_key="scene-a",
        ),
        set_index=1,
    )
    source = OutputCanvasSourceGroup("source-a", "Source A", {1: item})
    comparison_image_id = uuid4()
    comparison_item = OutputCanvasImageItem(
        image_id=comparison_image_id,
        image_meta=ImageMeta(
            workflow_name="Workflow",
            cube_name="Comparison",
            image_number=1,
            suffix="",
            path="E:/comparison.png",
            source_key="source-b",
            source_label="Source B",
            scene_key="scene-a",
        ),
        set_index=1,
    )
    comparison_source = OutputCanvasSourceGroup(
        "source-b",
        "Source B",
        {1: comparison_item},
    )
    scene = OutputCanvasSceneGroup(
        scene_run_id="run-a",
        scene_key="scene-a",
        title="Scene A",
        order=0,
        sources=(source, comparison_source),
        primary_image_id=image_id,
    )
    return OutputCanvasProjection(
        sources=(source, comparison_source),
        active_source_key=(None if active_scene_overview else "source-a"),
        active_set_index=active_set_index,
        active_uuid=image_id if active_uuid else None,
        set_count=1,
        scene_groups=(scene,),
        active_scene_key="scene-a",
        active_scene_overview=active_scene_overview,
        scene_count=scene_count,
        compare_state=compare_state or OutputCompareState(),
    )
