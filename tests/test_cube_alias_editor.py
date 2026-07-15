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

"""Tests for the cube alias inline editor."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    ThemeColor,
    isDarkTheme,
)

from substitute.presentation.cubes.cube_alias_editor import CubeAliasEditor


def _app() -> QApplication:
    """Return a QApplication for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _editor(text: str = "SDXL/Text to Image") -> CubeAliasEditor:
    """Return a visible editor with stable test geometry."""

    _app()
    editor = CubeAliasEditor()
    editor.resize(220, 24)
    editor.begin(text)
    QApplication.processEvents()
    return editor


def test_editor_begin_selects_all_text() -> None:
    """Starting an edit should select the complete alias."""

    editor = _editor()

    assert editor.text() == "SDXL/Text to Image"
    assert editor.selectionRange() == (0, len("SDXL/Text to Image"))


def test_editor_return_commits_stripped_changed_text() -> None:
    """Return should accept changed stripped text and finish editing."""

    editor = _editor("Old")
    accepted: list[str] = []
    finished: list[bool] = []
    editor.accepted.connect(accepted.append)
    editor.editingFinished.connect(lambda: finished.append(True))
    editor.setText(" New ")

    QTest.keyClick(editor, Qt.Key.Key_Return)

    assert accepted == ["New"]
    assert finished == [True]
    assert editor.isHidden()


def test_editor_empty_commit_restores_without_accepting() -> None:
    """Empty committed aliases should finish without emitting accepted text."""

    editor = _editor("Old")
    accepted: list[str] = []
    editor.accepted.connect(accepted.append)
    editor.setText("   ")

    QTest.keyClick(editor, Qt.Key.Key_Return)

    assert accepted == []
    assert editor.isHidden()


def test_editor_escape_cancels_and_restores_original_text() -> None:
    """Escape should cancel the edit and restore original text."""

    editor = _editor("Old")
    cancelled: list[bool] = []
    editor.cancelled.connect(lambda: cancelled.append(True))
    editor.setText("New")

    QTest.keyClick(editor, Qt.Key.Key_Escape)

    assert editor.text() == "Old"
    assert cancelled == [True]
    assert editor.isHidden()


def test_editor_selection_color_matches_qfluent_line_edit_theme() -> None:
    """Selection fill should use the same theme token as QFluent line edits."""

    expected = (
        ThemeColor.PRIMARY.color() if isDarkTheme() else ThemeColor.LIGHT_1.color()
    )

    assert CubeAliasEditor._resolved_selection_color() == expected


def test_clicking_outside_editor_commits_current_text() -> None:
    """Mouse presses outside the alias editor should commit like line-edit focus loss."""

    app = _app()
    parent = QWidget()
    parent.resize(260, 80)
    editor = CubeAliasEditor(parent)
    editor.setGeometry(20, 20, 180, 24)
    accepted: list[str] = []
    editor.accepted.connect(accepted.append)
    parent.show()
    editor.begin("Old")
    editor.setText("New")
    app.processEvents()

    QTest.mouseClick(
        parent,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(4, 4),
    )
    app.processEvents()

    assert accepted == ["New"]
    assert editor.isHidden()
    assert editor.isEditing() is False

    parent.close()
    parent.deleteLater()


def test_backspace_at_body_start_removes_prefix_token() -> None:
    """Backspace at the body boundary should remove the full prefix token."""

    editor = _editor()
    editor.selectRange(len("SDXL/"), len("SDXL/"))

    QTest.keyClick(editor, Qt.Key.Key_Backspace)

    assert editor.text() == "Text to Image"
    assert editor.cursorIndex() == 0


def test_backspace_inside_prefix_removes_prefix_token() -> None:
    """Backspace inside the prefix should remove the full prefix token."""

    editor = _editor()
    editor.selectRange(2, 2)

    QTest.keyClick(editor, Qt.Key.Key_Backspace)

    assert editor.text() == "Text to Image"


def test_delete_at_prefix_start_removes_prefix_token() -> None:
    """Delete at prefix start should remove the full prefix token."""

    editor = _editor()
    editor.selectRange(0, 0)

    QTest.keyClick(editor, Qt.Key.Key_Delete)

    assert editor.text() == "Text to Image"
    assert editor.cursorIndex() == 0


def test_selection_intersecting_prefix_deletes_full_token() -> None:
    """Selections touching the prefix should expand to token boundaries."""

    editor = _editor()
    editor.selectRange(2, 7)

    QTest.keyClick(editor, Qt.Key.Key_Delete)

    assert editor.text() == "xt to Image"


def test_click_inside_prefix_snaps_cursor_to_token_edge() -> None:
    """Mouse hit testing should not place the caret inside the prefix token."""

    editor = _editor()

    QTest.mouseClick(
        editor,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(2, editor.height() // 2),
    )

    assert editor.cursorIndex() in {0, len("SDXL/")}


def test_double_click_inside_prefix_selects_full_token() -> None:
    """Double-clicking the small prefix should select it as one token."""

    editor = _editor()

    QTest.mouseDClick(
        editor,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(2, editor.height() // 2),
    )

    assert editor.selectionRange() == (0, len("SDXL/"))


def test_shift_arrow_selection_treats_prefix_as_one_token() -> None:
    """Shift+Arrow should select the full prefix token at its boundaries."""

    editor = _editor()
    prefix_end = len("SDXL/")

    editor.selectRange(prefix_end, prefix_end)
    QTest.keyClick(editor, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert editor.selectionRange() == (0, prefix_end)

    editor.selectRange(0, 0)
    QTest.keyClick(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert editor.selectionRange() == (0, prefix_end)


def test_ctrl_arrow_navigation_treats_prefix_as_one_token() -> None:
    """Ctrl+Arrow should jump over the prefix token rather than entering it."""

    editor = _editor()
    prefix_end = len("SDXL/")

    editor.selectRange(0, 0)
    QTest.keyClick(editor, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
    assert editor.cursorIndex() == prefix_end

    QTest.keyClick(editor, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)
    assert editor.cursorIndex() == 0


def test_drag_selection_touching_prefix_expands_to_token_boundaries() -> None:
    """Drag selections touching the prefix should report snapped token boundaries."""

    editor = _editor()

    QTest.mousePress(
        editor,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(2, editor.height() // 2),
    )
    move_event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(60, editor.height() / 2),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    editor.mouseMoveEvent(move_event)

    selection = editor.selectionRange()
    assert selection is not None
    assert selection[0] == 0
    assert selection[1] >= len("SDXL/")


def test_ctrl_a_selects_all_text() -> None:
    """Ctrl+A should select the full editable alias."""

    editor = _editor()
    editor.selectRange(0, 0)

    QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)

    assert editor.selectionRange() == (0, len("SDXL/Text to Image"))


def test_clipboard_copy_cut_and_paste_body_text() -> None:
    """Clipboard operations should work for normal body selections."""

    app = _app()
    editor = _editor("Text to Image")
    editor.selectRange(0, 4)

    QTest.keyClick(editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert app.clipboard().text() == "Text"

    QTest.keyClick(editor, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
    assert app.clipboard().text() == "Text"
    assert editor.text() == " to Image"

    editor.selectRange(len(editor.text()), len(editor.text()))
    QTest.keyClick(editor, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)

    assert editor.text() == " to ImageText"
