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

"""Tests for the production splash paper-flip widget state machine."""

from __future__ import annotations

import os
import random
from typing import cast

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import pytest

from substitute.presentation.splash_animation.paper_flip_widget import (
    SplashFlipPhase,
    SplashFlipSettings,
    SplashPaperFlipWidget,
)
from substitute.presentation.splash_animation.pose_library import SplashPose
from substitute.presentation.splash_animation.pose_selector import (
    RecencyWeightedPoseSelector,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "splash paper flip Qt tests require non-xdist execution",
        allow_module_level=True,
    )


class ManualClock:
    """Provide deterministic monotonic time for widget state tests."""

    def __init__(self) -> None:
        """Initialize the clock at zero seconds."""

        self.now = 0.0

    def __call__(self) -> float:
        """Return the current manual time."""

        return self.now

    def advance_ms(self, milliseconds: int) -> None:
        """Advance the clock by a millisecond interval."""

        self.now += milliseconds / 1000.0


def _app() -> QApplication:
    """Return the shared QApplication required for QWidget construction."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _pose(name: str, color: QColor) -> SplashPose:
    """Return one tiny valid splash pose for widget tests."""

    pixmap = QPixmap(8, 8)
    pixmap.fill(color)
    return SplashPose(
        name=name,
        resource_path=f":/test/{name}",
        pixmap=pixmap,
        base_weight=1.0,
    )


def test_widget_starts_with_current_and_next_pose() -> None:
    """Widget construction should queue a next pose immediately."""

    _app()
    poses = (_pose("1.png", QColor("red")), _pose("2.png", QColor("blue")))
    selector = RecencyWeightedPoseSelector(poses, seed=1)

    widget = SplashPaperFlipWidget(poses, selector)

    assert widget.current_pose is poses[0]
    assert widget.next_pose is poses[1]
    assert widget.phase is SplashFlipPhase.HOLD
    widget.close()


def test_widget_samples_hold_duration_within_jitter_range() -> None:
    """The active hold duration should be jittered around the configured base."""

    _app()
    poses = (_pose("1.png", QColor("red")), _pose("2.png", QColor("blue")))
    selector = RecencyWeightedPoseSelector(poses, seed=1)
    settings = SplashFlipSettings(base_hold_ms=950, hold_jitter_ms=150)

    widget = SplashPaperFlipWidget(
        poses,
        selector,
        settings=settings,
        hold_random=random.Random(4),
    )

    assert 800 <= widget.current_hold_ms <= 1100
    widget.close()


def test_widget_reports_zero_progress_during_hold() -> None:
    """Hold phases should keep the rendered flip progress at the front face."""

    _app()
    clock = ManualClock()
    poses = (_pose("1.png", QColor("red")), _pose("2.png", QColor("blue")))
    selector = RecencyWeightedPoseSelector(poses, seed=1)
    widget = SplashPaperFlipWidget(poses, selector, clock=clock)

    clock.advance_ms(500)

    assert widget._current_progress() == 0.0
    widget.close()


def test_widget_renders_next_pose_at_halfway_point() -> None:
    """The queued pose should become the painted pose at the flip midpoint."""

    _app()
    clock = ManualClock()
    poses = (_pose("1.png", QColor("red")), _pose("2.png", QColor("blue")))
    selector = RecencyWeightedPoseSelector(poses, seed=1)
    settings = SplashFlipSettings(base_hold_ms=100, hold_jitter_ms=0, flip_ms=120)
    widget = SplashPaperFlipWidget(poses, selector, settings=settings, clock=clock)
    queued_pose = widget.next_pose

    clock.advance_ms(100)
    widget._tick()
    clock.advance_ms(60)

    assert widget._current_render_pose(widget._current_progress()) is queued_pose
    widget.close()


def test_widget_trigger_flip_starts_immediate_flip_during_hold() -> None:
    """The mascot click action should start the existing flip path immediately."""

    _app()
    clock = ManualClock()
    poses = (_pose("1.png", QColor("red")), _pose("2.png", QColor("blue")))
    selector = RecencyWeightedPoseSelector(poses, seed=1)
    widget = SplashPaperFlipWidget(poses, selector, clock=clock)

    assert widget.trigger_flip() is True
    assert widget.phase is SplashFlipPhase.FLIP

    widget.close()


def test_widget_trigger_flip_ignores_active_flip() -> None:
    """Repeated mascot clicks should not restart an in-progress transition."""

    _app()
    clock = ManualClock()
    poses = (_pose("1.png", QColor("red")), _pose("2.png", QColor("blue")))
    selector = RecencyWeightedPoseSelector(poses, seed=1)
    widget = SplashPaperFlipWidget(poses, selector, clock=clock)

    assert widget.trigger_flip() is True
    started_at = widget._phase_started_at
    clock.advance_ms(10)

    assert widget.trigger_flip() is False
    assert widget.phase is SplashFlipPhase.FLIP
    assert widget._phase_started_at == started_at

    widget.close()


def test_widget_left_click_starts_immediate_flip() -> None:
    """Left-clicking the mascot should trigger the easter-egg flip."""

    _app()
    poses = (_pose("1.png", QColor("red")), _pose("2.png", QColor("blue")))
    selector = RecencyWeightedPoseSelector(poses, seed=1)
    widget = SplashPaperFlipWidget(poses, selector)
    widget.show()

    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)

    assert widget.phase is SplashFlipPhase.FLIP
    widget.close()


def test_widget_card_bounds_preserve_source_aspect_ratio() -> None:
    """PSD layer rectangles should not stretch source pose art."""

    _app()
    poses = (_pose("1.png", QColor("red")), _pose("2.png", QColor("blue")))
    selector = RecencyWeightedPoseSelector(poses, seed=1)
    widget = SplashPaperFlipWidget(poses, selector)
    widget.resize(387, 386)

    bounds = widget._card_bounds(QRectF(0.0, 0.0, 1254.0, 1254.0))

    assert bounds.width() == pytest.approx(bounds.height())
    assert bounds.height() == pytest.approx(386.0)
    assert bounds.left() == pytest.approx(0.5)
    widget.close()


def test_widget_commits_next_pose_after_flip_completion() -> None:
    """A completed flip should promote the queued next pose and return to hold."""

    _app()
    clock = ManualClock()
    poses = (
        _pose("1.png", QColor("red")),
        _pose("2.png", QColor("blue")),
        _pose("3.png", QColor("green")),
    )
    selector = RecencyWeightedPoseSelector(poses, seed=3)
    settings = SplashFlipSettings(base_hold_ms=100, hold_jitter_ms=0, flip_ms=120)
    widget = SplashPaperFlipWidget(poses, selector, settings=settings, clock=clock)
    first_next = widget.next_pose

    clock.advance_ms(100)
    widget._tick()
    assert widget.phase.value == SplashFlipPhase.FLIP.value

    clock.advance_ms(120)
    widget._tick()

    assert widget.phase.value == SplashFlipPhase.HOLD.value
    assert widget.current_pose is first_next
    assert widget.current_hold_ms == 100
    widget.close()
