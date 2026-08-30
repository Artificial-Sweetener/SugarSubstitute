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

"""Verify focused context-menu and trigger-word insertion ownership."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
)
from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.application.prompt_editor.editing.structured_text import (
    PromptStructuredTextMutationService,
    PromptStructuredTextReplacement,
)
from substitute.domain.prompt.document.ranges import SourceRange
from substitute.presentation.editor.prompt_editor.commands.context_insertion import (
    PromptContextInsertionService,
)
from substitute.presentation.editor.prompt_editor.commands.execution import (
    PromptEditExecution,
)
from substitute.presentation.editor.prompt_editor.commands.source_service import (
    PromptSourceCommandService,
)
from substitute.presentation.editor.prompt_editor.commands.trigger_word_commands import (
    PromptTriggerWordCommandService,
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


@dataclass(slots=True)
class _Cursor:
    """Provide source-backed cursor reads."""

    selection_start: int
    selection_end: int
    cursor_position: int

    def hasSelection(self) -> bool:  # noqa: N802
        """Return whether the cursor has a selection."""

        return self.selection_start != self.selection_end

    def selectionStart(self) -> int:  # noqa: N802
        """Return the selection start."""

        return self.selection_start

    def selectionEnd(self) -> int:  # noqa: N802
        """Return the selection end."""

        return self.selection_end

    def position(self) -> int:
        """Return the live cursor position."""

        return self.cursor_position


@dataclass(frozen=True, slots=True)
class _InsertState:
    """Carry one captured context-menu insertion target."""

    insert_position: int | None
    should_replace_selection: bool | None


class _Boundary:
    """Provide inert payloads and record commits and key-group flushes."""

    def __init__(self) -> None:
        """Create empty observations."""

        self.commits: list[PromptEditCommit[str]] = []
        self.flush_reasons: list[str] = []

    def undo_comparison_payload(self) -> None:
        """Return no comparison payload."""

    def undo_restoration_payload(self) -> None:
        """Return no restoration payload."""

    def emit_undo_available_changed(self, available: bool) -> None:
        """Accept an undo transition."""

        _ = available

    def emit_redo_available_changed(self, available: bool) -> None:
        """Accept a redo transition."""

        _ = available

    def apply_edit_commit(self, commit: PromptEditCommit[str]) -> None:
        """Record one source commit."""

        self.commits.append(commit)

    def finish_typing_edit_block(self, *, reason: str) -> None:
        """Record a typing-only flush."""

        self.flush_reasons.append(reason)

    def finish_pending_key_edit_blocks(self, *, reason: str) -> None:
        """Record a complete key-edit flush."""

        self.flush_reasons.append(reason)


class _RejectingStructuredMutations(PromptStructuredTextMutationService):
    """Reject insertion to model a cross-value structured edit."""

    def replacement_for_range(
        self,
        source_text: str,
        source_range: SourceRange,
        replacement_text: str,
    ) -> PromptStructuredTextReplacement | None:
        """Reject every prepared replacement."""

        _ = source_text
        _ = source_range
        _ = replacement_text
        return None


def _service(
    source_text: str,
    *,
    cursor: _Cursor,
    insert_state: _InsertState,
    structured_text_mutations: PromptStructuredTextMutationService | None = None,
) -> tuple[
    PromptContextInsertionService[str],
    PromptEditingSession[str],
    _Boundary,
    list[str],
]:
    """Return a real context insertion owner and observable boundaries."""

    session = PromptEditingSession[str](
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor.cursor_position,
            cursor.cursor_position,
        ),
        max_undo_states=8,
        max_redo_states=8,
    )
    boundary = _Boundary()
    execution = PromptEditExecution(
        session=session,
        undo_payload_provider=boundary,
        availability_signal_sink=boundary,
        commit_sink=boundary,
    )
    execution.set_pending_key_flusher(boundary)
    normalizer = PromptSourceNormalizationService()
    source_commands = PromptSourceCommandService(
        execution=execution,
        normalizer=normalizer,
        exact_source_enabled=lambda: False,
    )
    mutations = structured_text_mutations or PromptStructuredTextMutationService(
        OrdinaryPromptDocumentSemantics()
    )
    trigger_words = PromptTriggerWordCommandService(
        execution=execution,
        normalizer=normalizer,
        exact_source_enabled=lambda: False,
        structured_text_mutations=mutations,
    )
    focus_restores: list[str] = []
    return (
        PromptContextInsertionService(
            source_commands=source_commands,
            trigger_word_commands=trigger_words,
            cursor_provider=lambda: cursor,
            context_insert_state_provider=lambda: insert_state,
            source_text_provider=lambda: session.source_text,
            structured_text_mutations=mutations,
            focus_restorer=lambda: focus_restores.append("restored"),
        ),
        session,
        boundary,
        focus_restores,
    )


def test_context_insertion_replaces_selection_and_flushes_once() -> None:
    """A live selection should become one command, commit, and focus restore."""

    service, session, boundary, focus = _service(
        "alpha beta",
        cursor=_Cursor(6, 10, 10),
        insert_state=_InsertState(2, None),
    )

    result = service.insert_context_menu_text("gamma")

    assert result.status == "applied"
    assert session.source_text == "alpha gamma"
    assert len(boundary.commits) == 1
    assert boundary.flush_reasons == ["context_menu_insert_text"]
    assert focus == ["restored"]


def test_context_insertion_uses_captured_position_when_selection_is_blocked() -> None:
    """A stale menu selection should use the captured insertion boundary."""

    service, session, _, focus = _service(
        "alpha beta",
        cursor=_Cursor(6, 10, 10),
        insert_state=_InsertState(5, False),
    )

    service.insert_context_menu_text(", gamma")

    assert session.source_text == "alpha, gamma beta"
    assert focus == ["restored"]


def test_context_insertion_rejection_restores_focus_without_a_commit() -> None:
    """An unavailable structured prompt value must not mutate source."""

    service, session, boundary, focus = _service(
        "alpha",
        cursor=_Cursor(0, 0, 3),
        insert_state=_InsertState(None, None),
        structured_text_mutations=_RejectingStructuredMutations(
            OrdinaryPromptDocumentSemantics()
        ),
    )

    result = service.insert_context_menu_text("beta")

    assert result.status == "rejected"
    assert result.reason == "prompt_value_unavailable"
    assert session.source_text == "alpha"
    assert boundary.commits == []
    assert boundary.flush_reasons == []
    assert focus == ["restored"]
