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

from _pytest.monkeypatch import MonkeyPatch
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.presentation.motion.controller import SurfaceMotionController
from substitute.presentation.motion.models import MotionSpec
from substitute.presentation.motion.overlay import MotionOverlay
from tools.editor_projection_rig.qt_harness import ensure_qapplication


def _mounted_surface() -> tuple[QWidget, QLabel]:
    """Return one visible surface and target suitable for capture."""

    ensure_qapplication()
    viewport = QWidget()
    viewport.resize(320, 180)
    target = QLabel("Committed card", viewport)
    target.setGeometry(30, 40, 180, 52)
    target.show()
    viewport.show()
    QApplication.processEvents()
    return viewport, target


def test_zero_duration_settles_without_overlay(monkeypatch: MonkeyPatch) -> None:
    """Reduced or disabled motion should expose committed pixels immediately."""

    viewport, target = _mounted_surface()
    controller = SurfaceMotionController(viewport_provider=lambda: viewport)
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

    viewport, target = _mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
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

    viewport, target = _mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
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

    viewport, target = _mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
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

    viewport, target = _mounted_surface()
    controller = SurfaceMotionController(
        viewport_provider=lambda: viewport,
        default_spec=MotionSpec(duration_ms=500),
    )
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
