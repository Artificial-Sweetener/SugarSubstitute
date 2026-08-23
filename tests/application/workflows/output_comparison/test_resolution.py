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

"""Contract tests for output compare selection resolution."""

from __future__ import annotations

from uuid import UUID, uuid4

from substitute.application.workflows import (
    OutputCompareSelection,
    OutputCompareState,
    default_output_compare_state,
    default_output_compare_state_for_context,
    output_compare_candidates,
    reconcile_output_compare_state,
    resolve_output_compare_selection,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    build_output_canvas_projection,
)
from substitute.domain.workflow import ImageMeta, WorkflowState


def _meta(
    label: str,
    *,
    source_key: str,
    image_number: int = 1,
    scene_key: str = "",
    scene_title: str = "",
    scene_order: int | None = None,
    scene_count: int | None = None,
) -> ImageMeta:
    """Build output metadata for compare resolver tests."""

    return ImageMeta(
        workflow_name="Recipe",
        cube_name=label,
        image_number=image_number,
        suffix="",
        path=f"E:/outputs/{source_key}_{image_number}.png",
        source_key=source_key,
        source_label=label,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
    )


def _projection(
    ordered_ids: list[UUID],
    metadata: dict[UUID, ImageMeta],
) -> OutputCanvasProjection:
    """Build an output projection for resolver tests."""

    workflow = WorkflowState(output_image_uuids=ordered_ids)
    return build_output_canvas_projection(workflow, metadata)


def test_compare_candidates_use_set_then_source_order_for_single_scene() -> None:
    """Single-scene candidates should use shared set order then source order."""

    ids = [uuid4() for _ in range(4)]
    projection = _projection(
        ids,
        {
            ids[0]: _meta("Text", source_key="text", image_number=1),
            ids[1]: _meta("Upscale", source_key="upscale", image_number=1),
            ids[2]: _meta("Text", source_key="text", image_number=2),
            ids[3]: _meta("Upscale", source_key="upscale", image_number=2),
        },
    )

    assert output_compare_candidates(projection) == (
        OutputCompareSelection(None, 1, "text"),
        OutputCompareSelection(None, 1, "upscale"),
        OutputCompareSelection(None, 2, "text"),
        OutputCompareSelection(None, 2, "upscale"),
    )


def test_compare_candidates_include_scene_order_for_multi_scene() -> None:
    """Multi-scene candidates should remain scoped to their scene keys."""

    ids = [uuid4() for _ in range(4)]
    projection = _projection(
        ids,
        {
            ids[0]: _meta(
                "Text",
                source_key="text",
                scene_key="second",
                scene_title="Second",
                scene_order=2,
                scene_count=2,
            ),
            ids[1]: _meta(
                "Upscale",
                source_key="upscale",
                scene_key="second",
                scene_title="Second",
                scene_order=2,
                scene_count=2,
            ),
            ids[2]: _meta(
                "Text",
                source_key="text",
                scene_key="first",
                scene_title="First",
                scene_order=1,
                scene_count=2,
            ),
            ids[3]: _meta(
                "Upscale",
                source_key="upscale",
                scene_key="first",
                scene_title="First",
                scene_order=1,
                scene_count=2,
            ),
        },
    )

    assert output_compare_candidates(projection) == (
        OutputCompareSelection("first", 1, "text"),
        OutputCompareSelection("first", 1, "upscale"),
        OutputCompareSelection("second", 1, "text"),
        OutputCompareSelection("second", 1, "upscale"),
    )


def test_default_compare_state_uses_first_and_last_candidates() -> None:
    """Default compare state should span the first and last available outputs."""

    ids = [uuid4() for _ in range(3)]
    projection = _projection(
        ids,
        {
            ids[0]: _meta("Text", source_key="text"),
            ids[1]: _meta("Upscale", source_key="upscale"),
            ids[2]: _meta("Face", source_key="face"),
        },
    )

    state = default_output_compare_state(projection)

    assert state.enabled is True
    assert state.base == OutputCompareSelection(None, 1, "text")
    assert state.comparison == OutputCompareSelection(None, 1, "face")


def test_contextual_default_compare_state_uses_current_batch_outputs() -> None:
    """Contextual default should span first and last source outputs in one batch."""

    ids = [uuid4() for _ in range(6)]
    projection = _projection(
        ids,
        {
            ids[0]: _meta("Text", source_key="text", image_number=1),
            ids[1]: _meta("Upscale", source_key="upscale", image_number=1),
            ids[2]: _meta("Face", source_key="face", image_number=1),
            ids[3]: _meta("Text", source_key="text", image_number=2),
            ids[4]: _meta("Upscale", source_key="upscale", image_number=2),
            ids[5]: _meta("Face", source_key="face", image_number=2),
        },
    )

    state = default_output_compare_state_for_context(
        projection,
        scene_key=None,
        set_index=2,
    )

    assert state.enabled is True
    assert state.base == OutputCompareSelection(None, 2, "text")
    assert state.comparison == OutputCompareSelection(None, 2, "face")


def test_resolve_compare_selection_returns_exact_item_or_none() -> None:
    """Selection resolution should require matching scene, source, and set."""

    image_id = uuid4()
    projection = _projection(
        [image_id],
        {image_id: _meta("Text", source_key="text")},
    )

    resolved = resolve_output_compare_selection(
        projection,
        OutputCompareSelection(None, 1, "text"),
    )

    assert resolved is not None
    assert resolved.image_id == image_id
    assert (
        resolve_output_compare_selection(
            projection,
            OutputCompareSelection(None, 2, "text"),
        )
        is None
    )


def test_reconcile_disables_compare_when_only_one_distinct_output_remains() -> None:
    """Compare should fail closed when fewer than two distinct outputs remain."""

    image_id = uuid4()
    projection = _projection(
        [image_id],
        {image_id: _meta("Text", source_key="text")},
    )
    selection = OutputCompareSelection(None, 1, "text")

    state = reconcile_output_compare_state(
        projection,
        OutputCompareState(enabled=True, base=selection, comparison=selection),
    )

    assert state.enabled is False
    assert state.base == selection
    assert state.comparison == selection


def test_reconcile_falls_back_deterministically_for_missing_selection() -> None:
    """Missing selections should fall back to nearest valid output choices."""

    ids = [uuid4() for _ in range(2)]
    projection = _projection(
        ids,
        {
            ids[0]: _meta("Text", source_key="text", image_number=1),
            ids[1]: _meta("Text", source_key="text", image_number=2),
        },
    )

    state = reconcile_output_compare_state(
        projection,
        OutputCompareState(
            enabled=True,
            base=OutputCompareSelection(None, 4, "text"),
            comparison=OutputCompareSelection(None, 1, "missing"),
            split_position=1.5,
            orientation="diagonal",
        ),
    )

    assert state.enabled is True
    assert state.base == OutputCompareSelection(None, 2, "text")
    assert state.comparison == OutputCompareSelection(None, 1, "text")
    assert state.split_position == 1.0
    assert state.orientation == "vertical"


def test_reconcile_disables_enabled_state_when_projection_is_empty() -> None:
    """Enabled compare state should disable when no output candidates remain."""

    projection = _projection([], {})

    state = reconcile_output_compare_state(
        projection,
        OutputCompareState(
            enabled=True,
            base=OutputCompareSelection(None, 1, "text"),
            comparison=OutputCompareSelection(None, 1, "upscale"),
        ),
    )

    assert state.enabled is False
    assert state.base is None
    assert state.comparison is None
