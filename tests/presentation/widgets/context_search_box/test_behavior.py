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

"""Verify context-search behavior through the real Qt widget surface."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from substitute.presentation.widgets.search_box import ContextSearchBox
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


def test_completed_context_command_selects_context_and_publishes_query() -> None:
    """A complete command should atomically become selected context and query."""

    ensure_qt_application()
    widget = ContextSearchBox()
    changes: list[tuple[str, str]] = []
    widget.contextSearchChanged.connect(
        lambda context, query: changes.append((context, query))
    )

    widget.setQuery("@field   guidance")

    assert widget.context() == "Field"
    assert widget.searchText() == "guidance"
    assert changes[-1] == ("Field", "guidance")
    destroy_qt_object(widget)


def test_partial_context_command_is_not_published_as_search_text() -> None:
    """An incomplete command should remain editable without changing search state."""

    ensure_qt_application()
    widget = ContextSearchBox()
    changes: list[tuple[str, str]] = []
    widget.contextSearchChanged.connect(
        lambda context, query: changes.append((context, query))
    )

    widget.setQuery("@fi")

    assert widget.searchText() == "@fi"
    assert changes == []
    destroy_qt_object(widget)


def test_context_selector_overlays_left_aligned_search_surface() -> None:
    """The real child geometry should preserve the compact overlay contract."""

    ensure_qt_application()
    widget = ContextSearchBox()

    assert widget.width() == widget.searchLineEdit.width()
    assert widget.comboBox.pos().isNull()
    assert widget.searchLineEdit.pos().isNull()
    margins = widget.searchLineEdit.textMargins()
    assert (
        margins.left(),
        margins.top(),
        margins.right(),
        margins.bottom(),
    ) == (widget.comboBox.width() - 4, 0, 0, 0)
    assert widget.searchLineEdit.alignment() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    destroy_qt_object(widget)


def test_shift_enter_requests_backward_text_match_navigation() -> None:
    """Shift+Enter on the real editor should request only backward navigation."""

    ensure_qt_application()
    widget = ContextSearchBox()
    forward_calls: list[str] = []
    backward_calls: list[str] = []
    widget.cycleSearchMatchRequested.connect(lambda: forward_calls.append("forward"))
    widget.cycleSearchMatchRequestedBackward.connect(
        lambda: backward_calls.append("backward")
    )
    widget.searchLineEdit.setFocus()

    QTest.keyClick(
        widget.searchLineEdit,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier,
    )

    assert forward_calls == []
    assert backward_calls == ["backward"]
    destroy_qt_object(widget)
