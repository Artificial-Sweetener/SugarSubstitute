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

"""Verify native prompt-editor editing through its context-menu contracts."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
    TextEditMenu,
)

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.field_actions import FieldActionContext
from substitute.presentation.editor.prompt_editor.shell.context_menu_controller import (
    _PromptEditorTextEditMenu,
)
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_prompt_editor,
    ensure_qapp,
    process_events,
)
from tests.support.prompt_editor.projection_engine_support import surface_for
from substitute.presentation.widgets.menu_model import MenuItem

pytestmark = pytest.mark.usefixtures("qt_clipboard_owner")


class _RecordingClipboardActions:
    """Record prompt clipboard action calls from context-menu rows."""

    def __init__(self) -> None:
        """Initialize empty action recording."""

        self.calls: list[str] = []

    def copy(self) -> None:
        """Record a copy request."""

        self.calls.append("copy")

    def cut(self) -> None:
        """Record a cut request."""

        self.calls.append("cut")

    def paste(self) -> None:
        """Record a paste request."""

        self.calls.append("paste")

    def select_all(self) -> None:
        """Record a select-all request."""

        self.calls.append("select_all")


def test_prompt_field_actions_exclude_generic_editing_commands(
    prompt_widgets: list[QWidget],
) -> None:
    """The node-menu contribution should contain prompt-domain actions only."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    cursor = editor.textCursor()
    cursor.setPosition(5)
    editor.setTextCursor(cursor)

    assert editor.field_actions_available() is True
    entries = editor.field_action_entries(FieldActionContext(QPoint(20, 30)))
    action_ids = {entry.action_id for entry in entries if isinstance(entry, MenuItem)}

    assert "prompt.rich_rendering.toggle" in action_ids
    assert action_ids.isdisjoint(
        {
            "prompt.undo",
            "prompt.redo",
            "prompt.cut",
            "prompt.copy",
            "prompt.paste",
            "prompt.select_all",
        }
    )
    insert_state = cast(Any, editor)._shell_context_menu.consume_context_insert_state()
    assert insert_state.insert_position == 5
    assert insert_state.should_replace_selection is False

    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    editor.field_action_entries(FieldActionContext(QPoint(20, 30)))
    selection_state = cast(
        Any, editor
    )._shell_context_menu.consume_context_insert_state()
    assert selection_state.insert_position is None
    assert selection_state.should_replace_selection is True


def test_prompt_editor_context_menu_select_all_selects_full_source(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Context-menu Select all should use the projection-backed source selection."""

    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha,\n\nbeta")
    process_events(ensure_qapp())
    cursor = editor.textCursor()
    cursor.setPosition(6)
    editor.setTextCursor(cursor)
    QApplication.clipboard().clear()

    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    select_all_action = next(
        action for action in menu.menuActions() if action.text() == "Select all"
    )
    select_all_action.trigger()

    assert editor.textCursor().selectedText() == "alpha,\n\nbeta"


def test_prompt_editor_context_menu_owns_clipboard_rows_without_qfluent_text_menu() -> (
    None
):
    """Prompt clipboard rows should not inherit QFluent's text-edit menu behavior."""

    assert issubclass(_PromptEditorTextEditMenu, RoundMenu)
    assert not issubclass(_PromptEditorTextEditMenu, TextEditMenu)


def test_prompt_editor_context_menu_clipboard_rows_use_shared_controller(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Context-menu clipboard rows should bypass legacy parent-method wiring."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    QApplication.clipboard().setText("omega")
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    def fail_parent_clipboard_method(self: PromptEditor) -> None:
        """Fail if a menu row still routes through the parent widget method."""

        _ = self
        raise AssertionError("context menu used parent clipboard method")

    monkeypatch.setattr(PromptEditor, "copy", fail_parent_clipboard_method)
    monkeypatch.setattr(PromptEditor, "cut", fail_parent_clipboard_method)
    monkeypatch.setattr(PromptEditor, "paste", fail_parent_clipboard_method)
    monkeypatch.setattr(PromptEditor, "selectAll", fail_parent_clipboard_method)

    menu = _PromptEditorTextEditMenu(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    actions = {action.text(): action for action in menu.menuActions()}

    actions["Copy"].trigger()
    assert QApplication.clipboard().text() == "alpha"

    QApplication.clipboard().setText("omega")
    actions["Paste"].trigger()
    process_events(app)
    assert editor.toPlainText() == "omega beta"

    editor.setPlainText("alpha beta")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    actions["Cut"].trigger()
    process_events(app)
    assert QApplication.clipboard().text() == "alpha"
    assert editor.toPlainText() == " beta"

    editor.setPlainText("alpha beta")
    actions["Select all"].trigger()
    assert editor.textCursor().selectedText() == "alpha beta"


@pytest.mark.parametrize(
    ("row_text", "expected_call"),
    (
        ("Copy", "copy"),
        ("Cut", "cut"),
        ("Paste", "paste"),
        ("Select all", "select_all"),
    ),
)
def test_prompt_editor_context_menu_clipboard_row_clicks_call_the_shared_actions(
    row_text: str,
    expected_call: str,
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Clicking a clipboard menu row should invoke the same owner as QAction.trigger."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    QApplication.clipboard().setText("omega")
    clipboard_actions = _RecordingClipboardActions()
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        clipboard_actions=clipboard_actions,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(action for action in menu.menuActions() if action.text() == row_text)
    item = next(
        menu.view.item(index)
        for index in range(menu.view.count())
        if menu.view.item(index).data(Qt.ItemDataRole.UserRole) is action
    )
    monkeypatch.setattr(menu, "_hideMenu", lambda *_args, **_kwargs: None)

    action.trigger()
    cast(Any, menu)._onItemClicked(item)

    assert clipboard_actions.calls == [expected_call, expected_call]


@pytest.mark.parametrize(
    ("row_text", "method_name", "shortcut_key"),
    (
        ("Copy", "copy", Qt.Key.Key_C),
        ("Cut", "cut", Qt.Key.Key_X),
        ("Paste", "paste", Qt.Key.Key_V),
        ("Select all", "select_all", Qt.Key.Key_A),
    ),
)
def test_prompt_editor_context_menu_clipboard_click_and_shortcut_share_controller(
    row_text: str,
    method_name: str,
    shortcut_key: Qt.Key,
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Context-menu and Ctrl clipboard entrypoints should call one controller method."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    editor.setFocus()
    QApplication.clipboard().setText("omega")
    calls: list[str] = []
    controller_type = type(cast(Any, editor)._clipboard_history_controller)

    def record_controller_call(self: object) -> None:
        """Record one clipboard controller action invocation."""

        _ = self
        calls.append(method_name)

    monkeypatch.setattr(controller_type, method_name, record_controller_call)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu = _PromptEditorTextEditMenu(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(action for action in menu.menuActions() if action.text() == row_text)
    item = next(
        menu.view.item(index)
        for index in range(menu.view.count())
        if menu.view.item(index).data(Qt.ItemDataRole.UserRole) is action
    )
    monkeypatch.setattr(menu, "_hideMenu", lambda *_args, **_kwargs: None)

    cast(Any, menu)._onItemClicked(item)
    QTest.keyClick(editor, shortcut_key, Qt.KeyboardModifier.ControlModifier)
    process_events(app)

    assert calls == [method_name, method_name]


def test_prompt_editor_host_facade_text_history_and_signal_contract(
    prompt_widgets: list[QWidget],
) -> None:
    """Phase 20.1 baselines public text/history methods and signal emissions."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    text_changed_count = 0
    cursor_changed_count = 0
    undo_available: list[bool] = []
    redo_available: list[bool] = []

    def record_text_changed() -> None:
        """Record one public textChanged emission."""

        nonlocal text_changed_count
        text_changed_count += 1

    def record_cursor_changed() -> None:
        """Record one public cursorPositionChanged emission."""

        nonlocal cursor_changed_count
        cursor_changed_count += 1

    editor.textChanged.connect(record_text_changed)
    editor.cursorPositionChanged.connect(record_cursor_changed)
    editor.undoAvailableChanged.connect(undo_available.append)
    editor.redoAvailableChanged.connect(redo_available.append)

    editor.setSourceText("alpha")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(len(editor.toPlainText()))
    editor.setTextCursor(cursor)
    QTest.keyClicks(editor, "x")
    surface_for(editor).edit_execution.finish_pending_key_edit_block(reason="phase20_1")
    process_events(app)

    assert editor.toPlainText() == "alphax"
    assert editor.canUndo() is True
    assert text_changed_count > 0
    assert cursor_changed_count > 0
    assert True in undo_available

    editor.undo()
    process_events(app)
    assert editor.toPlainText() == "alpha"
    assert editor.canRedo() is True
    assert True in redo_available

    editor.redo()
    process_events(app)
    assert editor.toPlainText() == "alphax"


def test_prompt_editor_host_facade_read_only_blocks_edits_but_allows_copy(
    prompt_widgets: list[QWidget],
) -> None:
    """Phase 20.1 baselines read-only source editing and selection behavior."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha beta")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    QApplication.clipboard().clear()

    editor.setReadOnly(True)
    QTest.keyClicks(editor, "x")
    editor.copy()
    process_events(app)

    assert editor.toPlainText() == "alpha beta"
    assert QApplication.clipboard().text() == "alpha"


def test_prompt_editor_host_facade_context_insert_preserves_focus_target(
    prompt_widgets: list[QWidget],
) -> None:
    """Phase 20.1 baselines menu insertion focus restoration behavior."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("alpha")
    editor.setFocus()
    process_events(app)
    cast(Any, editor)._set_context_menu_insert_state_for_tests(insert_position=5)

    cast(Any, editor)._context_insertion.insert_context_menu_text(
        ", beta",
        command_name="lora_insert_trigger_words",
    )
    process_events(app)

    assert editor.toPlainText() == "alpha, beta"
    assert editor.hasFocus()


def test_prompt_editor_context_menu_undo_redo_follow_custom_stack(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Undo and redo menu rows should reflect the custom prompt history."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu_type = _PromptEditorTextEditMenu

    clean_menu = menu_type(editor, schedule_lora=lambda: None)
    clean_menu.exec(editor.mapToGlobal(editor.rect().center()))
    clean_actions = [action.text() for action in clean_menu.menuActions()]

    assert "Undo" not in clean_actions
    assert "Redo" not in clean_actions
    assert "Cancel" not in clean_actions

    QTest.keyClicks(editor, "x")
    surface_for(editor).edit_execution.finish_pending_key_edit_block(reason="test_menu")
    undo_menu = menu_type(editor, schedule_lora=lambda: None)
    undo_menu.exec(editor.mapToGlobal(editor.rect().center()))
    undo_actions = [action.text() for action in undo_menu.menuActions()]

    assert "Undo" in undo_actions
    assert "Redo" not in undo_actions

    editor.undo()
    redo_menu = menu_type(editor, schedule_lora=lambda: None)
    redo_menu.exec(editor.mapToGlobal(editor.rect().center()))
    redo_actions = [action.text() for action in redo_menu.menuActions()]

    assert "Undo" not in redo_actions
    assert "Redo" in redo_actions


def test_prompt_editor_context_menu_copy_restores_exclusive_selection_end(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """QFluent menu actions should restore prompt selections without a +1 drift."""

    app = ensure_qapp()
    editor = create_prompt_editor(prompt_widgets)
    editor.setPlainText("see-through dress, sparkling")
    process_events(app)
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len("see-through dres"), QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu_type = _PromptEditorTextEditMenu
    menu = menu_type(
        editor,
        schedule_lora=lambda: None,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    copy_action = next(
        action for action in menu.menuActions() if action.text() == "Copy"
    )
    copy_item = next(
        menu.view.item(index)
        for index in range(menu.view.count())
        if menu.view.item(index).data(Qt.ItemDataRole.UserRole) is copy_action
    )
    monkeypatch.setattr(menu, "_hideMenu", lambda *_args, **_kwargs: None)

    cast(Any, menu)._onItemClicked(copy_item)

    assert QApplication.clipboard().text() == "see-through dres"
    assert editor.textCursor().selectionStart() == 0
    assert editor.textCursor().selectionEnd() == len("see-through dres")
