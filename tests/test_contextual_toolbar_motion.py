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

from collections.abc import Callable

from PySide6.QtCore import QPoint, QCoreApplication, QRect, Qt, qInstallMessageHandler
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget

from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_SURFACE_HEIGHT,
)
from substitute.presentation.canvas.shared.contextual_toolbar import (
    CanvasContextualToolbar,
    ContextualToolbarPage,
    ContextualToolbarPlacementUpdate,
)


class _MotionPage(ContextualToolbarPage):
    """Provide deterministic intrinsic width and one focusable control."""

    def __init__(self, width: int, parent: QWidget) -> None:
        """Create one canonical row with a fixed-width button."""
        super().__init__(parent)
        self.button = QPushButton("Control", self)
        self.button.setFixedSize(width, CANVAS_CHROME_CONTROL_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.button)


def _app() -> QApplication:
    """Return the shared GUI application required by toolbar widgets."""
    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _wait_until(predicate: Callable[[], bool], *, timeout_ms: int = 1000) -> None:
    """Wait for one observable animation state with a bounded event loop."""

    elapsed = 0
    while not predicate() and elapsed < timeout_ms:
        QTest.qWait(5)
        elapsed += 5
    assert predicate()


def _opacity(page: ContextualToolbarPage) -> float:
    """Return one page's effective host opacity for motion assertions."""

    parent = page.parentWidget()
    effect = None if parent is None else parent.graphicsEffect()
    opacity = getattr(effect, "opacity", None)
    return 1.0 if not callable(opacity) else float(opacity())


def test_reduced_motion_settles_canonical_single_row_immediately() -> None:
    """Reduced motion must retain exact 28/36 geometry without transient state."""
    qapp = _app()
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
        page = toolbar.set_content("one", lambda parent: _MotionPage(120, parent))
        qapp.processEvents()

        assert page.height() == CANVAS_CHROME_CONTROL_HEIGHT
        assert toolbar.height() == CANVAS_CHROME_SURFACE_HEIGHT == 36
        toolbar.clear_content()
        qapp.processEvents()
        assert not toolbar.isVisible()
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous)


def test_context_set_before_page_mount_anchors_with_final_shell_geometry() -> None:
    """A newly selected context must not retain empty-shell placement geometry."""

    qapp = _app()
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
        toolbar.set_content("selection", lambda parent: _MotionPage(180, parent))
        qapp.processEvents()

        assert abs(toolbar.geometry().center().x() - selection.center().x()) <= 1
        assert toolbar.y() == selection.bottom() + 13
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous)


def test_new_context_ignores_page_lingering_during_prior_dismissal() -> None:
    """A rapid new selection must not project through a fading previous page."""

    qapp = _app()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    selection = QRect(240, 100, 80, 40)
    try:
        toolbar.set_content("previous", lambda parent: _MotionPage(90, parent))
        QTest.qWait(220)
        toolbar.clear_content()
        assert toolbar.page is not None

        toolbar.set_context_rect(
            selection,
            update=ContextualToolbarPlacementUpdate.RESET,
        )
        toolbar.set_content("selection", lambda parent: _MotionPage(180, parent))
        QTest.qWait(220)
        qapp.processEvents()

        assert abs(toolbar.geometry().center().x() - selection.center().x()) <= 1
        assert toolbar.y() == selection.bottom() + 13
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous)


def test_rapid_page_retarget_preserves_shell_focus_and_latest_generation() -> None:
    """Rapid replacements must finish on the latest page with no stale receivers."""
    qapp = _app()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        first = toolbar.set_content("first", lambda parent: _MotionPage(90, parent))
        assert isinstance(first, _MotionPage)
        QTest.qWait(220)
        first.button.setFocus(Qt.FocusReason.OtherFocusReason)
        assert QApplication.focusWidget() is first.button

        toolbar.set_content("second", lambda parent: _MotionPage(180, parent))
        latest = toolbar.set_content("latest", lambda parent: _MotionPage(140, parent))
        assert isinstance(latest, _MotionPage)
        QTest.qWait(240)
        qapp.processEvents()

        assert QApplication.focusWidget() is latest.button
        assert toolbar.page is latest
        assert toolbar.height() == CANVAS_CHROME_SURFACE_HEIGHT
        assert toolbar.content_host.findChildren(ContextualToolbarPage) == [latest]
        toolbar.set_suppressed(True)
        assert toolbar.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        _wait_until(lambda: not toolbar.isVisible())
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous)


def test_page_geometry_change_never_blanks_already_visible_controls() -> None:
    """Late layout publication must not restart the current page's opacity."""

    qapp = _app()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        page = toolbar.set_content("transform", lambda parent: _MotionPage(180, parent))
        assert isinstance(page, _MotionPage)
        _wait_until(lambda: toolbar.isVisible() and _opacity(page) >= 0.99)

        page.geometryChanged.emit()
        qapp.processEvents()

        assert _opacity(page) >= 0.99
        assert page.button.isVisible()
        assert page.geometry() == toolbar.content_host.rect()
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous)


def test_interrupted_crossfade_never_restores_partial_page_to_full_opacity() -> None:
    """Replacing an incoming page must fade from its rendered opacity without flash."""

    qapp = _app()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        first = toolbar.set_content("first", lambda parent: _MotionPage(90, parent))
        _wait_until(lambda: _opacity(first) >= 0.99)
        toolbar.set_content("second", lambda parent: _MotionPage(180, parent))
        _wait_until(lambda: 0.05 < _opacity(first) < 0.95)
        rendered_opacity = _opacity(first)

        toolbar.set_content("latest", lambda parent: _MotionPage(140, parent))
        qapp.processEvents()

        assert _opacity(first) <= rendered_opacity + 0.05
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous)


def test_dismissal_retains_full_shell_geometry_until_hidden_then_releases_page() -> (
    None
):
    """Dismissal must never expose an empty collapsed shell between page and hide."""

    qapp = _app()
    previous = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        page = toolbar.set_content("selection", lambda parent: _MotionPage(180, parent))
        _wait_until(lambda: toolbar.isVisible() and _opacity(page) >= 0.99)
        visible_size = toolbar.size()

        toolbar.clear_content()
        qapp.processEvents()
        toolbar.set_suppressed(False)

        assert toolbar.isVisible()
        assert toolbar.size() == visible_size
        assert toolbar.page is page
        assert toolbar.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        _wait_until(lambda: not toolbar.isVisible())
        assert toolbar.page is None
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous)


def test_shell_hide_after_page_crossfade_never_reenters_qt_painting() -> None:
    """Nested toolbar motion must not ask Qt to paint one device recursively."""

    qapp = _app()
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
        first = toolbar.set_content(
            "selection", lambda parent: _MotionPage(140, parent)
        )
        _wait_until(
            lambda: (
                toolbar.isVisible()
                and _opacity(first) >= 0.99
                and toolbar.graphicsEffect() is None
            )
        )
        assert toolbar.graphicsEffect() is None
        assert first.graphicsEffect() is None
        second = toolbar.set_content(
            "transform", lambda parent: _MotionPage(220, parent)
        )
        assert toolbar.graphicsEffect() is None
        _wait_until(
            lambda: (
                _opacity(second) >= 0.99
                and toolbar.content_host.graphicsEffect() is None
            )
        )
        assert second.graphicsEffect() is None

        toolbar.set_suppressed(True)
        assert toolbar.graphicsEffect() is not None
        assert second.graphicsEffect() is None
        _wait_until(lambda: not toolbar.isVisible())

        paint_failures = tuple(
            message
            for message in messages
            if "paint device can only be painted by one painter" in message
            or "Painter not active" in message
        )
        assert not paint_failures
    finally:
        toolbar.close()
        viewport.close()
        qInstallMessageHandler(previous_handler)
        qapp.setProperty("substitute.reduce_motion", previous_motion)


def test_hidden_page_retarget_keeps_entry_motion_on_shell_only() -> None:
    """A page replaced while suppressed must not nest under the entering effect."""

    qapp = _app()
    previous_motion = qapp.property("substitute.reduce_motion")
    qapp.setProperty("substitute.reduce_motion", False)
    viewport = QWidget()
    viewport.resize(640, 400)
    viewport.show()
    toolbar = CanvasContextualToolbar(viewport)
    try:
        first = toolbar.set_content(
            "selection", lambda parent: _MotionPage(140, parent)
        )
        _wait_until(lambda: toolbar.isVisible() and toolbar.graphicsEffect() is None)
        assert first.graphicsEffect() is None
        toolbar.set_suppressed(True)
        _wait_until(lambda: not toolbar.isVisible())

        second = toolbar.set_content(
            "transform",
            lambda parent: _MotionPage(220, parent),
        )
        assert toolbar.graphicsEffect() is None
        assert second.graphicsEffect() is None

        toolbar.set_suppressed(False)
        assert toolbar.graphicsEffect() is not None
        assert second.graphicsEffect() is None
        _wait_until(lambda: toolbar.isVisible() and toolbar.graphicsEffect() is None)
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous_motion)


def test_page_and_controls_remain_inside_shell_through_every_morph_sample() -> None:
    """Animated geometry must never displace page content beyond its shell."""

    qapp = _app()
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
        first = toolbar.set_content("first", lambda parent: _MotionPage(90, parent))
        _wait_until(lambda: toolbar.isVisible() and toolbar.graphicsEffect() is None)
        assert first.isVisible()
        toolbar.content_host.geometryChanged.connect(sample_geometry)
        toolbar.set_content("second", lambda parent: _MotionPage(220, parent))

        def wait_for_morph() -> None:
            """Sample every event-loop slice until content motion settles."""

            elapsed = 0
            while elapsed < 1000 and (
                toolbar.content_host.graphicsEffect() is not None
                or toolbar.content_host.size() != toolbar.content_host.sizeHint()
            ):
                sample_geometry()
                QTest.qWait(5)
                elapsed += 5
            sample_geometry()

        wait_for_morph()
        toolbar.set_content("third", lambda parent: _MotionPage(70, parent))
        wait_for_morph()
        toolbar.set_content("fourth", lambda parent: _MotionPage(260, parent))
        QTest.qWait(20)
        toolbar.set_content("latest", lambda parent: _MotionPage(110, parent))
        wait_for_morph()

        assert not violations
    finally:
        toolbar.close()
        viewport.close()
        qapp.setProperty("substitute.reduce_motion", previous_motion)
