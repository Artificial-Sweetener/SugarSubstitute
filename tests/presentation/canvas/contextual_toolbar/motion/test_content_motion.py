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

"""Verify contextual-toolbar content morphing and interruption."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
    ContextualToolbarPage,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition

from .support import MotionPage, effective_opacity, qt_application


def test_page_geometry_change_never_blanks_already_visible_controls() -> None:
    """Late layout publication must not restart the current page's opacity."""

    qapp = qt_application()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        page = toolbar.set_content("transform", lambda parent: MotionPage(180, parent))
        assert isinstance(page, MotionPage)
        wait_for_qt_condition(
            lambda: toolbar.isVisible() and effective_opacity(page) >= 0.99
        )

        page.geometryChanged.emit()
        wait_for_qt_condition(lambda: page.geometry() == toolbar.content_host.rect())

        assert effective_opacity(page) >= 0.99
        assert page.button.isVisible()
        assert page.geometry() == toolbar.content_host.rect()
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous)


def test_interrupted_crossfade_never_restores_partial_page_to_full_opacity() -> None:
    """Replacing an incoming page must fade from its rendered opacity without flash."""

    qapp = qt_application()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        first = toolbar.set_content("first", lambda parent: MotionPage(90, parent))
        wait_for_qt_condition(lambda: effective_opacity(first) >= 0.99)
        toolbar.set_content("second", lambda parent: MotionPage(180, parent))
        effect = toolbar.content_host.graphicsEffect()
        assert isinstance(effect, QGraphicsOpacityEffect)
        interrupted_opacity: list[tuple[float, float]] = []

        def interrupt_at_partial_opacity(value: float) -> None:
            """Interrupt synchronously at an observed partial render sample."""

            rendered_opacity = float(value)
            if interrupted_opacity or not 0.05 < rendered_opacity < 0.95:
                return
            toolbar.set_content("latest", lambda parent: MotionPage(140, parent))
            interrupted_opacity.append((rendered_opacity, float(effect.opacity())))

        effect.opacityChanged.connect(interrupt_at_partial_opacity)
        wait_for_qt_condition(lambda: bool(interrupted_opacity))

        rendered_opacity, retained_opacity = interrupted_opacity[0]
        assert retained_opacity <= rendered_opacity + 0.05
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous)


def test_page_and_controls_remain_inside_shell_through_every_morph_sample() -> None:
    """Animated geometry must never displace page content beyond its shell."""

    qapp = qt_application()
    previous_motion = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    violations: list[str] = []

    def sample_geometry() -> None:
        """Record any page or control that escapes its authoritative host."""

        host = toolbar.content_host
        if toolbar.graphicsEffect() is not None and host.graphicsEffect() is not None:
            violations.append("nested-shell-and-content-effects")
        for page in host.findChildren(ContextualToolbarPage):
            if page.graphicsEffect() is not None:
                violations.append("page-effect-installed")
            if page.pos() != QPoint():
                violations.append(f"page-origin={page.pos()}")
            if page.geometry() != host.rect():
                violations.append(f"page={page.geometry()} host={host.rect()}")
            for control in page.findChildren(QWidget):
                top_left = control.mapTo(page, QPoint())
                bounds = QRect(top_left, control.size())
                if control.isVisible() and not page.rect().contains(bounds):
                    violations.append(f"control={bounds} page={page.rect()}")

    try:
        first = toolbar.set_content("first", lambda parent: MotionPage(90, parent))
        wait_for_qt_condition(
            lambda: toolbar.isVisible() and toolbar.graphicsEffect() is None
        )
        assert first.isVisible()
        toolbar.content_host.geometryChanged.connect(sample_geometry)
        toolbar.set_content("second", lambda parent: MotionPage(220, parent))

        def wait_for_morph() -> None:
            """Wait for terminal owner state while geometry signals capture samples."""

            wait_for_qt_condition(
                lambda: (
                    toolbar.content_host.graphicsEffect() is None
                    and toolbar.content_host.size() == toolbar.content_host.sizeHint()
                )
            )
            sample_geometry()

        wait_for_morph()
        toolbar.set_content("third", lambda parent: MotionPage(70, parent))
        wait_for_morph()
        toolbar.set_content("fourth", lambda parent: MotionPage(260, parent))
        wait_for_qt_condition(
            lambda: (
                isinstance(
                    effect := toolbar.content_host.graphicsEffect(),
                    QGraphicsOpacityEffect,
                )
                and 0.05 < effect.opacity() < 0.95
            )
        )
        toolbar.set_content("latest", lambda parent: MotionPage(110, parent))
        wait_for_morph()

        assert not violations
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous_motion)
