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

"""Regression tests for prompt projection Unicode and input-method behavior."""

from __future__ import annotations

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QInputMethodEvent, QTextCharFormat, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.editing_session.edit_controller import (
    PromptEditController,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionUndoPayload,
)
import substitute.presentation.text_coordinates as text_coordinates_module
from substitute.presentation.text_coordinates import TextCoordinateMap
from tests.prompt_projection_surface_test_helpers import (
    new_projection_surface,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    surface_router,
)
from tests.prompt_projection_test_helpers import ensure_qapp

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _set_source(surface: Any, text: str) -> None:
    """Replace the complete source through the composed command boundary."""

    surface.set_exact_source_editing_enabled(True)
    surface_router(surface).replace_source_range(
        start=0,
        end=len(surface.toPlainText()),
        replacement_text=text,
        origin=PromptSourceEditOrigin.TYPED,
        command_name="test_set_source",
        record_undo=False,
    )


def test_prompt_preedit_is_transient_and_exposes_complete_qt_queries(
    widgets: list[QWidget],
) -> None:
    """Keep Japanese preedit out of source while answering the platform IME."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    _set_source(surface, "prefix 👩‍💻 suffix")
    surface.set_cursor_positions(cursor_position=7, anchor_position=7)
    text_format = QTextCharFormat()
    text_format.setFontUnderline(True)
    attributes = [
        QInputMethodEvent.Attribute(
            QInputMethodEvent.AttributeType.TextFormat,
            0,
            3,
            text_format,
        ),
        QInputMethodEvent.Attribute(
            QInputMethodEvent.AttributeType.Cursor,
            3,
            1,
            None,
        ),
    ]

    QApplication.sendEvent(surface, QInputMethodEvent("にほん", attributes))

    assert surface.toPlainText() == "prefix 👩‍💻 suffix"
    assert surface.inputMethodQuery(Qt.InputMethodQuery.ImEnabled) is True
    assert (
        surface.inputMethodQuery(Qt.InputMethodQuery.ImSurroundingText)
        == "prefix 👩‍💻 suffix"
    )
    assert surface.inputMethodQuery(Qt.InputMethodQuery.ImCursorPosition) == 7
    assert surface.inputMethodQuery(Qt.InputMethodQuery.ImCurrentSelection) == ""
    assert cast(
        QRectF,
        surface.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle),
    ).isValid()


def test_prompt_ime_commit_replaces_selection_once_and_round_trips_undo(
    widgets: list[QWidget],
) -> None:
    """Commit Chinese/Japanese text as one undo-safe source mutation."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    _set_source(surface, "replace me")
    surface.set_cursor_positions(cursor_position=10, anchor_position=0)
    QApplication.sendEvent(surface, QInputMethodEvent("nihon", []))
    commit = QInputMethodEvent()
    commit.setCommitString("中文 日本語 한국어 👩‍💻")

    QApplication.sendEvent(surface, commit)

    assert surface.toPlainText() == "中文 日本語 한국어 👩‍💻"
    edit_controller = cast(
        PromptEditController[PromptProjectionUndoPayload],
        cast(Any, surface)._phase21_test_edit_controller,
    )
    restore_result = edit_controller.undo()
    assert restore_result is not None
    surface.restore_clipboard_history_state(restore_result)
    assert surface.toPlainText() == "replace me"


def test_text_coordinate_map_keeps_surrogates_and_graphemes_atomic() -> None:
    """Map Qt offsets without exposing interior surrogate or grapheme boundaries."""

    coordinates = TextCoordinateMap("A👩‍🚀é日")

    assert coordinates.utf16_length == 9
    assert coordinates.python_to_utf16(2) == 3
    assert coordinates.utf16_to_python(2) == 1
    assert coordinates.utf16_to_python(2, prefer_after=True) == 2
    assert coordinates.utf16_to_python(10_000) == len(coordinates.text)
    assert coordinates.utf16_offsets_by_python_index() == (0, 1, 3, 4, 6, 7, 8, 9)
    assert coordinates.grapheme_boundaries() == (0, 1, 4, 6, 7)
    assert coordinates.next_grapheme_boundary(1) == 4
    assert coordinates.previous_grapheme_boundary(6) == 4


def test_text_coordinate_map_resolves_graphemes_with_linear_width_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve a boundary batch with one character-width pass."""

    text = "A👩‍🚀é日" * 256
    width_call_count = 0
    original_width = text_coordinates_module._utf16_code_units  # noqa: SLF001

    def count_width(character: str) -> int:
        """Count coordinate-width work without changing its result."""

        nonlocal width_call_count
        width_call_count += 1
        return original_width(character)

    monkeypatch.setattr(
        text_coordinates_module,
        "_utf16_code_units",
        count_width,
    )

    boundaries = TextCoordinateMap(text).grapheme_boundaries()

    assert boundaries[0] == 0
    assert boundaries[-1] == len(text)
    assert width_call_count == len(text)


def test_prompt_navigation_and_deletion_do_not_split_grapheme_clusters(
    widgets: list[QWidget],
) -> None:
    """Move and delete across emoji ZWJ and combining sequences atomically."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    _set_source(surface, "A👩‍🚀é日")
    surface.set_cursor_positions(cursor_position=7, anchor_position=7)

    surface.move_cursor_by_operation(
        QTextCursor.MoveOperation.Left,
        keep_anchor=False,
    )
    assert surface.cursor_position == 6
    surface.move_cursor_by_operation(
        QTextCursor.MoveOperation.Left,
        keep_anchor=False,
    )
    assert surface.cursor_position == 4

    QTest.keyClick(surface, Qt.Key.Key_Backspace)

    assert surface.toPlainText() == "Aé日"
    assert surface.cursor_position == 1
