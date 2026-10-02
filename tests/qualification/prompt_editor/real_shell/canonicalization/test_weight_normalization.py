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

"""Verify real-shell prompt-weight normalization and history behavior."""

from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy

from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisAction,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands.weight_commands import (
    PromptWeightActionRequest,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.support.prompt_editor.projection_engine_support import surface_for

from tests.support.prompt_editor.real_shell.invariants.snapshot import (
    snapshot_invariant_violations,
)
from tests.support.prompt_editor.real_shell.invariants.transitions import (
    transition_violations,
)
from tests.support.prompt_editor.real_shell.scenario import (
    PromptEditorRealShellScenario,
)


def test_real_shell_paste_canonicalizes_implicit_parenthesis_weights(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Canonicalize pasted implicit emphasis through the production route."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-parenthesis-paste",
    )
    real_shell_scenario.input.paste_text(
        field,
        "(blue laces), ((deep focus)), (wide shot:6)",
    )
    after = real_shell_scenario.snapshots.capture(
        field, label="after-parenthesis-paste"
    )

    assert after.source_text == (
        "(blue laces:1.10), (deep focus:1.21), (wide shot:6.00)"
    )
    assert not transition_violations(
        action_name="paste",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )


def test_real_shell_typing_nested_parentheses_canonicalizes_once_closed(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Canonicalize nested authored emphasis only after it closes."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    before = real_shell_scenario.snapshots.capture(
        field,
        label="before-nested-parenthesis-typing",
    )
    real_shell_scenario.input.type_text(field, "((test))")
    after = real_shell_scenario.snapshots.capture(
        field,
        label="after-nested-parenthesis-typing",
    )

    assert after.source_text == "(test:1.21)"
    assert not transition_violations(
        action_name="typing",
        before=before,
        after=after,
        snapshot_violations=snapshot_invariant_violations,
    )


def test_real_shell_wrapping_generated_emphasis_re_evaluates_nesting(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Re-evaluate generated emphasis when it gains an outer parenthesis."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "(test)")
    generated = real_shell_scenario.snapshots.capture(
        field,
        label="generated-single-emphasis",
    )
    assert generated.source_text == "(test:1.10)"

    real_shell_scenario.input.set_source_cursor_position(field, 0)
    real_shell_scenario.input.type_text(field, "(")
    real_shell_scenario.input.set_source_cursor_position(
        field, len(field.editor.toPlainText())
    )
    real_shell_scenario.input.type_text(field, ")")
    wrapped = real_shell_scenario.snapshots.capture(
        field,
        label="wrapped-generated-emphasis",
    )

    assert wrapped.source_text == "(test:1.21)"
    assert not snapshot_invariant_violations(wrapped)


def test_real_shell_generated_emphasis_re_evaluates_after_undo_redo(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Restore generated-weight provenance through real editor history."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.type_text(field, "(test)")
    generated = real_shell_scenario.snapshots.capture(
        field,
        label="generated-before-history",
    )
    assert generated.source_text == "(test:1.10)"

    real_shell_scenario.input.undo(field)
    real_shell_scenario.input.redo(field)
    restored = real_shell_scenario.snapshots.capture(
        field,
        label="generated-after-history",
    )
    assert restored.source_text == generated.source_text

    real_shell_scenario.input.set_source_cursor_position(field, 0)
    real_shell_scenario.input.type_text(field, "(")
    real_shell_scenario.input.set_source_cursor_position(
        field, len(field.editor.toPlainText())
    )
    real_shell_scenario.input.type_text(field, ")")
    wrapped = real_shell_scenario.snapshots.capture(
        field,
        label="wrapped-generated-after-history",
    )

    assert wrapped.source_text == "(test:1.21)"
    assert not snapshot_invariant_violations(wrapped)


def test_real_shell_parenthesis_conversion_round_trips_through_undo_redo(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Restore normalized source, mappings, and projection through history."""

    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text="")
    real_shell_scenario.input.paste_text(field, "((blue laces))")
    canonical = real_shell_scenario.snapshots.capture(
        field,
        label="canonical-parentheses",
    )
    real_shell_scenario.input.undo(field)
    undone = real_shell_scenario.snapshots.capture(field, label="undone-parentheses")
    real_shell_scenario.input.redo(field)
    redone = real_shell_scenario.snapshots.capture(field, label="redone-parentheses")

    assert canonical.source_text == "(blue laces:1.21)"
    assert undone.source_text == ""
    assert redone.source_text == canonical.source_text
    assert not snapshot_invariant_violations(redone)


def test_real_shell_manual_unescape_persists_until_segment_replacement(
    real_shell_scenario: PromptEditorRealShellScenario,
) -> None:
    """Preserve manual escaping until the edited segment is reconstructed."""

    field = real_shell_scenario.workflows.add_prompt_workflow(
        initial_text=r"\(blue laces\)"
    )
    real_shell_scenario.input.set_rich_rendering(field, enabled=False)
    real_shell_scenario.input.set_source_cursor_position(field, 0)
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Delete)
    closing_slash = field.editor.toPlainText().index(r"\)")
    real_shell_scenario.input.set_source_cursor_position(field, closing_slash)
    real_shell_scenario.input.press_key(field, Qt.Key.Key_Delete)
    real_shell_scenario.input.set_source_cursor_position(
        field,
        len(field.editor.toPlainText()) - 1,
    )
    real_shell_scenario.input.type_text(field, "!")
    real_shell_scenario.input.set_rich_rendering(field, enabled=True)
    overridden = real_shell_scenario.snapshots.capture(field, label="manual-unescape")

    assert overridden.source_text == "(blue laces!)"
    assert not snapshot_invariant_violations(overridden)

    real_shell_scenario.input.replace_text_with_keys(field, "(fresh)")
    replaced = real_shell_scenario.snapshots.capture(field, label="replaced-segment")

    assert replaced.source_text == "(fresh:1.10)"
    assert not snapshot_invariant_violations(replaced)


@pytest.mark.parametrize("prefix", ["", "😀, "])
def test_real_shell_weight_normalization_publishes_one_coherent_history_edit(
    real_shell_scenario: PromptEditorRealShellScenario,
    prefix: str,
) -> None:
    """Keep normalized weight edits coherent through Qt, field wiring, and history."""

    original = prefix + "(cat:1.05), (dog)"
    expected = prefix + "(cat:1.10), (dog:1.10)"
    field = real_shell_scenario.workflows.add_prompt_workflow(initial_text=original)
    editor = field.editor
    surface = surface_for(editor)
    cursor_position = len(prefix) + 2
    real_shell_scenario.input.set_source_cursor_position(field, cursor_position)
    before = real_shell_scenario.snapshots.capture(field, label="before-weight-step")
    changed = QSignalSpy(editor.textChanged)
    moved = QSignalSpy(editor.cursorPositionChanged)

    result = editor.execute_weight_action(
        PromptWeightActionRequest(
            action=PromptAdjustEmphasisAction(
                outer_start=len(prefix),
                outer_end=len(prefix) + len("(cat:1.05)"),
                delta=Decimal("0.05"),
            ),
            source_identity=editor.prompt_command_source_identity(),
            cursor_policy="preserve_cursor",
        ),
        mutation_service=PromptMutationService(),
        syntax_service=PromptSyntaxService(EmptyPromptWildcardCatalogGateway()),
        syntax_profile=prompt_syntax_profile("emphasis"),
    )

    assert result.status == "applied"
    assert result.edit_commit is not None
    assert result.edit_commit.next_snapshot.source_text == expected
    assert editor.toPlainText() == surface.document().toPlainText() == expected
    assert surface._editing_session.source_text == expected  # noqa: SLF001
    assert surface.editor_state.source.source_text == expected
    assert surface.editor_state.edit_semantic.document.source_text == expected
    assert surface.projection_document().source_text == expected
    assert surface.cursor_position == editor.textCursor().position() == cursor_position
    assert editor.textCursor().selectionStart() == cursor_position
    assert editor.textCursor().selectionEnd() == cursor_position
    assert surface._editing_session.anchor_position == cursor_position  # noqa: SLF001
    assert changed.count() == 1
    assert moved.count() == 1
    after = real_shell_scenario.snapshots.capture(field, label="normalized-weight-step")
    assert after.undo_depth == before.undo_depth + 1
    assert after.undo_edit_block_depth == 0
    assert after.editing_session_source_revision == after.source_revision
    assert after.semantic_is_current
    assert not snapshot_invariant_violations(after)
    assert field.workflow.cube_state.dirty
    nodes = field.workflow.cube_state.buffer["nodes"]
    assert isinstance(nodes, dict)
    node = nodes[field.node_name]
    assert isinstance(node, dict)
    inputs = node["inputs"]
    assert isinstance(inputs, dict)
    assert inputs[field.field_key] == expected

    real_shell_scenario.input.undo(field)
    undone = real_shell_scenario.snapshots.capture(field, label="undone-weight-step")
    assert undone.source_text == original
    assert surface.document().toPlainText() == original
    assert surface._editing_session.source_text == original  # noqa: SLF001
    assert undone.cursor_position == before.cursor_position
    assert undone.selection_range == before.selection_range
    assert undone.undo_depth == before.undo_depth
    assert undone.redo_depth == 1
    assert not snapshot_invariant_violations(undone)
    assert changed.count() == 2

    real_shell_scenario.input.redo(field)
    redone = real_shell_scenario.snapshots.capture(field, label="redone-weight-step")
    assert redone.source_text == expected
    assert surface.document().toPlainText() == expected
    assert surface._editing_session.source_text == expected  # noqa: SLF001
    assert redone.cursor_position == after.cursor_position
    assert redone.selection_range == after.selection_range
    assert redone.undo_depth == after.undo_depth
    assert redone.redo_depth == 0
    assert not snapshot_invariant_violations(redone)
    assert changed.count() == 3
