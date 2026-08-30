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

"""Verify reorder animation cancellation, settlement, and target filtering."""

from __future__ import annotations


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

        _set_presenter_animation_time(presenter, 80)
        _process_events(app)

        assert presenter.paint_rect_overrides() == {}
    finally:
        host.close()
        host.deleteLater()
        _process_events(app)


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
