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

"""Qualify repeated emphasis shortcuts around literal parenthesized tags."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

from substitute.application.prompt_editor.document.service import PromptDocumentService
from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_repeated_ctrl_up_keeps_one_shell_around_literal_parentheses(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Adjust one selected tag without recursively wrapping its literal group."""

    tag = r"cassidy \(overwatch\)"
    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text=f"{tag}, portrait"
    )
    cursor = field.editor.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(len(tag), QTextCursor.MoveMode.KeepAnchor)
    field.editor.setTextCursor(cursor)

    for step, weight in enumerate(("1.05", "1.10", "1.15", "1.10", "1.05")):
        route = real_shell_scenario.input.press_key(
            field,
            Qt.Key.Key_Up if step < 3 else Qt.Key.Key_Down,
            modifiers=Qt.KeyboardModifier.ControlModifier,
        )
        assert route.source_after == f"({tag}:{weight}), portrait"
        assert (
            len(
                PromptDocumentService()
                .build_document_view(route.source_after)
                .emphasis_spans
            )
            == 1
        )
        snapshot = real_shell_scenario.snapshots.capture(
            field, label=f"literal-emphasis-shortcut-{step}"
        )
        assert r"\(" not in snapshot.projection_text
        assert r"\)" not in snapshot.projection_text
        assert not snapshot_invariant_violations(snapshot)


def test_ctrl_up_from_inside_escaped_group_adjusts_existing_shell(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Adjust the enclosing emphasis when the caret is inside literal parens."""

    tag = r"cassidy \(overwatch\)"
    source = f"({tag}:1.05), portrait"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=source)
    real_shell_scenario.input.set_source_cursor_position(
        field, source.index("overwatch") + 4
    )

    for step, weight in enumerate(("1.10", "1.15", "1.10")):
        route = real_shell_scenario.input.press_key(
            field,
            Qt.Key.Key_Up if step < 2 else Qt.Key.Key_Down,
            modifiers=Qt.KeyboardModifier.ControlModifier,
        )
        assert route.source_after == f"({tag}:{weight}), portrait"
        snapshot = real_shell_scenario.snapshots.capture(
            field, label=f"literal-emphasis-existing-{step}"
        )
        assert not snapshot_invariant_violations(snapshot)
