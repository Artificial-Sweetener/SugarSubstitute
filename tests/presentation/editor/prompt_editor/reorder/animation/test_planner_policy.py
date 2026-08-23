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

"""Verify reorder animation eligibility, fallback, and identity policy."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_paint_policy import (
    animation_plan_with_complete_paint_ownership,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_animation import (
    PromptReorderAnimationPlanner,
)
from tests.presentation.editor.prompt_editor.reorder.animation.planner_support import (
    _layout,
)


def test_animation_requires_complete_projection_paint_snapshot() -> None:
    """A moving chip without text paint ownership should settle immediately."""

    planner = PromptReorderAnimationPlanner()
    plan = planner.build_plan(
        generation=1,
        current_visuals={0: QRectF(0.0, 0.0, 20.0, 10.0)},
        proposed_layout_view=_layout((0,)),
        proposed_chip_geometry={0: QRectF(40.0, 0.0, 20.0, 10.0)},
        ordered_segment_indices=(0,),
        dragged_segment_index=None,
        reason="paint_ownership_test",
    )

    assert plan.animated_segment_indices == frozenset({0})
    safe_plan = animation_plan_with_complete_paint_ownership(
        plan,
        snapshot_indices=frozenset(),
    )

    assert safe_plan.changed_targets == ()
    assert tuple(target.segment_index for target in safe_plan.immediate_targets) == (0,)
    assert safe_plan.immediate_segment_indices == frozenset({0})
    assert safe_plan.fallbacks[-1].reason == "projection_paint_snapshot_missing"


def test_animation_retains_targets_with_complete_projection_paint() -> None:
    """A moving chip with a complete snapshot should keep smooth displacement."""

    planner = PromptReorderAnimationPlanner()
    plan = planner.build_plan(
        generation=1,
        current_visuals={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(24.0, 0.0, 20.0, 10.0),
        },
        proposed_layout_view=_layout((0, 1)),
        proposed_chip_geometry={
            0: QRectF(24.0, 0.0, 20.0, 10.0),
            1: QRectF(0.0, 0.0, 20.0, 10.0),
        },
        ordered_segment_indices=(0, 1),
        dragged_segment_index=None,
        reason="paint_ownership_test",
    )

    safe_plan = animation_plan_with_complete_paint_ownership(
        plan,
        snapshot_indices=frozenset({0}),
    )

    assert tuple(target.segment_index for target in safe_plan.changed_targets) == (0,)
    assert tuple(target.segment_index for target in safe_plan.immediate_targets) == (1,)


def test_missing_current_rect_produces_immediate_target() -> None:
    """Newly visible settled chips should be placed immediately, not animated."""

    planner = PromptReorderAnimationPlanner()
    plan = planner.build_plan(
        generation=4,
        current_visuals={0: QRectF(0.0, 0.0, 20.0, 10.0)},
        proposed_layout_view=_layout((0, 1)),
        proposed_chip_geometry={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(24.0, 0.0, 20.0, 10.0),
        },
        ordered_segment_indices=(0, 1),
        dragged_segment_index=None,
        reason="target_changed",
    )

    assert plan.changed_targets == ()
    assert plan.immediate_segment_indices == frozenset({1})
    assert tuple(target.segment_index for target in plan.immediate_targets) == (1,)
    assert plan.immediate_targets[0].target_rect == QRectF(24.0, 0.0, 20.0, 10.0)
    assert plan.fallbacks[0].reason == "current_rect_missing"
    assert plan.fallbacks[0].disposition == "immediate"


def test_missing_target_rect_skips_animation() -> None:
    """Chips without settled target geometry should be skipped with metadata."""

    planner = PromptReorderAnimationPlanner()
    plan = planner.build_plan(
        generation=2,
        current_visuals={0: QRectF(0.0, 0.0, 20.0, 10.0)},
        proposed_layout_view=_layout((0, 1)),
        proposed_chip_geometry={},
        ordered_segment_indices=(0, 1),
        dragged_segment_index=None,
        reason="target_changed",
    )

    assert plan.changed_targets == ()
    assert plan.immediate_segment_indices == frozenset()
    assert plan.skipped_segment_indices == frozenset({0, 1})
    assert tuple(fallback.reason for fallback in plan.fallbacks) == (
        "target_rect_missing",
        "target_rect_missing",
    )
    assert {fallback.disposition for fallback in plan.fallbacks} == {"skipped"}


def test_only_changed_non_dragged_chips_are_included() -> None:
    """Unchanged and actively dragged chips should not become animation targets."""

    planner = PromptReorderAnimationPlanner()
    plan = planner.build_plan(
        generation=1,
        current_visuals={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(24.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 20.0, 10.0),
        },
        proposed_layout_view=_layout((1, 0, 2)),
        proposed_chip_geometry={
            0: QRectF(8.0, 0.0, 20.0, 10.0),
            1: QRectF(0.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 20.0, 10.0),
        },
        ordered_segment_indices=(1, 0, 2),
        dragged_segment_index=1,
        reason="keyboard_move",
    )

    assert tuple(target.segment_index for target in plan.changed_targets) == (0,)


def test_plan_values_are_frozen_and_copy_input_rects() -> None:
    """Planner output should not share caller-owned QRectF instances."""

    planner = PromptReorderAnimationPlanner()
    start_rect = QRectF(0.0, 0.0, 20.0, 10.0)
    target_rect = QRectF(10.0, 0.0, 20.0, 10.0)
    plan = planner.build_plan(
        generation=1,
        current_visuals={0: start_rect},
        proposed_layout_view=_layout((0,)),
        proposed_chip_geometry={0: target_rect},
        ordered_segment_indices=(0,),
        dragged_segment_index=None,
        reason="target_changed",
    )

    start_rect.moveLeft(100.0)
    target_rect.moveLeft(200.0)

    assert plan.changed_targets[0].start_rect == QRectF(0.0, 0.0, 20.0, 10.0)
    assert plan.changed_targets[0].target_rect == QRectF(10.0, 0.0, 20.0, 10.0)
    with pytest.raises(FrozenInstanceError):
        plan.reason = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        plan.changed_targets[0].segment_index = 99  # type: ignore[misc]


def test_stale_generation_is_ignored() -> None:
    """Older geometry generations should produce inert stale plans."""

    planner = PromptReorderAnimationPlanner()
    layout = _layout((0, 1))
    fresh = planner.build_plan(
        generation=3,
        current_visuals={0: QRectF(0.0, 0.0, 20.0, 10.0)},
        proposed_layout_view=layout,
        proposed_chip_geometry={0: QRectF(10.0, 0.0, 20.0, 10.0)},
        ordered_segment_indices=(0, 1),
        dragged_segment_index=None,
        reason="fresh",
    )
    stale = planner.build_plan(
        generation=2,
        current_visuals={0: QRectF(0.0, 0.0, 20.0, 10.0)},
        proposed_layout_view=layout,
        proposed_chip_geometry={0: QRectF(40.0, 0.0, 20.0, 10.0)},
        ordered_segment_indices=(0, 1),
        dragged_segment_index=None,
        reason="stale",
    )

    assert fresh.stale is False
    assert stale.stale is True
    assert stale.changed_targets == ()
    assert stale.immediate_targets == ()
    assert stale.skipped_segment_indices == frozenset({0, 1})
    assert {fallback.reason for fallback in stale.fallbacks} == {"stale_generation"}
