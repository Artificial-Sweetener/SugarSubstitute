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

"""Tests for prompt editing-session source edit transactions."""

from __future__ import annotations

import pytest

from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.editing_session import (
    source_edit_commands,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptSourceBuffer,
    PromptSourceEditSession,
    PromptSourceTextEdit,
    PromptUndoSnapshot,
    PromptUndoStack,
    source_text_edit_between,
)


def _undo_snapshot(source_text: str) -> PromptUndoSnapshot[str]:
    """Return one passive undo snapshot for source edit tests."""

    cursor_position = len(source_text)
    return PromptUndoSnapshot(
        source_text=source_text,
        cursor_state=PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=cursor_position,
        ),
        restoration_payload=source_text,
    )


def _session(source_text: str = "") -> PromptSourceEditSession[str]:
    """Return a source edit session with a bounded undo owner."""

    return PromptSourceEditSession(
        source_buffer=PromptSourceBuffer(source_text=source_text),
        undo_stack=PromptUndoStack[str](max_undo_states=8, max_redo_states=8),
    )


def test_full_storage_replacement_normalizes_and_maps_cursor() -> None:
    """Full storage replacement should normalize source and cursor positions."""

    session = _session()

    result = session.replace_full_source(
        "painting (medium)",
        cursor_position=len("painting (medium)"),
        anchor_position=len("painting (medium)"),
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        record_undo=True,
        clear_history=False,
        undo_snapshot=_undo_snapshot(""),
    )

    assert result.previous_snapshot.source_text == ""
    assert result.next_snapshot.source_text == "painting (medium:1.10)"
    assert result.next_snapshot.source_revision == 1
    assert result.cursor_state.cursor_position == len("painting (medium:1.10)")
    assert result.source_edit == PromptSourceTextEdit(
        start=0,
        end=0,
        replacement_text="painting (medium:1.10)",
    )
    assert result.undo_availability_change is not None
    assert result.undo_availability_change.undo_changed


def test_exact_full_replacement_preserves_raw_source() -> None:
    """Exact full replacement should bypass storage normalization."""

    session = _session()

    result = session.replace_full_source(
        "painting (medium)",
        cursor_position=len("painting (medium)"),
        anchor_position=len("painting (medium)"),
        normalizer=PromptSourceNormalizationService(),
        exact_source=True,
        record_undo=True,
        clear_history=False,
        undo_snapshot=_undo_snapshot(""),
    )

    assert result.next_snapshot.source_text == "painting (medium)"
    assert result.cursor_state.cursor_position == len("painting (medium)")


def test_plain_edit_without_generated_emphasis_skips_document_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avoid parsing source when no generated emphasis provenance can move."""

    session = _session("alpha, (decorated:1.20), omega")

    def reject_parse(_text: str) -> object:
        """Fail if the generated-emphasis remapper requests a document parse."""

        raise AssertionError("plain edit unexpectedly parsed the prompt document")

    monkeypatch.setattr(source_edit_commands, "parse_prompt_document", reject_parse)

    result = session.replace_source_range(
        start=len("alpha"),
        end=len("alpha"),
        replacement_text="x",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )

    assert result.next_snapshot.source_text == "alphax, (decorated:1.20), omega"
    assert result.next_snapshot.generated_emphases == ()


def test_baseline_replacement_clears_prior_history() -> None:
    """Baseline replacement should clear undo history before adopting source."""

    undo_stack = PromptUndoStack[str](max_undo_states=8, max_redo_states=8)
    session = PromptSourceEditSession(
        source_buffer=PromptSourceBuffer(source_text="alpha"),
        undo_stack=undo_stack,
    )
    session.replace_source_range(
        start=len("alpha"),
        end=len("alpha"),
        replacement_text=" beta",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot("alpha"),
    )
    assert undo_stack.can_undo()

    result = session.replace_full_source(
        "recipe prompt",
        cursor_position=len("recipe prompt"),
        anchor_position=len("recipe prompt"),
        normalizer=PromptSourceNormalizationService(),
        exact_source=True,
        record_undo=False,
        clear_history=True,
        undo_snapshot=_undo_snapshot("alpha beta"),
    )

    assert result.next_snapshot.source_text == "recipe prompt"
    assert result.undo_availability_change is not None
    assert result.undo_availability_change.undo_changed
    assert not undo_stack.can_undo()


def test_typed_close_parenthesis_canonicalizes_implicit_emphasis() -> None:
    """Typed range edits should stabilize completed implicit emphasis."""

    session = _session("painting (medium")

    result = session.replace_source_range(
        start=len("painting (medium"),
        end=len("painting (medium"),
        replacement_text=")",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot("painting (medium"),
    )

    assert result.next_snapshot.source_text == "painting (medium:1.10)"
    assert result.cursor_state.cursor_position == len("painting (medium:1.10)")


def test_typed_selection_replacement_does_not_close_distant_parenthesis() -> None:
    """Replacing a selection must insert exact text without normalizing prior syntax."""

    source_text = "open (, alpha, {lighting/day}, omega"
    selection_start = source_text.index(",", source_text.index("{"))
    session = _session(source_text)

    result = session.replace_source_range(
        start=selection_start,
        end=selection_start + 2,
        replacement_text=")",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(source_text),
    )

    assert result.next_snapshot.source_text == ("open (, alpha, {lighting/day})omega")
    assert result.cursor_state.cursor_position == selection_start + 1


def test_typed_nested_parentheses_wait_for_outer_close_before_canonicalizing() -> None:
    """Keep authored nesting intact until its outer shell reveals the full weight."""

    session = _session("((test")
    normalizer = PromptSourceNormalizationService()

    inner_close = session.replace_source_range(
        start=len("((test"),
        end=len("((test"),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot("((test"),
    )
    outer_close = session.replace_source_range(
        start=len(inner_close.next_snapshot.source_text),
        end=len(inner_close.next_snapshot.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(inner_close.next_snapshot.source_text),
    )

    assert inner_close.next_snapshot.source_text == "((test)"
    assert outer_close.next_snapshot.source_text == "(test:1.21)"


def test_wrapping_generated_emphasis_re_evaluates_authored_nesting() -> None:
    """Recompute nesting added around an editor-generated explicit weight."""

    session = _session("(test")
    normalizer = PromptSourceNormalizationService()
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    assert session.source_text == "(test:1.10)"
    assert session.snapshot().generated_emphases

    session.replace_source_range(
        start=0,
        end=0,
        replacement_text="(",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )

    assert session.source_text == "(test:1.21)"
    assert session.snapshot().generated_emphases[0].nesting_depth == 2


def test_wrapping_user_authored_explicit_weight_preserves_inner_weight() -> None:
    """Keep an authored numeric weight distinct from editor-generated provenance."""

    session = _session("(test:1.10)")
    normalizer = PromptSourceNormalizationService()
    session.replace_source_range(
        start=0,
        end=0,
        replacement_text="(",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )

    assert session.source_text == "((test:1.10):1.10)"
    assert session.snapshot().generated_emphases[0].nesting_depth == 1


def test_editing_generated_emphasis_content_retains_re_evaluation() -> None:
    """Keep generated ownership when the user edits only emphasis content."""

    session = _session("(test")
    normalizer = PromptSourceNormalizationService()
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    content_end = session.source_text.index(":")
    session.replace_source_range(
        start=content_end,
        end=content_end,
        replacement_text="s",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    session.replace_source_range(
        start=0,
        end=0,
        replacement_text="(",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )

    assert session.source_text == "(tests:1.21)"


def test_editing_generated_weight_releases_generated_ownership() -> None:
    """Treat a direct edit to a generated numeric weight as user authorship."""

    session = _session("(test")
    normalizer = PromptSourceNormalizationService()
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    weight_start = session.source_text.index("1.10")
    session.replace_source_range(
        start=weight_start,
        end=weight_start + len("1.10"),
        replacement_text="2.00",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    assert session.snapshot().generated_emphases == ()
    session.replace_source_range(
        start=0,
        end=0,
        replacement_text="(",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )
    session.replace_source_range(
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session.source_text),
    )

    assert session.source_text == "((test:2.00):1.10)"


def test_paste_range_normalizes_only_pasted_text() -> None:
    """Paste normalization should preserve existing raw source around the paste."""

    prefix = "painting (medium), "
    session = _session(prefix)

    result = session.replace_source_range(
        start=len(prefix),
        end=len(prefix),
        replacement_text="blue (butterfly)",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.PASTE,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(prefix),
    )

    assert result.next_snapshot.source_text == (
        "painting (medium), blue (butterfly:1.10)"
    )


def test_same_text_range_edit_updates_cursor_without_revision_bump() -> None:
    """A no-op source edit should not bump revision or record undo history."""

    undo_stack = PromptUndoStack[str](max_undo_states=8, max_redo_states=8)
    session = PromptSourceEditSession(
        source_buffer=PromptSourceBuffer(source_text="abc", source_revision=4),
        undo_stack=undo_stack,
    )

    result = session.replace_source_range(
        start=1,
        end=2,
        replacement_text="b",
        normalizer=PromptSourceNormalizationService(),
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=True,
        record_undo=True,
        undo_snapshot=_undo_snapshot("abc"),
    )

    assert result.source_changed is False
    assert result.next_snapshot.source_revision == 4
    assert result.cursor_state.cursor_position == 2
    assert not undo_stack.can_undo()


def test_invalid_range_raises_without_mutating_source() -> None:
    """Source ranges outside the current text should fail closed."""

    session = _session("abc")

    with pytest.raises(ValueError, match="Source edit range"):
        session.replace_source_range(
            start=3,
            end=2,
            replacement_text="x",
            normalizer=PromptSourceNormalizationService(),
            origin=PromptSourceEditOrigin.TYPED,
            exact_source=True,
            record_undo=True,
            undo_snapshot=_undo_snapshot("abc"),
        )

    assert session.source_text == "abc"
    assert session.source_revision == 0


def test_source_text_edit_between_returns_minimal_contiguous_edit() -> None:
    """Source diff results should describe the smallest contiguous edit."""

    assert source_text_edit_between("alpha beta", "alpha brave beta") == (
        PromptSourceTextEdit(
            start=len("alpha b"),
            end=len("alpha b"),
            replacement_text="rave b",
        )
    )
    assert source_text_edit_between("same", "same") is None
