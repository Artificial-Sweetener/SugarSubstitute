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

"""Verify deterministic reorder animation frame publication and retargeting."""

from __future__ import annotations


import pytest
from PySide6.QtCore import QRectF

from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presenter import (
    PromptReorderAnimationPresenter,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_animation import (
    PromptReorderAnimationTarget,
)
from tests.presentation.editor.prompt_editor.reorder.animation.presenter_support import (
    _host_with_chips,
    _presenter_plan,
    _process_events,
    _set_presenter_animation_time,
)


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

        _set_presenter_animation_time(presenter, 80)
        _process_events(app)

        assert presenter.is_animating() is False
        assert presenter.paint_rect_overrides() == {}
        assert presenter.counters()["animation_finished_count"] == 1
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


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

        assert presenter.paint_rect_overrides()[0] == QRectF(0.0, 0.0, 20.0, 10.0)
        assert frame_count >= 1

        _set_presenter_animation_time(presenter, 80)
        _process_events(app)

        assert presenter.paint_rect_overrides() == {}
        assert frame_count >= 2
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


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
        _set_presenter_animation_time(presenter, 80)
        _process_events(app)

        non_empty_frames = [frame for frame in captured_frames if frame]

        assert non_empty_frames
        assert all(set(frame) == {0, 1} for frame in non_empty_frames)
        assert all(
            frame[1].left() - frame[0].left() == pytest.approx(80.0, abs=1.0)
            for frame in non_empty_frames
        )

        _set_presenter_animation_time(presenter, 160)
        _process_events(app)
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


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
        _set_presenter_animation_time(presenter, 50)
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
