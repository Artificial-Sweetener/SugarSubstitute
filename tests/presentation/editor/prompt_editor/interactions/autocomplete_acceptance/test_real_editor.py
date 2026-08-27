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

"""Verify real-editor autocomplete navigation and acceptance behavior."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
)
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
    widgets as _widgets,  # noqa: F401
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_assertions import (
    panel_rows,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_fixtures import (
    sample_suggestions,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
    create_prompt_editor,
    editor_autocomplete_preview_text,
    has_pending_autocomplete_refresh,
)


def _panel(box: QWidget) -> PromptAutocompletePanel:
    """Return the real editor's current autocomplete panel."""

    panel = getattr(box, "_autocomplete_panel")
    assert isinstance(panel, PromptAutocompletePanel)
    return panel


def test_prompt_editor_real_widget_keeps_typing_flow_and_updates_inline_preview(
    widgets: list[QWidget],
) -> None:
    """PromptEditor should keep focus while typing and update the ghost suffix live."""

    app = ensure_qapp()
    suggestions = sample_suggestions()
    gateway = StaticPromptAutocompleteGateway({"1g": suggestions, "1gi": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    panel = _panel(box)
    assert gateway.calls[-1] == ("1g", 10)
    assert box.toPlainText() == "1g"
    assert box.hasFocus() is True
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(box) == "irl"
    assert panel.parentWidget() is host
    assert panel.geometry().bottom() > box.geometry().bottom()

    QTest.keyClicks(box, "i")
    process_events(app)

    assert gateway.calls[-1] == ("1gi", 10)
    assert box.toPlainText() == "1gi"
    assert box.hasFocus() is True
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(box) == "rl"


def test_prompt_editor_real_widget_cycles_selection_without_mutating_text(
    widgets: list[QWidget],
) -> None:
    """Arrow navigation should change selection and preview without editing text."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1gi": sample_suggestions()})
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1gi")
    process_events(app)
    panel = _panel(box)

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)
    assert box.toPlainText() == "1gi"
    assert box.hasFocus() is True
    assert panel.current_index() == 1
    assert editor_autocomplete_preview_text(box) == "rls"

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)
    assert box.toPlainText() == "1gi"
    assert box.hasFocus() is True
    assert panel.current_index() == 0
    assert editor_autocomplete_preview_text(box) == "rl"


def test_prompt_editor_real_widget_suppresses_autocomplete_after_caret_navigation(
    widgets: list[QWidget],
) -> None:
    """Caret-only navigation should not reopen key-owning autocomplete."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway(
        {"blue": (PromptAutocompleteSuggestion("blue hair", 500),)}
    )
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText("blue")
    cursor = box.textCursor()
    cursor.setPosition(3, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert gateway.calls == []
    assert getattr(box, "_autocomplete_panel") is None
    assert has_pending_autocomplete_refresh(box) is False


def test_prompt_editor_real_widget_repeated_arrow_navigation_does_not_query_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Repeated caret moves should stay out of the autocomplete query path."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway(
        {"blue": (PromptAutocompleteSuggestion("blue hair", 500),)}
    )
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText("blue")
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    for _ in range(4):
        QTest.keyClick(box, Qt.Key.Key_Right)
        process_events(app)

    assert gateway.calls == []
    assert has_pending_autocomplete_refresh(box) is False


def test_prompt_editor_real_widget_vertical_boundaries_wrap_horizontal_arrows_escape(
    widgets: list[QWidget],
) -> None:
    """Vertical popup boundaries should wrap while horizontal arrows move the caret."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1gi": sample_suggestions()})
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText("1g\nnext")
    cursor = box.textCursor()
    cursor.setPosition(2, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    QTest.keyClicks(box, "i")
    process_events(app)
    panel = _panel(box)

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)
    assert panel.current_index() == 1
    cursor_before_boundary = box.textCursor().position()
    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)
    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0
    assert box.textCursor().position() == cursor_before_boundary

    box.setPlainText("above\n1g")
    cursor = box.textCursor()
    cursor.setPosition(len("above\n1g"), QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    QTest.keyClicks(box, "i")
    process_events(app)
    panel = _panel(box)
    cursor_before_boundary = box.textCursor().position()
    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)
    assert panel.is_panel_visible() is True
    assert panel.current_index() == 1
    assert box.textCursor().position() == cursor_before_boundary

    box.setPlainText("1g\nnext")
    cursor = box.textCursor()
    cursor.setPosition(2, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)
    QTest.keyClicks(box, "i")
    process_events(app)
    panel = _panel(box)
    cursor_before_horizontal = box.textCursor().position()
    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)
    assert panel.is_panel_visible() is False
    assert box.textCursor().position() > cursor_before_horizontal
    assert editor_autocomplete_preview_text(box) == ""


def test_prompt_editor_real_widget_preserves_acceptance_shortcuts(
    widgets: list[QWidget],
) -> None:
    """Tab and click should accept suggestions with existing semantics."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    widgets.extend([host, box])
    box.setFocus()
    process_events(app)
    QTest.keyClicks(box, "1g")
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Tab)
    process_events(app)
    assert box.toPlainText() == "1girl, "

    box.setPlainText("")
    box.setFocus()
    process_events(app)
    QTest.keyClicks(box, "1g")
    process_events(app)
    row = panel_rows(_panel(box))[1]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)
    assert box.toPlainText() == "1girls"
    assert box.hasFocus() is True


def test_prompt_editor_real_widget_enter_inserts_newline_without_accepting_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Enter should keep its text-editing behavior while autocomplete is visible."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)
    QTest.keyClicks(box, "1g")
    process_events(app)
    assert editor_autocomplete_preview_text(box) == "irl"

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)
    assert box.toPlainText() == "1g\n"
    assert editor_autocomplete_preview_text(box) == ""
