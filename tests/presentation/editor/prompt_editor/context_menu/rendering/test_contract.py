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

"""Verify rich-rendering and diagnostic context-menu row contracts."""

from __future__ import annotations

from typing import Any, cast

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget
from qfluentwidgets.components.widgets.menu import (  # type: ignore[import-untyped]
    RoundMenu,
)

from substitute.presentation.editor.prompt_editor.features import (
    PromptContextMenuAction,
)
from substitute.presentation.editor.prompt_editor.shell.context_menu_controller import (
    _PromptEditorTextEditMenu,
)
from tests.presentation.editor.prompt_editor.context_menu.menu_rows import (
    visible_menu_rows,
)
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    create_prompt_editor,
)


def test_context_menu_adds_checked_rich_rendering_action(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Expose rich rendering with a stateful icon-column action."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu = _PromptEditorTextEditMenu(editor, schedule_lora=lambda: None)
    menu.exec(editor.mapToGlobal(editor.rect().center()))

    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )
    assert action.isCheckable() is True
    assert action.isChecked() is True
    assert action.icon().isNull() is False
    assert cast(Any, action.property("item")).icon().isNull() is False
    assert menu.view.itemDelegate().__class__.__name__ == "ShortcutMenuItemDelegate"

    unchecked_menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        rich_prompt_rendering_enabled=False,
    )
    unchecked_menu.exec(editor.mapToGlobal(editor.rect().center()))
    unchecked_action = next(
        action
        for action in unchecked_menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )
    assert unchecked_action.isChecked() is False
    assert unchecked_action.icon().isNull() is False
    assert cast(Any, unchecked_action.property("item")).icon().isNull() is False


def test_context_menu_adds_disabled_diagnostic_explainer(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Place disabled diagnostic explainers before editing rows."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        diagnostic_actions=(
            PromptContextMenuAction(
                label="Wildcard not found",
                callback=None,
                enabled=False,
            ),
        ),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action for action in menu.menuActions() if action.text() == "Wildcard not found"
    )
    visual_rows = visible_menu_rows(menu)

    assert action.isEnabled() is False
    assert action.icon().isNull() is False
    assert cast(Any, action.property("item")).icon().isNull() is False
    assert visual_rows[0] == "Wildcard not found"
    assert visual_rows[1] == "<separator>"
    assert "Cancel" not in visual_rows
    assert "Select all" in visual_rows


def test_context_menu_aligns_enabled_diagnostic_actions(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Reserve the diagnostic icon column for enabled actions too."""

    editor = create_prompt_editor(prompt_widgets)
    triggered: list[str] = []
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)

    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        diagnostic_actions=(
            PromptContextMenuAction(
                label="teh",
                callback=lambda: triggered.append("teh"),
            ),
        ),
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(action for action in menu.menuActions() if action.text() == "teh")
    visual_rows = visible_menu_rows(menu)

    assert action.isEnabled() is True
    assert action.icon().isNull() is False
    assert cast(Any, action.property("item")).icon().isNull() is False
    assert visual_rows[0] == "teh"
    assert visual_rows[1] == "<separator>"
    assert "Cancel" not in visual_rows
    assert "Select all" in visual_rows

    action.trigger()

    assert triggered == ["teh"]


def test_context_menu_rich_rendering_action_toggles_editor(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Toggle rich rendering through the menu's authoritative editor callback."""

    editor = create_prompt_editor(prompt_widgets)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        rich_prompt_rendering_enabled=editor.richPromptRenderingEnabled(),
        toggle_rich_prompt_rendering=editor.setRichPromptRenderingEnabled,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )

    action.trigger()

    assert editor.richPromptRenderingEnabled() is False

    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        rich_prompt_rendering_enabled=editor.richPromptRenderingEnabled(),
        toggle_rich_prompt_rendering=editor.setRichPromptRenderingEnabled,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )
    action.trigger()

    assert editor.richPromptRenderingEnabled() is True


def test_context_menu_rich_rendering_action_preserves_selection(
    monkeypatch: pytest.MonkeyPatch,
    prompt_widgets: list[QWidget],
) -> None:
    """Preserve source selection when a menu action changes rendering mode."""

    editor = create_prompt_editor(prompt_widgets)
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(10, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    monkeypatch.setattr(RoundMenu, "exec", lambda *_args, **_kwargs: None)
    menu = _PromptEditorTextEditMenu(
        editor,
        schedule_lora=lambda: None,
        rich_prompt_rendering_enabled=editor.richPromptRenderingEnabled(),
        toggle_rich_prompt_rendering=editor.setRichPromptRenderingEnabled,
    )
    menu.exec(editor.mapToGlobal(editor.rect().center()))
    action = next(
        action
        for action in menu.menuActions()
        if action.text() == "Rich prompt rendering"
    )

    action.trigger()

    assert editor.textCursor().selectionStart() == 6
    assert editor.textCursor().selectionEnd() == 10
    assert editor.toPlainText() == "alpha beta gamma"
