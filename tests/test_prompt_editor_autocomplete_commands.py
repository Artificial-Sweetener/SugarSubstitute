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

"""Tests for Phase 3.3 prompt editor autocomplete acceptance commands."""

from __future__ import annotations

from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.commands import (
    PromptAcceptLoraAutocompleteCommand,
    PromptAcceptSceneAutocompleteCommand,
    PromptAcceptTagAutocompleteCommand,
    PromptAcceptWildcardAutocompleteCommand,
    PromptCommandDispatcher,
    PromptCommandSourceIdentity,
    PromptLoraAutocompleteAcceptance,
    PromptSceneAutocompleteAcceptance,
    PromptTagAutocompleteAcceptance,
    PromptWildcardAutocompleteAcceptance,
    build_autocomplete_acceptance_command,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptCursorState,
    PromptEditingSession,
    PromptUndoSnapshot,
)


def _session(
    source_text: str,
    *,
    cursor_position: int | None = None,
    anchor_position: int | None = None,
) -> PromptEditingSession[str]:
    """Return one editing session for autocomplete command tests."""

    default_position = len(source_text)
    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=(
                default_position if cursor_position is None else cursor_position
            ),
            anchor_position=default_position
            if anchor_position is None
            else anchor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )


def _undo_snapshot(session: PromptEditingSession[str]) -> PromptUndoSnapshot[str]:
    """Return the current session state as a passive undo snapshot."""

    return PromptUndoSnapshot(
        source_text=session.source_text,
        cursor_state=session.cursor_state,
        restoration_payload=session.source_text,
    )


def _source_identity(
    session: PromptEditingSession[str],
) -> PromptCommandSourceIdentity:
    """Return the current source identity for stale-command tests."""

    return PromptCommandSourceIdentity(
        source_revision=session.source_revision,
        source_length=len(session.source_text),
    )


def test_tag_autocomplete_command_escapes_parentheses_and_adds_comma() -> None:
    """Tag acceptance should preserve canonical tag insertion formatting."""

    session = _session("xx cat_", cursor_position=7)
    result = PromptCommandDispatcher(session).execute(
        PromptAcceptTagAutocompleteCommand(
            acceptance=PromptTagAutocompleteAcceptance(
                tag="cat_(animal)",
                prefix="cat_",
                word_start=3,
                word_end=7,
                active_tag_end=7,
                add_comma=True,
                source_identity=_source_identity(session),
            ),
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "applied"
    assert session.source_text == r"xx cat \(animal\), "
    assert result.cursor_state == PromptCursorState(
        cursor_position=len(r"xx cat \(animal\), "),
        anchor_position=len(r"xx cat \(animal\), "),
    )
    assert session.can_undo()


def test_tag_autocomplete_command_consumes_existing_matching_right_text() -> None:
    """Tag acceptance should consume already-typed compatible suffix text."""

    session = _session("long hir", cursor_position=6)
    result = PromptCommandDispatcher(session).execute(
        PromptAcceptTagAutocompleteCommand(
            acceptance=PromptTagAutocompleteAcceptance(
                tag="long hair",
                prefix="long h",
                word_start=0,
                word_end=6,
                active_tag_end=8,
                add_comma=False,
                source_identity=_source_identity(session),
            ),
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "applied"
    assert session.source_text == "long hair"


def test_tag_autocomplete_command_preserves_unrelated_right_text() -> None:
    """Tag acceptance should not consume incompatible text after the caret."""

    session = _session("long hx", cursor_position=6)
    result = PromptCommandDispatcher(session).execute(
        PromptAcceptTagAutocompleteCommand(
            acceptance=PromptTagAutocompleteAcceptance(
                tag="long hair",
                prefix="long h",
                word_start=0,
                word_end=6,
                active_tag_end=7,
                add_comma=False,
                source_identity=_source_identity(session),
            ),
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "applied"
    assert session.source_text == "long hairx"


def test_wildcard_autocomplete_command_replaces_placeholder_range() -> None:
    """Wildcard acceptance should wrap the accepted name in braces."""

    session = _session("{ani}", cursor_position=5)
    result = PromptCommandDispatcher(session).execute(
        PromptAcceptWildcardAutocompleteCommand(
            acceptance=PromptWildcardAutocompleteAcceptance(
                wildcard_name="animal",
                opener_start=0,
                replacement_end=5,
                source_identity=_source_identity(session),
            ),
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "applied"
    assert session.source_text == "{animal}"


def test_scene_autocomplete_command_replaces_only_scene_title() -> None:
    """Scene acceptance should leave the marker and following body intact."""

    session = _session("**po\nbody", cursor_position=4)
    result = PromptCommandDispatcher(session).execute(
        PromptAcceptSceneAutocompleteCommand(
            acceptance=PromptSceneAutocompleteAcceptance(
                title="portrait (close)",
                title_start=2,
                replacement_end=4,
                source_identity=_source_identity(session),
            ),
            normalizer=PromptSourceNormalizationService(),
            exact_source=True,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "applied"
    assert session.source_text == "**portrait (close)\nbody"


def test_lora_autocomplete_command_preserves_scheduler_safe_replacement() -> None:
    """LoRA acceptance should apply the prepared scheduler-safe token text."""

    source_text = "<lora:Civ:1.2>"
    session = _session(source_text, cursor_position=9)
    result = PromptCommandDispatcher(session).execute(
        PromptAcceptLoraAutocompleteCommand(
            acceptance=PromptLoraAutocompleteAcceptance(
                replacement_text=r"<lora:illustrious\characters\raw_midna:1.2>",
                replacement_start=0,
                replacement_end=len(source_text),
                source_identity=_source_identity(session),
            ),
            normalizer=PromptSourceNormalizationService(),
            exact_source=True,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "applied"
    assert session.source_text == r"<lora:illustrious\characters\raw_midna:1.2>"


def test_autocomplete_command_rejects_stale_source_identity() -> None:
    """Prepared autocomplete acceptance should fail closed on stale source identity."""

    session = _session("cat", cursor_position=3)
    command = build_autocomplete_acceptance_command(
        PromptTagAutocompleteAcceptance(
            tag="cat girl",
            prefix="cat",
            word_start=0,
            word_end=3,
            active_tag_end=3,
            add_comma=False,
            source_identity=PromptCommandSourceIdentity(
                source_revision=session.source_revision + 1,
                source_length=len(session.source_text),
            ),
        ),
        normalizer=PromptSourceNormalizationService(),
        exact_source=False,
        undo_snapshot=_undo_snapshot(session),
    )

    result = PromptCommandDispatcher(session).execute(command)

    assert result.status == "rejected"
    assert result.reason == "stale_source"
    assert session.source_text == "cat"
    assert not session.can_undo()


def test_autocomplete_command_rejects_invalid_source_range() -> None:
    """Prepared autocomplete acceptance should reject ranges outside current text."""

    session = _session("cat", cursor_position=3)
    result = PromptCommandDispatcher(session).execute(
        PromptAcceptWildcardAutocompleteCommand(
            acceptance=PromptWildcardAutocompleteAcceptance(
                wildcard_name="animal",
                opener_start=0,
                replacement_end=9,
                source_identity=_source_identity(session),
            ),
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            undo_snapshot=_undo_snapshot(session),
        )
    )

    assert result.status == "rejected"
    assert result.reason == "invalid_source_range"
    assert session.source_text == "cat"
    assert not session.can_undo()
