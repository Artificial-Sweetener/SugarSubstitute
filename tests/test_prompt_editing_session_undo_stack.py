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

"""Tests for prompt editing-session undo and grouping ownership."""

from __future__ import annotations

import pytest

from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptUndoSnapshot,
    PromptUndoStack,
)


def _snapshot(
    source_text: str,
    *,
    cursor_position: int | None = None,
    marker: str | None = None,
) -> PromptUndoSnapshot[str]:
    """Return a compact undo snapshot for pure stack behavior tests."""

    cursor = len(source_text) if cursor_position is None else cursor_position
    return PromptUndoSnapshot(
        source_text=source_text,
        cursor_state=PromptCursorState(
            cursor_position=cursor,
            anchor_position=cursor,
        ),
        comparison_payload=marker,
        restoration_payload=marker,
    )


def _stack() -> PromptUndoStack[str]:
    """Return a small prompt undo stack for focused tests."""

    return PromptUndoStack[str](max_undo_states=4, max_redo_states=4)


def test_undo_snapshot_rejects_negative_revision() -> None:
    """Undo snapshots should reject invalid source revision identities."""

    with pytest.raises(ValueError, match="Source revision"):
        PromptUndoSnapshot(
            source_text="alpha",
            cursor_state=PromptCursorState(),
            source_revision=-1,
        )


def test_record_snapshot_clears_redo_after_new_edit() -> None:
    """A new edit after undo should clear redo availability."""

    stack = _stack()
    alpha = _snapshot("alpha")
    beta = _snapshot("beta")
    gamma = _snapshot("gamma")

    stack.record_snapshot(alpha)
    undo_result = stack.undo(beta)
    assert undo_result is not None
    assert stack.can_redo()

    change = stack.record_snapshot(gamma)

    assert change is not None
    assert change.redo_changed
    assert stack.can_undo()
    assert not stack.can_redo()


def test_nested_edit_blocks_commit_one_changed_transaction() -> None:
    """Nested edit blocks should produce one undo state when the outer block ends."""

    stack = _stack()
    alpha = _snapshot("alpha")
    beta = _snapshot("alpha beta")

    stack.begin_edit_block(alpha)
    stack.begin_edit_block(alpha)
    assert stack.edit_block_depth == 2
    assert stack.end_edit_block(beta) is None

    change = stack.end_edit_block(beta)

    assert change is not None
    assert change.undo_changed
    assert stack.undo_depth == 1
    undo_result = stack.undo(beta)
    assert undo_result is not None
    assert undo_result.snapshot == alpha


def test_unchanged_edit_block_does_not_push_undo_state() -> None:
    """Edit blocks that leave undo-relevant state unchanged should not alter history."""

    stack = _stack()
    alpha = _snapshot("alpha")

    stack.begin_edit_block(alpha)
    change = stack.end_edit_block(alpha)

    assert change is None
    assert not stack.can_undo()
    assert not stack.can_redo()


def test_typing_group_coalesces_contiguous_word_text() -> None:
    """Contiguous word typing should commit as one undoable transaction."""

    stack = _stack()
    alpha = _snapshot("alpha")
    alpha_b = _snapshot("alpha b")
    alpha_be = _snapshot("alpha be")

    assert stack.can_group_typed_text("b", selection_empty=True)
    assert not stack.can_group_typed_text(" ", selection_empty=True)
    assert not stack.can_group_typed_text("bc", selection_empty=True)
    assert not stack.can_group_typed_text("b", selection_empty=False)

    stack.begin_or_extend_typing_group(
        "b",
        cursor_position=len("alpha "),
        snapshot=alpha,
    )
    stack.begin_or_extend_typing_group(
        "e",
        cursor_position=len("alpha b"),
        snapshot=alpha_b,
    )
    change = stack.finish_typing_group(alpha_be)

    assert change is not None
    assert stack.undo_depth == 1
    undo_result = stack.undo(alpha_be)
    assert undo_result is not None
    assert undo_result.snapshot == alpha


def test_idle_separated_typing_groups_stay_separate() -> None:
    """Typing groups separated by explicit idle commits should not merge."""

    stack = _stack()
    alpha = _snapshot("a")
    alpha_b = _snapshot("ab")
    alpha_bc = _snapshot("abc")

    stack.begin_or_extend_typing_group("b", cursor_position=1, snapshot=alpha)
    stack.finish_typing_group(alpha_b)
    stack.begin_or_extend_typing_group("c", cursor_position=2, snapshot=alpha_b)
    stack.finish_typing_group(alpha_bc)

    assert stack.undo_depth == 2
    undo_result = stack.undo(alpha_bc)
    assert undo_result is not None
    assert undo_result.snapshot == alpha_b


def test_delete_group_switch_commits_prior_key_group() -> None:
    """Switching delete keys should commit the prior delete transaction."""

    stack = _stack()
    alpha = _snapshot("alpha")
    alph = _snapshot("alph")
    alp = _snapshot("alp")

    stack.begin_delete_group(key=1, snapshot=alpha)
    stack.begin_delete_group(key=1, snapshot=alph)
    switch_change = stack.begin_delete_group(key=2, snapshot=alph)
    finish_change = stack.finish_delete_group(alp)

    assert switch_change is not None
    assert finish_change is not None
    assert stack.undo_depth == 2
    first_undo = stack.undo(alp)
    assert first_undo is not None
    assert first_undo.snapshot == alph
    second_undo = stack.undo(alph)
    assert second_undo is not None
    assert second_undo.snapshot == alpha


def test_clear_resets_history_and_open_groups() -> None:
    """Clearing history should reset stacks, edit blocks, and key group state."""

    stack = _stack()
    alpha = _snapshot("alpha")

    stack.record_snapshot(alpha)
    stack.begin_or_extend_typing_group("b", cursor_position=5, snapshot=alpha)

    change = stack.clear()

    assert change.undo_changed
    assert not stack.can_undo()
    assert not stack.can_redo()
    assert stack.edit_block_depth == 0
    assert not stack.typing_group_active
    assert not stack.delete_group_active


def test_discard_trailing_undo_state_removes_only_expected_latest_snapshot() -> None:
    """Trailing undo discard should match snapshots before mutating history."""

    stack = _stack()
    alpha = _snapshot("alpha")
    beta = _snapshot("beta")

    stack.record_snapshot(alpha)
    stack.record_snapshot(beta)

    assert stack.discard_trailing_undo_state(alpha) is None
    assert stack.undo_depth == 2

    change = stack.discard_trailing_undo_state(beta)

    assert change is not None
    assert stack.undo_depth == 1
