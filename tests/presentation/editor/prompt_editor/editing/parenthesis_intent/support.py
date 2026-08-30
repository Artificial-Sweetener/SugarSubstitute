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

"""Editing-session helpers for parenthesis-intent contracts."""

from __future__ import annotations


from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.presentation.editor.prompt_editor.core.editing.commands import (
    PromptReplaceRangeEdit,
)
from substitute.presentation.editor.prompt_editor.core.editing.commit import (
    PromptEditCommit,
)
from substitute.presentation.editor.prompt_editor.core.editing.cursor_state import (
    PromptCursorState,
)
from substitute.presentation.editor.prompt_editor.core.editing.session import (
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.core.editing.source_commands import (
    PromptSourceEditOrigin,
)
from substitute.presentation.editor.prompt_editor.core.editing.transactions import (
    PromptUndoSnapshot,
)


def _undo_snapshot(session: PromptEditingSession[str]) -> PromptUndoSnapshot[str]:
    """Capture source intent alongside source and cursor state."""

    return PromptUndoSnapshot(
        source_text=session.source_text,
        cursor_state=session.cursor_state,
        parenthesis_intents=session.source_snapshot().parenthesis_intents,
        generated_emphases=session.source_snapshot().generated_emphases,
    )


def _session(source_text: str) -> PromptEditingSession[str]:
    """Build one editing session for parenthesis-intent tests."""

    return PromptEditingSession(
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(len(source_text), len(source_text)),
        max_undo_states=10,
        max_redo_states=10,
    )


def _replace_source_range(
    session: PromptEditingSession[str],
    *,
    start: int,
    end: int,
    replacement_text: str,
    normalizer: PromptSourceNormalizationService,
    origin: PromptSourceEditOrigin,
    exact_source: bool,
    record_undo: bool,
    undo_snapshot: PromptUndoSnapshot[str],
) -> PromptEditCommit[str]:
    """Execute one range edit through the typed session boundary."""

    return session.execute(
        PromptReplaceRangeEdit(
            start=start,
            end=end,
            replacement_text=replacement_text,
            normalizer=normalizer,
            origin=origin,
            exact_source=exact_source,
            record_undo=record_undo,
            undo_snapshot=undo_snapshot,
        )
    )
