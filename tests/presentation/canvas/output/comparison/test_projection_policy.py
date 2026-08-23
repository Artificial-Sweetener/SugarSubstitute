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

"""Verify projection-derived Output comparison policy and labels."""

from __future__ import annotations


from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)


from tests.presentation.canvas.output.comparison.controller_support import (
    build_controller,
    build_source,
    build_source_with_item,
)


def test_compare_sources_for_selection_scopes_to_matching_scene() -> None:
    """Compare source lookup should use scene-local sources for scene projections."""

    scene_a_sources = (build_source_with_item("source-a", "scene-a"),)
    scene_b_sources = (
        build_source_with_item("source-b", "scene-b"),
        build_source_with_item("source-c", "scene-b"),
    )
    projection = OutputCanvasProjection(
        sources=scene_a_sources + scene_b_sources,
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_count=2,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="run-a",
                scene_key="scene-a",
                title="Scene A",
                order=0,
                sources=scene_a_sources,
            ),
            OutputCanvasSceneGroup(
                scene_run_id="run-b",
                scene_key="scene-b",
                title="Scene B",
                order=1,
                sources=scene_b_sources,
            ),
        ),
    )
    controller = build_controller()

    sources = controller.compare_sources_for_selection(
        projection,
        OutputCompareSelection("scene-b", 1, "source-c"),
    )

    assert sources == scene_b_sources


def test_compare_projection_plan_defaults_base_and_counts_scoped_sources() -> None:
    """Compare projection sync should be planned from controller-owned policy."""

    scene_a_sources = (build_source_with_item("source-a", "scene-a"),)
    scene_b_sources = (
        build_source_with_item("source-b", "scene-b"),
        build_source_with_item("source-c", "scene-b"),
    )
    projection = OutputCanvasProjection(
        sources=scene_a_sources + scene_b_sources,
        active_source_key="source-a",
        active_set_index=1,
        active_uuid=None,
        set_count=1,
        scene_count=2,
        scene_groups=(
            OutputCanvasSceneGroup(
                scene_run_id="run-a",
                scene_key="scene-a",
                title="Scene A",
                order=0,
                sources=scene_a_sources,
            ),
            OutputCanvasSceneGroup(
                scene_run_id="run-b",
                scene_key="scene-b",
                title="Scene B",
                order=1,
                sources=scene_b_sources,
            ),
        ),
    )
    counted_sources: list[tuple[OutputCanvasSourceGroup, ...]] = []
    controller = build_controller(counted_sources=counted_sources, set_count=4)

    plan = controller.compare_projection_plan(
        projection,
        OutputCompareState(enabled=True),
    )

    assert plan.state == OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene-a", 1, "source-a"),
        comparison=OutputCompareSelection("scene-b", 1, "source-c"),
    )
    assert plan.base == OutputCompareSelection("scene-a", 1, "source-a")
    assert plan.sources == scene_a_sources
    assert plan.set_count == 4
    assert counted_sources == [scene_a_sources]


def test_compare_set_count_uses_sources_for_active_side() -> None:
    """Compare set counts should be derived from the side-specific sources."""

    source_a = build_source("source-a")
    source_b = build_source("source-b")
    state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection(None, 1, "source-a"),
        comparison=OutputCompareSelection(None, 1, "source-b"),
    )
    counted_sources: list[tuple[OutputCanvasSourceGroup, ...]] = []
    controller = build_controller(
        projection=OutputCanvasProjection(
            sources=(source_a, source_b),
            active_source_key="source-a",
            active_set_index=1,
            active_uuid=None,
            set_count=2,
        ),
        state=state,
        counted_sources=counted_sources,
        set_count=7,
    )

    count = controller.compare_set_count("comparison")

    assert count == 7
    assert counted_sources == [(source_a, source_b)]


def test_compare_source_label_uses_selected_source_label() -> None:
    """Compare source labels should resolve from the selection's scoped sources."""

    source_a = build_source("source-a", label="Base")
    source_b = build_source("source-b", label="Comparison")
    controller = build_controller(
        projection=OutputCanvasProjection(
            sources=(source_a, source_b),
            active_source_key="source-a",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        )
    )

    assert (
        controller.compare_source_label(OutputCompareSelection(None, 1, "source-b"))
        == "Comparison"
    )


def test_compare_source_label_falls_back_without_projection_or_source() -> None:
    """Compare source labels should have a stable empty-state fallback."""

    missing_projection = build_controller(projection=None)
    missing_source = build_controller(
        projection=OutputCanvasProjection(
            sources=(build_source("source-a", label="Base"),),
            active_source_key="source-a",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        )
    )

    assert (
        missing_projection.compare_source_label(
            OutputCompareSelection(None, 1, "source-a")
        )
        == "Output"
    )
    assert (
        missing_source.compare_source_label(
            OutputCompareSelection(None, 1, "source-missing")
        )
        == "Output"
    )
