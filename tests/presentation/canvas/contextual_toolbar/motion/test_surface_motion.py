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

"""Verify canonical and interruptible Contextual Toolbar shell motion."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, qInstallMessageHandler
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_SURFACE_HEIGHT,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
    ContextualToolbarPage,
    ContextualToolbarPlacementUpdate,
)
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition

from .support import MotionPage, effective_opacity, qt_application


def test_reduced_motion_settles_canonical_single_row_immediately() -> None:
    """Reduced motion must retain exact 28/36 geometry without transient state."""
    qapp = qt_application()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", True)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        toolbar.set_context_rect(
            QRect(100, 100, 80, 40),
            update=ContextualToolbarPlacementUpdate.RESET,
        )
        page = toolbar.set_content("one", lambda parent: MotionPage(120, parent))
        wait_for_qt_condition(lambda: page.geometry() == toolbar.content_host.rect())

        assert page.height() == CANVAS_CHROME_CONTROL_HEIGHT
        assert toolbar.height() == CANVAS_CHROME_SURFACE_HEIGHT == 36
        toolbar.clear_content()
        wait_for_qt_condition(lambda: not toolbar.isVisible())
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous)


def test_context_set_before_page_mount_anchors_with_final_shell_geometry() -> None:
    """A newly selected context must not retain empty-shell placement geometry."""

    qapp = qt_application()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", True)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    selection = QRect(240, 100, 80, 40)
    try:
        toolbar.set_context_rect(
            selection,
            update=ContextualToolbarPlacementUpdate.RESET,
        )
        toolbar.set_content("selection", lambda parent: MotionPage(180, parent))
        wait_for_qt_condition(
            lambda: abs(toolbar.geometry().center().x() - selection.center().x()) <= 1
        )

        assert abs(toolbar.geometry().center().x() - selection.center().x()) <= 1
        assert toolbar.y() == selection.bottom() + 13
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous)


def test_new_context_ignores_page_lingering_during_prior_dismissal() -> None:
    """A rapid new selection must not project through a fading previous page."""

    qapp = qt_application()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    selection = QRect(240, 100, 80, 40)
    try:
        toolbar.set_content("previous", lambda parent: MotionPage(90, parent))
        wait_for_qt_condition(
            lambda: toolbar.isVisible() and toolbar.graphicsEffect() is None
        )
        toolbar.clear_content()
        assert toolbar.page is not None

        toolbar.set_context_rect(
            selection,
            update=ContextualToolbarPlacementUpdate.RESET,
        )
        toolbar.set_content("selection", lambda parent: MotionPage(180, parent))
        wait_for_qt_condition(
            lambda: (
                toolbar.isVisible()
                and toolbar.graphicsEffect() is None
                and toolbar.content_host.graphicsEffect() is None
            )
        )

        assert abs(toolbar.geometry().center().x() - selection.center().x()) <= 1
        assert toolbar.y() == selection.bottom() + 13
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous)


def test_rapid_page_retarget_preserves_shell_focus_and_latest_generation() -> None:
    """Rapid replacements must finish on the latest page with no stale receivers."""
    qapp = qt_application()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        first = toolbar.set_content("first", lambda parent: MotionPage(90, parent))
        assert isinstance(first, MotionPage)
        wait_for_qt_condition(
            lambda: toolbar.isVisible() and toolbar.graphicsEffect() is None
        )
        first.button.setFocus(Qt.FocusReason.OtherFocusReason)
        assert QApplication.focusWidget() is first.button

        toolbar.set_content("second", lambda parent: MotionPage(180, parent))
        latest = toolbar.set_content("latest", lambda parent: MotionPage(140, parent))
        assert isinstance(latest, MotionPage)
        wait_for_qt_condition(
            lambda: (
                toolbar.page is latest
                and toolbar.content_host.graphicsEffect() is None
                and latest.button.isEnabled()
            )
        )

        assert QApplication.focusWidget() is latest.button
        assert toolbar.page is latest
        assert toolbar.height() == CANVAS_CHROME_SURFACE_HEIGHT
        assert toolbar.content_host.findChildren(ContextualToolbarPage) == [latest]
        toolbar.set_suppressed(True)
        assert toolbar.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        wait_for_qt_condition(lambda: not toolbar.isVisible())
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous)


def test_dismissal_retains_full_shell_geometry_until_hidden_then_releases_page() -> (
    None
):
    """Dismissal must never expose an empty collapsed shell between page and hide."""

    qapp = qt_application()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        page = toolbar.set_content("selection", lambda parent: MotionPage(180, parent))
        wait_for_qt_condition(
            lambda: toolbar.isVisible() and effective_opacity(page) >= 0.99
        )
        visible_size = toolbar.size()

        toolbar.clear_content()
        toolbar.set_suppressed(False)

        assert toolbar.isVisible()
        assert toolbar.size() == visible_size
        assert toolbar.page is page
        assert toolbar.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        wait_for_qt_condition(lambda: not toolbar.isVisible())
        assert toolbar.page is None
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous)


def test_shell_hide_after_page_crossfade_never_reenters_qt_painting() -> None:
    """Nested toolbar motion must not ask Qt to paint one device recursively."""

    qapp = qt_application()
    previous_motion = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    messages: list[str] = []

    def capture_message(_kind: object, _context: object, message: str) -> None:
        """Record Qt diagnostics emitted by the exercised paint path."""

        messages.append(message)

    previous_handler = qInstallMessageHandler(capture_message)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        first = toolbar.set_content("selection", lambda parent: MotionPage(140, parent))
        wait_for_qt_condition(
            lambda: (
                toolbar.isVisible()
                and effective_opacity(first) >= 0.99
                and toolbar.graphicsEffect() is None
            )
        )
        assert toolbar.graphicsEffect() is None
        assert first.graphicsEffect() is None
        second = toolbar.set_content(
            "transform", lambda parent: MotionPage(220, parent)
        )
        assert toolbar.graphicsEffect() is None
        wait_for_qt_condition(
            lambda: (
                effective_opacity(second) >= 0.99
                and toolbar.content_host.graphicsEffect() is None
            )
        )
        assert second.graphicsEffect() is None

        toolbar.set_suppressed(True)
        assert toolbar.graphicsEffect() is not None
        assert second.graphicsEffect() is None
        wait_for_qt_condition(lambda: not toolbar.isVisible())

        paint_failures = tuple(
            message
            for message in messages
            if "paint device can only be painted by one painter" in message
            or "Painter not active" in message
        )
        assert not paint_failures
    finally:
        destroy_qt_object(viewport)
        qInstallMessageHandler(previous_handler)
        qapp.setProperty("substitute.reduce_motion", previous_motion)


def test_hidden_page_retarget_keeps_entry_motion_on_shell_only() -> None:
    """A page replaced while suppressed must not nest under the entering effect."""

    qapp = qt_application()
    previous_motion = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        first = toolbar.set_content("selection", lambda parent: MotionPage(140, parent))
        wait_for_qt_condition(
            lambda: toolbar.isVisible() and toolbar.graphicsEffect() is None
        )
        assert first.graphicsEffect() is None
        toolbar.set_suppressed(True)
        wait_for_qt_condition(lambda: not toolbar.isVisible())

        second = toolbar.set_content(
            "transform",
            lambda parent: MotionPage(220, parent),
        )
        assert toolbar.graphicsEffect() is None
        assert second.graphicsEffect() is None

        toolbar.set_suppressed(False)
        assert toolbar.graphicsEffect() is not None
        assert second.graphicsEffect() is None
        wait_for_qt_condition(
            lambda: toolbar.isVisible() and toolbar.graphicsEffect() is None
        )
    finally:
        destroy_qt_object(viewport)
        qapp.setProperty("substitute.reduce_motion", previous_motion)
