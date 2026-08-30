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

"""Contracts for parenthesis intent across prompt editor session history."""

from __future__ import annotations


from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.presentation.editor.prompt_editor.core.editing.commands import (
    PromptRedoEdit,
    PromptUndoEdit,
)
from substitute.presentation.editor.prompt_editor.core.editing.source_commands import (
    PromptSourceEditOrigin,
)

from .support import _replace_source_range, _session, _undo_snapshot


def test_manual_unescape_is_preserved_until_complete_segment_replacement() -> None:
    """Keep user-authored escapement intent through later local edits."""

    source = r"\(blue laces\)"
    session = _session(source)
    normalizer = PromptSourceNormalizationService()
    first = _replace_source_range(
        session,
        start=0,
        end=1,
        replacement_text="",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    closing_slash = first.next_snapshot.source_text.index(r"\)")
    _replace_source_range(
        session,
        start=closing_slash,
        end=closing_slash + 1,
        replacement_text="",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    _replace_source_range(
        session,
        start=len(session.source_text) - 1,
        end=len(session.source_text) - 1,
        replacement_text="!",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )

    assert session.source_text == "(blue laces!)"
    assert session.source_snapshot().parenthesis_intents

    _replace_source_range(
        session,
        start=0,
        end=len(session.source_text),
        replacement_text="(fresh)",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.PASTE,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )

    assert session.source_text == "(fresh:1.10)"
    assert session.source_snapshot().parenthesis_intents == ()


def test_manual_escapement_intent_round_trips_with_undo_redo() -> None:
    """Restore user parenthesis intent together with source history."""

    session = _session(r"\(blue laces\)")
    normalizer = PromptSourceNormalizationService()
    _replace_source_range(
        session,
        start=0,
        end=1,
        replacement_text="",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    closing_slash = session.source_text.index(r"\)")
    _replace_source_range(
        session,
        start=closing_slash,
        end=closing_slash + 1,
        replacement_text="",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )

    undo_result = session.execute(
        PromptUndoEdit(current_snapshot=_undo_snapshot(session))
    )

    assert undo_result is not None
    assert session.source_text == r"(blue laces\)"
    assert session.source_snapshot().parenthesis_intents

    redo_result = session.execute(
        PromptRedoEdit(current_snapshot=_undo_snapshot(session))
    )

    assert redo_result is not None
    assert session.source_text == "(blue laces)"
    assert session.source_snapshot().parenthesis_intents


def test_generated_emphasis_provenance_round_trips_with_undo_redo() -> None:
    """Restore generated-weight ownership so later wrapping still re-evaluates."""

    session = _session("(test")
    normalizer = PromptSourceNormalizationService()
    _replace_source_range(
        session,
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    generated_snapshot = _undo_snapshot(session)

    assert (
        session.execute(PromptUndoEdit(current_snapshot=generated_snapshot)) is not None
    )
    assert (
        session.execute(PromptRedoEdit(current_snapshot=_undo_snapshot(session)))
        is not None
    )
    assert session.source_snapshot().generated_emphases

    _replace_source_range(
        session,
        start=0,
        end=0,
        replacement_text="(",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )
    _replace_source_range(
        session,
        start=len(session.source_text),
        end=len(session.source_text),
        replacement_text=")",
        normalizer=normalizer,
        origin=PromptSourceEditOrigin.TYPED,
        exact_source=False,
        record_undo=True,
        undo_snapshot=_undo_snapshot(session),
    )

    assert session.source_text == "(test:1.21)"
    assert session.source_snapshot().generated_emphases[0].nesting_depth == 2
