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

"""Protect text entry while preserving visible video navigation ownership."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QWidget,
)

from substitute.presentation.canvas.output.video_viewport_interaction import (
    VideoViewportInteraction,
)
from tests.support.qt.lifecycle import ensure_qt_application, widget_root_scope
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)


@pytest.fixture
def video_scope() -> Iterator[tuple[QWidget, QWidget, VideoViewportInteraction]]:
    """Mount a visible video beside controls and restore process-local input state."""
    app = ensure_qt_application()
    pointer = QCursor.pos()
    with widget_root_scope() as owner:
        root = owner.own(QWidget())
        root.resize(640, 320)
        page = QWidget(root)
        page.setGeometry(320, 0, 320, 320)
        surface = QWidget(page)
        surface.resize(320, 240)
        interaction = VideoViewportInteraction(
            surface=surface,
            keyboard_scope=page,
            apply_viewport=lambda _state: None,
            show_fit=lambda: None,
            show_actual_size=lambda _position: None,
        )
        root.show()
        root.activateWindow()
        wait_for_qt_condition(
            lambda: app.activeWindow() is root,
            description="video keyboard owner window activation",
        )
        try:
            yield root, surface, interaction
        finally:
            QCursor.setPos(pointer)


@pytest.mark.parametrize("editor_type", [QLineEdit, QTextEdit, QPlainTextEdit])
@pytest.mark.parametrize("inside_page", [False, True])
def test_video_hover_preserves_focused_text_entry(
    video_scope: tuple[QWidget, QWidget, VideoViewportInteraction],
    editor_type: type[QLineEdit] | type[QTextEdit] | type[QPlainTextEdit],
    inside_page: bool,
) -> None:
    """Keep spaces with the focused native text owner despite video hover."""
    root, surface, interaction = video_scope
    parent = surface.parentWidget() if inside_page else root
    assert parent is not None
    editor = editor_type(parent)
    editor.setGeometry(0, 0, 300, 100)
    editor.show()
    editor.setFocus()
    wait_for_qt_condition(editor.hasFocus, description="native text editor focus")
    QCursor.setPos(surface.mapToGlobal(surface.rect().center()))
    QTest.keyClicks(editor, "x y ")
    text = editor.text() if isinstance(editor, QLineEdit) else editor.toPlainText()
    assert text == "x y "
    assert not interaction.pan_zoom_active


def test_hidden_video_cannot_claim_hovered_space(
    video_scope: tuple[QWidget, QWidget, VideoViewportInteraction],
) -> None:
    """Keep retained hidden video geometry from claiming another control's Space."""
    root, surface, interaction = video_scope
    button = QPushButton(root)
    button.show()
    button.setFocus()
    wait_for_qt_condition(button.hasFocus, description="outside video control focus")
    page = surface.parentWidget()
    assert page is not None
    page.hide()
    QCursor.setPos(surface.mapToGlobal(surface.rect().center()))
    QTest.keyPress(button, Qt.Key.Key_Space)
    try:
        assert not interaction.pan_zoom_active
    finally:
        QTest.keyRelease(button, Qt.Key.Key_Space)


def test_visible_video_hover_keeps_temporary_navigation(
    video_scope: tuple[QWidget, QWidget, VideoViewportInteraction],
) -> None:
    """Preserve hover navigation when a non-text control owns keyboard focus."""
    root, surface, interaction = video_scope
    button = QPushButton(root)
    button.show()
    button.setFocus()
    wait_for_qt_condition(button.hasFocus, description="outside video control focus")
    QCursor.setPos(surface.mapToGlobal(surface.rect().center()))
    QTest.keyPress(button, Qt.Key.Key_Space)
    assert interaction.pan_zoom_active
    QTest.keyRelease(button, Qt.Key.Key_Space)
    assert not interaction.pan_zoom_active


def test_text_focus_ends_held_video_navigation(
    video_scope: tuple[QWidget, QWidget, VideoViewportInteraction],
) -> None:
    """End the temporary tool when keyboard ownership transfers to text entry."""
    root, surface, interaction = video_scope
    surface.setFocus()
    wait_for_qt_condition(surface.hasFocus, description="video render surface focus")
    QTest.keyPress(surface, Qt.Key.Key_Space)
    assert interaction.pan_zoom_active
    editor = QLineEdit(root)
    editor.show()
    editor.setFocus()
    wait_for_queued_qt_turn()
    try:
        assert editor.hasFocus()
        assert not interaction.pan_zoom_active
    finally:
        QTest.keyRelease(editor, Qt.Key.Key_Space)


def test_background_video_cannot_claim_another_windows_space(
    video_scope: tuple[QWidget, QWidget, VideoViewportInteraction],
) -> None:
    """Leave keyboard input with the active window when video is behind it."""
    _root, surface, interaction = video_scope
    other_window = QWidget()
    button = QPushButton(other_window)
    other_window.show()
    other_window.activateWindow()
    button.setFocus()
    wait_for_qt_condition(
        button.hasFocus, description="foreground window control focus"
    )
    QCursor.setPos(surface.mapToGlobal(surface.rect().center()))
    QTest.keyPress(button, Qt.Key.Key_Space)
    try:
        assert not interaction.pan_zoom_active
    finally:
        QTest.keyRelease(button, Qt.Key.Key_Space)


def test_hiding_video_ends_held_navigation(
    video_scope: tuple[QWidget, QWidget, VideoViewportInteraction],
) -> None:
    """Retire the held tool when its actual render surface becomes hidden."""
    _root, surface, interaction = video_scope
    surface.setFocus()
    wait_for_qt_condition(surface.hasFocus, description="visible video keyboard focus")
    QTest.keyPress(surface, Qt.Key.Key_Space)
    assert interaction.pan_zoom_active
    surface.hide()
    assert not interaction.pan_zoom_active
    QTest.keyRelease(surface, Qt.Key.Key_Space)
