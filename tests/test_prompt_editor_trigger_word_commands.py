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

"""Test identity-safe, prompt-aware LoRA trigger-word insertion commands."""

from __future__ import annotations

from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.application.managed_text_assets.wildcard_csv_document_semantics import (
    WildcardCsvDocumentSemantics,
)
from substitute.application.prompt_editor.prompt_structured_text_mutation_service import (
    PromptStructuredTextMutationService,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandDispatcher,
    PromptCommandSourceIdentity,
    PromptTriggerWordInsertionRequest,
    build_trigger_word_insertion_command,
    prepare_trigger_word_insertion,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)


def _request(
    *,
    source_text: str,
    insert_position: int | None = None,
    selection_start: int = 0,
    selection_end: int = 0,
    replace_selection: bool = False,
    source_revision: int = 0,
) -> PromptTriggerWordInsertionRequest:
    """Return one fully identified insertion request."""

    return PromptTriggerWordInsertionRequest(
        trigger_words="imp princess, twili helmet",
        source_identity=PromptCommandSourceIdentity(
            source_revision=source_revision,
            source_length=len(source_text),
        ),
        insert_position=insert_position,
        selection_start=selection_start,
        selection_end=selection_end,
        replace_selection=replace_selection,
    )


def test_trigger_word_insertion_targets_end_of_clicked_prompt_segment() -> None:
    """Clicked words should not be split by context-menu insertion."""

    source = "high quality portrait, outdoors"

    prepared = prepare_trigger_word_insertion(
        source_text=source,
        request=_request(source_text=source, insert_position=8),
    )

    assert prepared == (
        len("high quality portrait"),
        len("high quality portrait"),
        ", imp princess, twili helmet",
    )


def test_trigger_word_insertion_preserves_newline_boundary() -> None:
    """Trigger words should stay on the clicked line without consuming newlines."""

    source = "portrait\nsecond scene"

    prepared = prepare_trigger_word_insertion(
        source_text=source,
        request=_request(source_text=source, insert_position=2),
    )

    assert prepared == (8, 8, ", imp princess, twili helmet")


def test_trigger_word_insertion_replaces_explicit_selection_exactly() -> None:
    """Explicit replacement should not add delimiters around the selected range."""

    source = "alpha selected omega"

    prepared = prepare_trigger_word_insertion(
        source_text=source,
        request=_request(
            source_text=source,
            selection_start=6,
            selection_end=14,
            replace_selection=True,
        ),
    )

    assert prepared == (6, 14, "imp princess, twili helmet")


def test_trigger_word_command_rejects_stale_source_without_mutation() -> None:
    """A QAction prepared for an older revision must never mutate newer source."""

    source = "portrait"
    session: PromptEditingSession[str] = PromptEditingSession(
        source_text=source,
        source_revision=1,
        cursor_state=PromptCursorState(8, 8),
        max_undo_states=8,
        max_redo_states=8,
    )
    command = build_trigger_word_insertion_command(
        _request(source_text=source, insert_position=8, source_revision=0),
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        undo_snapshot=PromptUndoSnapshot(
            source_text=source,
            cursor_state=session.cursor_state,
            restoration_payload=source,
        ),
    )

    result = PromptCommandDispatcher(session).execute(command)

    assert result.status == "rejected"
    assert result.reason == "stale_source"
    assert session.source_text == source
    assert session.can_undo() is False


def test_trigger_word_command_is_one_undo_safe_source_change() -> None:
    """Insertion should publish one source revision and one undo snapshot."""

    source = "portrait"
    session: PromptEditingSession[str] = PromptEditingSession(
        source_text=source,
        source_revision=0,
        cursor_state=PromptCursorState(8, 8),
        max_undo_states=8,
        max_redo_states=8,
    )
    command = build_trigger_word_insertion_command(
        _request(source_text=source, insert_position=8),
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        undo_snapshot=PromptUndoSnapshot(
            source_text=source,
            cursor_state=session.cursor_state,
            restoration_payload=source,
        ),
    )

    result = PromptCommandDispatcher(session).execute(command)

    assert result.status == "applied"
    assert session.source_text == "portrait, imp princess, twili helmet"
    assert session.source_revision == 1
    assert session.can_undo() is True


def test_trigger_word_command_uses_quoted_csv_value_boundary() -> None:
    """Trigger words should append inside a quoted cell and preserve its quotes."""

    source = 'Prompt\n"portrait"'
    insertion_position = source.rindex('"')
    session: PromptEditingSession[str] = PromptEditingSession(
        source_text=source,
        source_revision=0,
        cursor_state=PromptCursorState(insertion_position, insertion_position),
        max_undo_states=8,
        max_redo_states=8,
    )
    command = build_trigger_word_insertion_command(
        _request(source_text=source, insert_position=insertion_position),
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        undo_snapshot=PromptUndoSnapshot(
            source_text=source,
            cursor_state=session.cursor_state,
            restoration_payload=source,
        ),
        structured_text_mutations=PromptStructuredTextMutationService(
            WildcardCsvDocumentSemantics()
        ),
    )

    result = PromptCommandDispatcher(session).execute(command)

    assert result.status == "applied"
    assert session.source_text == ('Prompt\n"portrait, imp princess, twili helmet"')
    assert session.cursor_state.cursor_position == len(session.source_text) - 1
