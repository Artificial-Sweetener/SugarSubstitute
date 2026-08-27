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

"""Test real-editor keyboard reorder commits."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.overlays import SegmentReorderOverlay
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
    create_prompt_editor,
)
from tests.support.prompt_editor.projection_engine_support import surface_for


def _reorder_preview_text(editor: PromptEditor) -> str:
    """Return the source text from the active reorder preview, if any."""

    preview_document = cast(
        PromptProjectionDocument | None,
        getattr(surface_for(editor), "_reorder_preview_projection").preview_document,
    )
    return "" if preview_document is None else preview_document.source_text


def _show_editor(
    widgets: list[QWidget],
    *,
    text: str,
    cursor_position: int,
    height: int = 220,
) -> PromptEditor:
    """Mount a focused editor at the supplied source cursor position."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, height)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(editor)
    editor.setPlainText(text)
    cursor = editor.textCursor()
    cursor.setPosition(cursor_position, QTextCursor.MoveMode.MoveAnchor)
    editor.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)
    return editor


def test_prompt_editor_real_widget_commits_alt_left_keyboard_reorder(
    widgets: list[QWidget],
) -> None:
    """Alt-left should commit one leftward chip move for the caret-owned chip."""

    app = ensure_qapp()
    editor = _show_editor(
        widgets,
        text="alpha, beta, gamma",
        cursor_position=8,
    )
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(editor, Qt.Key.Key_Left)
    process_events(app)

    assert _reorder_preview_text(editor) == "beta, alpha, gamma"
    overlay = cast(SegmentReorderOverlay, getattr(editor, "_segment_overlay"))
    latest_snapshot = overlay.commit_snapshot()
    assert latest_snapshot is not None
    assert latest_snapshot.ordered_chip_indices == (1, 0, 2)
    assert latest_snapshot.has_reordered is True
    assert editor.hasFocus() is True

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == "beta, alpha, gamma"
    assert editor.textCursor().selectionStart() == 1
    assert editor.textCursor().selectionEnd() == 1
    assert getattr(editor, "_segment_overlay") is None
    assert editor.hasFocus() is True


def test_prompt_editor_real_widget_commits_alt_right_keyboard_reorder(
    widgets: list[QWidget],
) -> None:
    """Alt-right should commit one rightward chip move for the caret-owned chip."""

    app = ensure_qapp()
    editor = _show_editor(
        widgets,
        text="alpha, beta, gamma",
        cursor_position=8,
    )
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(editor, Qt.Key.Key_Right)
    process_events(app)

    assert _reorder_preview_text(editor) == "alpha, gamma, beta"
    overlay = cast(SegmentReorderOverlay, getattr(editor, "_segment_overlay"))
    latest_snapshot = overlay.commit_snapshot()
    assert latest_snapshot is not None
    assert latest_snapshot.ordered_chip_indices == (0, 2, 1)
    assert latest_snapshot.has_reordered is True

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == "alpha, gamma, beta"
    assert getattr(editor, "_segment_overlay") is None


def test_prompt_editor_real_widget_commits_alt_up_keyboard_reorder(
    widgets: list[QWidget],
) -> None:
    """Alt-up should move the active chip into the previous visible reorder lane."""

    app = ensure_qapp()
    editor = _show_editor(
        widgets,
        text="alpha,\n\n\ngamma, beta",
        cursor_position=10,
        height=240,
    )
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(editor, Qt.Key.Key_Up)
    process_events(app)

    assert _reorder_preview_text(editor) == "alpha,\n\ngamma,\nbeta"
    overlay = cast(SegmentReorderOverlay, getattr(editor, "_segment_overlay"))
    latest_snapshot = overlay.commit_snapshot()
    assert latest_snapshot is not None
    assert latest_snapshot.ordered_chip_indices == (0, 1, 2)
    assert latest_snapshot.has_reordered is True

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == "alpha,\n\ngamma,\nbeta"
    assert getattr(editor, "_segment_overlay") is None


def test_prompt_editor_real_widget_clamps_alt_up_to_first_slot_on_top_lane(
    widgets: list[QWidget],
) -> None:
    """Alt-up on the top reorder lane should move the active chip to the row start."""

    app = ensure_qapp()
    editor = _show_editor(
        widgets,
        text="alpha, beta, gamma",
        cursor_position=8,
    )
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(editor, Qt.Key.Key_Up)
    process_events(app)

    assert _reorder_preview_text(editor) == "beta, alpha, gamma"

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == "beta, alpha, gamma"
    assert getattr(editor, "_segment_overlay") is None


def test_prompt_editor_real_widget_commits_alt_down_keyboard_reorder(
    widgets: list[QWidget],
) -> None:
    """Alt-down should move the active chip into the next visible reorder lane."""

    app = ensure_qapp()
    editor = _show_editor(
        widgets,
        text="alpha,\n\n\ngamma, beta",
        cursor_position=10,
        height=240,
    )
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(editor, Qt.Key.Key_Up)
    process_events(app)
    QTest.keyClick(editor, Qt.Key.Key_Down)
    process_events(app)

    assert _reorder_preview_text(editor) == "alpha,\n\n\nbeta, gamma"
    overlay = cast(SegmentReorderOverlay, getattr(editor, "_segment_overlay"))
    latest_snapshot = overlay.commit_snapshot()
    assert latest_snapshot is not None
    assert latest_snapshot.ordered_chip_indices == (0, 2, 1)
    assert latest_snapshot.has_reordered is True

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == "alpha,\n\n\nbeta, gamma"
    assert getattr(editor, "_segment_overlay") is None


def test_prompt_editor_real_widget_clamps_alt_down_to_last_slot_on_bottom_lane(
    widgets: list[QWidget],
) -> None:
    """Alt-down on the bottom reorder lane should move the active chip to the row end."""

    app = ensure_qapp()
    editor = _show_editor(
        widgets,
        text="alpha, beta, gamma",
        cursor_position=8,
    )
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(editor, Qt.Key.Key_Down)
    process_events(app)

    assert _reorder_preview_text(editor) == "alpha, gamma, beta"

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == "alpha, gamma, beta"
    assert getattr(editor, "_segment_overlay") is None
