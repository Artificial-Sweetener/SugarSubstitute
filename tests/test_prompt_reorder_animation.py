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

"""Cover projection-owned prompt reorder animation planning."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import os
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.prompt_editor import (
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderRowView,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_animation import (
    PromptReorderAnimationPlan,
    PromptReorderAnimationPlanner,
    PromptReorderAnimationTarget,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presenter import (
    PromptReorderAnimationPresenter,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_paint_ownership import (
    animation_plan_with_complete_paint_ownership,
)


_WINDOWS_XDIST_QT_SKIP = pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="Prompt reorder QWidget animation tests require non-xdist execution on Windows",
)


def _layout(*rows: tuple[int, ...]) -> PromptReorderLayoutView:
    """Return a settled layout view with deterministic row identities."""

    return PromptReorderLayoutView(
        rows=tuple(
            PromptReorderRowView(row_index=row_index, chip_indices=row)
            for row_index, row in enumerate(rows)
        ),
        gaps=(),
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


def test_same_line_move_produces_settled_target_rect_shift() -> None:
    """Planner should emit same-line displacement from supplied settled rects."""

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
            0: QRectF(24.0, 0.0, 20.0, 10.0),
            1: QRectF(0.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 20.0, 10.0),
        },
        ordered_segment_indices=(1, 0, 2),
        dragged_segment_index=1,
        reason="pointer_target_changed",
    )

    assert plan.changed_targets == (
        PromptReorderAnimationTarget(
            segment_index=0,
            start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
            target_rect=QRectF(24.0, 0.0, 20.0, 10.0),
            target_visible=True,
        ),
    )
    assert plan.immediate_segment_indices == frozenset()
    assert plan.skipped_segment_indices == frozenset()


def test_wrapped_move_uses_next_line_settled_target_rect() -> None:
    """Planner should preserve wrapped-line y positions from settled geometry."""

    planner = PromptReorderAnimationPlanner()
    plan = planner.build_plan(
        generation=1,
        current_visuals={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 26.0, 10.0),
            3: QRectF(78.0, 0.0, 26.0, 10.0),
        },
        proposed_layout_view=_layout((0, 1), (2, 3)),
        proposed_chip_geometry={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(24.0, 0.0, 20.0, 10.0),
            2: QRectF(0.0, 18.0, 26.0, 10.0),
            3: QRectF(30.0, 18.0, 26.0, 10.0),
        },
        ordered_segment_indices=(0, 1, 2, 3),
        dragged_segment_index=1,
        reason="pointer_target_changed_wrap",
    )

    target_by_segment = {
        target.segment_index: target.target_rect for target in plan.changed_targets
    }

    assert target_by_segment[2] == QRectF(0.0, 18.0, 26.0, 10.0)
    assert target_by_segment[3] == QRectF(30.0, 18.0, 26.0, 10.0)


def test_multiline_gap_move_uses_settled_gap_target_rect() -> None:
    """Planner should preserve gap-spanning target rects from settled geometry."""

    planner = PromptReorderAnimationPlanner()
    layout = PromptReorderLayoutView(
        rows=(
            PromptReorderRowView(row_index=0, chip_indices=(0,)),
            PromptReorderRowView(row_index=1, chip_indices=(1, 2)),
        ),
        gaps=(
            PromptReorderGapView(
                gap_index=0,
                separator_text="\n\n",
                blank_line_count=2,
                placement=PromptReorderGapPlacement.BETWEEN_ROWS,
            ),
        ),
    )
    plan = planner.build_plan(
        generation=1,
        current_visuals={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(24.0, 0.0, 20.0, 10.0),
            2: QRectF(48.0, 0.0, 26.0, 10.0),
        },
        proposed_layout_view=layout,
        proposed_chip_geometry={
            0: QRectF(0.0, 0.0, 20.0, 10.0),
            1: QRectF(0.0, 46.0, 20.0, 10.0),
            2: QRectF(24.0, 46.0, 26.0, 10.0),
        },
        ordered_segment_indices=(0, 1, 2),
        dragged_segment_index=None,
        reason="pointer_target_changed_multiline_gap",
    )

    target_by_segment = {
        target.segment_index: target.target_rect for target in plan.changed_targets
    }

    assert plan.layout_view.gaps == layout.gaps
    assert target_by_segment[1] == QRectF(0.0, 46.0, 20.0, 10.0)
    assert target_by_segment[2] == QRectF(24.0, 46.0, 26.0, 10.0)


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


def _ensure_qapp() -> QApplication:
    """Return the running Qt application used by presenter tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events(app: QApplication, cycles: int = 5) -> None:
    """Flush pending Qt animation and widget work for deterministic assertions."""

    for _ in range(cycles):
        app.processEvents()


def _host_with_chips() -> tuple[QApplication, QWidget, dict[int, QWidget]]:
    """Return a small visible widget tree for presenter-owned chip animation."""

    app = _ensure_qapp()
    host = QWidget()
    host.setGeometry(0, 0, 220, 80)
    chips = {
        0: QWidget(host),
        1: QWidget(host),
    }
    chips[0].setGeometry(0, 0, 20, 10)
    chips[1].setGeometry(24, 0, 20, 10)
    for segment_index, chip in chips.items():
        chip.setObjectName(f"chip{segment_index}")
        chip.show()
    host.show()
    _process_events(app)
    return app, host, chips


def _presenter_plan(
    *,
    generation: int,
    dragged_segment_index: int | None = None,
    changed_targets: tuple[PromptReorderAnimationTarget, ...] = (),
    immediate_targets: tuple[PromptReorderAnimationTarget, ...] = (),
    stale: bool = False,
) -> PromptReorderAnimationPlan:
    """Return one presenter-facing animation plan without invoking planning logic."""

    return PromptReorderAnimationPlan(
        generation=generation,
        dragged_segment_index=dragged_segment_index,
        ordered_segment_indices=(0, 1),
        layout_view=_layout((0, 1)),
        changed_targets=changed_targets,
        immediate_segment_indices=frozenset(
            target.segment_index for target in immediate_targets
        ),
        reason="presenter_test",
        immediate_targets=immediate_targets,
        stale=stale,
    )


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_starts_animations_for_changed_visible_chips() -> None:
    """Presenter should animate paint geometry from planner-provided rects."""

    app, host, chips = _host_with_chips()
    try:
        presenter = PromptReorderAnimationPresenter(parent=host, duration_ms=80)
        plan = _presenter_plan(
            generation=1,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(40.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(plan)
        _process_events(app)

        assert presenter.is_animating() is True
        assert presenter.counters()["animation_started_count"] == 1

        QTest.qWait(120)
        _process_events(app)

        assert presenter.is_animating() is False
        assert presenter.paint_rect_overrides() == {}
        assert presenter.counters()["animation_finished_count"] == 1
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_publishes_paint_rect_overrides_during_animation() -> None:
    """Presenter should expose visible paint rects while widget animation runs."""

    app, host, chips = _host_with_chips()
    frame_count = 0

    def count_frame() -> None:
        nonlocal frame_count
        frame_count += 1

    try:
        presenter = PromptReorderAnimationPresenter(
            parent=host,
            duration_ms=80,
            frame_callback=count_frame,
        )
        plan = _presenter_plan(
            generation=1,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(40.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(plan)
        _process_events(app)

        assert presenter.paint_rect_overrides()[0] == QRectF(0.0, 0.0, 20.0, 10.0)
        assert frame_count >= 1

        QTest.qWait(120)
        _process_events(app)

        assert presenter.paint_rect_overrides() == {}
        assert frame_count >= 2
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_publishes_coherent_multi_chip_frame_overrides() -> None:
    """Presenter should publish one synchronized paint rect snapshot per frame."""

    app, host, chips = _host_with_chips()
    captured_frames: list[dict[int, QRectF]] = []
    presenter_holder: list[PromptReorderAnimationPresenter] = []

    def capture_frame() -> None:
        captured_frames.append(presenter_holder[0].paint_rect_overrides())

    try:
        chips[1].setGeometry(80, 0, 20, 10)
        presenter = PromptReorderAnimationPresenter(
            parent=host,
            duration_ms=160,
            frame_callback=capture_frame,
        )
        presenter_holder.append(presenter)
        plan = _presenter_plan(
            generation=1,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(40.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
                PromptReorderAnimationTarget(
                    segment_index=1,
                    start_rect=QRectF(80.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(120.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(plan)
        QTest.qWait(80)
        _process_events(app)

        non_empty_frames = [frame for frame in captured_frames if frame]

        assert non_empty_frames
        assert all(set(frame) == {0, 1} for frame in non_empty_frames)
        assert all(
            frame[1].left() - frame[0].left() == pytest.approx(80.0, abs=1.0)
            for frame in non_empty_frames
        )

        QTest.qWait(120)
        _process_events(app)
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_retargets_running_animation_without_blank_cancel_frame() -> None:
    """Newer plans should continue from current paint rects without blanking."""

    app, host, chips = _host_with_chips()
    captured_frames: list[dict[int, QRectF]] = []
    presenter_holder: list[PromptReorderAnimationPresenter] = []

    def capture_frame() -> None:
        captured_frames.append(presenter_holder[0].paint_rect_overrides())

    try:
        presenter = PromptReorderAnimationPresenter(
            parent=host,
            duration_ms=200,
            frame_callback=capture_frame,
        )
        presenter_holder.append(presenter)
        first_plan = _presenter_plan(
            generation=1,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(40.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )
        presenter.apply_plan(first_plan)
        QTest.qWait(50)
        _process_events(app)
        retarget_start = presenter.paint_rect_overrides()[0]
        frame_count_before_retarget = len(captured_frames)

        second_plan = _presenter_plan(
            generation=2,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=retarget_start,
                    target_rect=QRectF(80.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )
        presenter.apply_plan(second_plan)
        _process_events(app)

        assert presenter.is_animating() is True
        assert presenter.counters()["animation_cancelled_count"] == 0
        assert presenter.counters()["animation_retargeted_count"] == 1
        assert presenter.paint_rect_overrides()[0] == retarget_start
        assert all(frame for frame in captured_frames[frame_count_before_retarget:])
    finally:
        if presenter_holder:
            presenter_holder[0].cancel(reason="test_cleanup")
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_ignores_stale_generation() -> None:
    """Presenter should reject plans older than the latest accepted generation."""

    app, host, chips = _host_with_chips()
    try:
        presenter = PromptReorderAnimationPresenter(parent=host, duration_ms=80)
        presenter.apply_plan(_presenter_plan(generation=3))
        stale_plan = _presenter_plan(
            generation=2,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(80.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(stale_plan)
        _process_events(app)

        assert presenter.is_animating() is False
        assert presenter.paint_rect_overrides() == {}
        assert presenter.counters()["animation_stale_generation_ignored_count"] == 1
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_cancel_stops_active_animations() -> None:
    """Presenter cancellation should stop the active animation group."""

    app, host, chips = _host_with_chips()
    try:
        presenter = PromptReorderAnimationPresenter(parent=host, duration_ms=200)
        plan = _presenter_plan(
            generation=1,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(80.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(plan)
        _process_events(app)

        assert presenter.is_animating() is True

        presenter.cancel(reason="test_cancel")
        _process_events(app)

        assert presenter.is_animating() is False
        assert presenter.counters()["animation_cancelled_count"] == 1
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_settle_clears_transient_paint_geometry() -> None:
    """Presenter settling should stop active motion and clear paint overrides."""

    app, host, chips = _host_with_chips()
    try:
        presenter = PromptReorderAnimationPresenter(parent=host, duration_ms=200)
        plan = _presenter_plan(
            generation=1,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(64.0, 18.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(plan)
        _process_events(app)
        presenter.settle(reason="test_settle")
        _process_events(app)

        assert presenter.is_animating() is False
        assert presenter.paint_rect_overrides() == {}
        assert presenter.counters()["animation_settled_count"] == 1
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_records_immediate_targets_without_animation() -> None:
    """Immediate targets should publish settled paint without animation state."""

    app, host, chips = _host_with_chips()
    try:
        frame_count = 0

        def count_frame() -> None:
            """Record the settled frame needed by the overlay paint owner."""

            nonlocal frame_count
            frame_count += 1

        presenter = PromptReorderAnimationPresenter(
            parent=host,
            duration_ms=200,
            frame_callback=count_frame,
        )
        plan = _presenter_plan(
            generation=1,
            immediate_targets=(
                PromptReorderAnimationTarget(
                    segment_index=1,
                    start_rect=QRectF(90.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(90.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(plan)
        _process_events(app)

        assert presenter.is_animating() is False
        assert presenter.paint_rect_overrides() == {}
        assert presenter.counters()["animation_immediate_target_count"] == 1
        assert presenter.counters()["animation_started_count"] == 0
        assert frame_count == 1
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_skips_dragged_chip_targets() -> None:
    """Presenter should not move the chip represented by the drag proxy."""

    app, host, chips = _host_with_chips()
    try:
        presenter = PromptReorderAnimationPresenter(parent=host, duration_ms=80)
        plan = _presenter_plan(
            generation=1,
            dragged_segment_index=0,
            changed_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(80.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
                PromptReorderAnimationTarget(
                    segment_index=1,
                    start_rect=QRectF(24.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(48.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
            immediate_targets=(
                PromptReorderAnimationTarget(
                    segment_index=0,
                    start_rect=QRectF(0.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(96.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(plan)
        _process_events(app)

        assert presenter.is_animating() is True
        assert set(presenter.paint_rect_overrides()) == {1}
        assert presenter.counters()["animation_skipped_target_count"] == 2

        QTest.qWait(120)
        _process_events(app)

        assert presenter.paint_rect_overrides() == {}
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


@_WINDOWS_XDIST_QT_SKIP
def test_presenter_cancel_after_immediate_target_is_a_noop() -> None:
    """Immediate targets should leave no transient animation state to cancel."""

    app, host, chips = _host_with_chips()
    try:
        presenter = PromptReorderAnimationPresenter(parent=host, duration_ms=200)
        plan = _presenter_plan(
            generation=1,
            immediate_targets=(
                PromptReorderAnimationTarget(
                    segment_index=1,
                    start_rect=QRectF(90.0, 0.0, 20.0, 10.0),
                    target_rect=QRectF(90.0, 0.0, 20.0, 10.0),
                    target_visible=True,
                ),
            ),
        )

        presenter.apply_plan(plan)
        _process_events(app)

        presenter.cancel(reason="test_cancel_immediate")
        presenter.settle(reason="test_settle_after_cancel")
        _process_events(app)

        assert presenter.paint_rect_overrides() == {}
        assert presenter.counters()["animation_cancelled_count"] == 0
        assert presenter.counters()["animation_settled_count"] == 0
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)
