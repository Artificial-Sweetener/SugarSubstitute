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

"""Test shared structural motion through a real Qt viewport."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from _pytest.monkeypatch import MonkeyPatch
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QWidget

from substitute.presentation.motion.controller import SurfaceMotionController
from substitute.presentation.motion.models import MotionSpec
from substitute.presentation.motion.overlay import MotionOverlay
from tests.presentation.motion.support import (
    ManualMotionClock,
    manual_clock_factory,
    mounted_surface,
)
from tests.support.qt.lifecycle import widget_root_scope
from tools.editor_projection_rig.qt_harness import ensure_qapplication


@pytest.fixture(autouse=True)
def _destroy_motion_widget_roots() -> Iterator[None]:
    """Synchronously destroy every native widget root created by one test."""

    with widget_root_scope():
        yield


def test_zero_duration_settles_without_overlay(monkeypatch: MonkeyPatch) -> None:
    """Reduced or disabled motion should expose committed pixels immediately."""

    viewport, target = mounted_surface()
    controller = SurfaceMotionController(viewport_provider=lambda: viewport)
    controller.setParent(viewport)
    monkeypatch.setattr(
        "substitute.presentation.motion.controller.resolve_motion_duration",
        lambda _duration: 0,
    )

    generation = controller.prepare(reason="cube_insert")
    assert generation is not None
    started = controller.animate_widgets(
        generation=generation,
        widgets=(("cube:A", target),),
    )

    assert started is False
    assert controller.is_animating() is False
    assert viewport.findChildren(MotionOverlay) == []
    assert controller.telemetry.plans_settled_immediately == 1
    viewport.close()


def test_active_motion_uses_one_mouse_transparent_overlay_and_cancels() -> None:
    """One timeline and overlay should cover the transition and cleanly cancel."""

    viewport, target = mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
    controller.setParent(viewport)
    generation = controller.prepare(reason="cube_insert")
    assert generation is not None

    assert controller.animate_widgets(
        generation=generation,
        widgets=(("cube:A", target),),
    )
    QApplication.processEvents()
    overlays = viewport.findChildren(MotionOverlay)

    assert len(overlays) == 1
    assert overlays[0].testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert target.isVisible() is True
    assert controller.is_animating() is True

    controller.cancel(reason="user_scroll")
    QApplication.processEvents()

    assert controller.is_animating() is False
    assert overlays[0].isVisible() is False
    assert controller.telemetry.plans_cancelled == 1
    viewport.close()


def test_new_prepare_supersedes_active_generation() -> None:
    """A newer structural change should settle the prior visual generation."""

    viewport, target = mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
    controller.setParent(viewport)
    first = controller.prepare(reason="first")
    assert first is not None
    assert controller.animate_widgets(
        generation=first,
        widgets=(("cube:A", target),),
    )

    second = controller.prepare(reason="second")

    assert second is not None and second > first
    assert controller.is_animating() is False
    assert controller.telemetry.plans_cancelled == 1
    viewport.close()


def test_viewport_resize_cancels_active_motion() -> None:
    """Geometry changes should remove the stale overlay in the same event turn."""

    viewport, target = mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
    controller.setParent(viewport)
    generation = controller.prepare(reason="cube_insert")
    assert generation is not None
    assert controller.animate_widgets(
        generation=generation,
        widgets=(("cube:A", target),),
    )

    viewport.resize(360, 200)
    QApplication.processEvents()

    assert controller.is_animating() is False
    assert controller.telemetry.plans_cancelled == 1
    viewport.close()


def test_direct_input_and_surface_hide_cancel_motion() -> None:
    """Real user input and teardown should synchronously expose final pixels."""

    viewport, target = mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
    controller.setParent(viewport)
    generation = controller.prepare(reason="cube_insert")
    assert generation is not None
    assert controller.animate_widgets(
        generation=generation,
        widgets=(("cube:A", target),),
    )

    controller.eventFilter(viewport, QEvent(QEvent.Type.MouseButtonPress))
    assert controller.is_animating() is False

    next_generation = controller.prepare(reason="node_card_replace")
    assert next_generation is not None
    assert controller.animate_widgets(
        generation=next_generation,
        widgets=(("node-card:A:N", target),),
    )
    viewport.hide()
    QApplication.processEvents()

    assert controller.is_animating() is False
    assert controller.telemetry.plans_cancelled == 2


def test_input_delivered_to_descendant_cancels_motion() -> None:
    """Direct manipulation of a real child should settle the overlay immediately."""

    viewport, target = mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
    controller.setParent(viewport)
    generation = controller.prepare(reason="cube_insert")
    assert generation is not None
    assert controller.animate_widgets(
        generation=generation,
        widgets=(("cube:A", target),),
    )

    QTest.mousePress(target, Qt.MouseButton.LeftButton)

    assert controller.is_animating() is False
    assert controller.telemetry.plans_cancelled == 1
    viewport.close()


def test_injected_clock_finishes_and_disposes_overlay() -> None:
    """Natural completion should be deterministic and release visual proxies."""

    viewport, target = mounted_surface()
    clock = ManualMotionClock()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=180),
        clock_factory=manual_clock_factory(clock),
    )
    controller.setParent(viewport)
    generation = controller.prepare(reason="cube_insert")
    assert generation is not None
    assert controller.animate_widgets(
        generation=generation,
        widgets=(("cube:A", target),),
    )
    overlays = viewport.findChildren(MotionOverlay)

    clock.advance(90.0)
    QApplication.processEvents()
    assert controller.is_animating() is True

    clock.finish()
    QApplication.processEvents()

    assert controller.is_animating() is False
    assert controller.telemetry.plans_finished == 1
    assert len(overlays) == 1
    assert overlays[0].isVisible() is False
    viewport.close()


def test_target_capture_count_and_memory_are_bounded() -> None:
    """One transition should retain only a bounded visible snapshot set."""

    ensure_qapplication()
    viewport = QWidget()
    viewport.resize(400, 240)
    targets: list[tuple[str, QWidget]] = []
    for index in range(30):
        target = QLabel(str(index), viewport)
        target.setGeometry((index % 10) * 35, (index // 10) * 40, 30, 30)
        target.show()
        targets.append((str(index), target))
    viewport.show()
    QApplication.processEvents()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
    controller.setParent(viewport)
    generation = controller.prepare(reason="bounded_targets")
    assert generation is not None

    assert controller.animate_widgets(generation=generation, widgets=targets)

    assert controller.telemetry.last_capture_target_count == 24
    assert controller.telemetry.last_capture_target_pixels <= 4_000_000
    controller.cancel(reason="test_complete")
    viewport.close()


def test_layout_motion_moves_retained_target_from_old_to_new_rect() -> None:
    """A retained surface should visibly traverse its committed geometry delta."""

    viewport, target = mounted_surface()
    target.setStyleSheet("background: rgb(20, 120, 220);")
    clock = ManualMotionClock()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        clock_factory=manual_clock_factory(clock),
    )
    controller.setParent(viewport)
    generation = controller.prepare(
        reason="cube_reorder",
        widgets=(("cube:A", target),),
    )
    assert generation is not None
    target.move(30, 100)

    assert controller.animate_layout(
        generation=generation,
        widgets=(("cube:A", target),),
        spec=MotionSpec(duration_ms=250, stagger_ms=0),
    )
    overlay = viewport.findChild(MotionOverlay)
    assert overlay is not None

    clock.advance(0.0)
    QApplication.processEvents()
    start = overlay.grab().toImage()
    assert QColor(start.pixel(40, 50)).blue() > 150

    clock.advance(125.0)
    QApplication.processEvents()
    middle = overlay.grab().toImage()
    assert QColor(middle.pixel(40, 85)).blue() > 150

    clock.advance(250.0)
    QApplication.processEvents()
    end = overlay.grab().toImage()
    assert QColor(end.pixel(40, 110)).blue() > 150
    viewport.close()


def test_layout_motion_animates_entry_and_exit_on_final_background() -> None:
    """One plan should fade entering and exiting surfaces without live duplicates."""

    viewport, exiting = mounted_surface()
    exiting.setStyleSheet("background: rgb(220, 40, 40);")
    clock = ManualMotionClock()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        clock_factory=manual_clock_factory(clock),
    )
    controller.setParent(viewport)
    generation = controller.prepare(
        reason="replace",
        widgets=(("old", exiting),),
    )
    assert generation is not None
    exiting.hide()
    entering = QLabel("New", viewport)
    entering.setStyleSheet("background: rgb(40, 190, 80);")
    entering.setGeometry(30, 100, 180, 52)
    entering.show()

    assert controller.animate_layout(
        generation=generation,
        widgets=(("new", entering),),
        spec=MotionSpec(duration_ms=250, stagger_ms=0, translation_y=16.0),
        exit_translation_y=-8.0,
    )
    overlay = viewport.findChild(MotionOverlay)
    assert overlay is not None
    assert entering.isVisible() is True

    clock.advance(0.0)
    QApplication.processEvents()
    start = overlay.grab().toImage()
    assert QColor(start.pixel(40, 50)).red() > 150
    assert QColor(start.pixel(40, 110)).red() > 200

    clock.advance(250.0)
    QApplication.processEvents()
    end = overlay.grab().toImage()
    assert QColor(end.pixel(40, 110)).green() > 150
    assert QColor(end.pixel(40, 110)).red() < 100
    departed_pixel = QColor(end.pixel(40, 50))
    assert abs(departed_pixel.red() - departed_pixel.green()) < 5
    viewport.close()


def test_target_free_capture_preserves_focus_visibility_and_geometry() -> None:
    """Snapshot preparation must not perturb committed widgets or focused input."""

    ensure_qapplication()
    viewport = QWidget()
    viewport.resize(320, 180)
    target = QWidget(viewport)
    target.setGeometry(20, 30, 220, 70)
    editor = QLineEdit(target)
    editor.setGeometry(10, 10, 180, 32)
    target.show()
    viewport.show()
    editor.setFocus()
    QApplication.processEvents()
    original_geometry = target.geometry()
    clock = ManualMotionClock()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        clock_factory=manual_clock_factory(clock),
    )
    controller.setParent(viewport)
    generation = controller.prepare(
        reason="focus_safe",
        widgets=(("cube:A", target),),
    )
    assert generation is not None
    target.move(20, 80)

    assert controller.animate_layout(
        generation=generation,
        widgets=(("cube:A", target),),
    )

    assert target.isVisible() is True
    assert target.geometry() == original_geometry.translated(0, 50)
    assert editor.hasFocus() is True
    controller.cancel(reason="test_complete")
    viewport.close()
