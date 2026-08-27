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

"""Provide the syntax-action editor double."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands.weight_commands import (
    PromptWeightActionRequest,
    PromptWeightCommandResult,
    build_weight_action_command,
)
from substitute.presentation.editor.prompt_editor.core.editing.cursor_state import (
    PromptCursorState,
)
from substitute.presentation.editor.prompt_editor.core.editing.session import (
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.core.editing.transactions import (
    PromptUndoSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptWeightControlIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)
from tests.presentation.editor.prompt_editor.interactions.support.editor import (
    ControllerEditorDouble,
    MenuCursorDouble,
)
from tests.support.prompt_editor.command_support import execute_prompt_command


class MousePressEventDouble:
    """Provide the position consumed by controller mouse-press handling."""

    def __init__(self, position: object) -> None:
        """Store one deterministic event position."""

        self._position = position

    def position(self) -> object:
        """Return the configured viewport-local event position."""

        return self._position


class SyntaxActionEditorDouble(ControllerEditorDouble):
    """Provide editor command behavior required by syntax-action tests."""

    def __init__(
        self,
        *,
        clicked_cursor: MenuCursorDouble,
        current_cursor: MenuCursorDouble,
        text: str,
    ) -> None:
        """Initialize prompt text, command state, and projection call tracking."""

        super().__init__(
            clicked_cursor=clicked_cursor,
            current_cursor=current_cursor,
            text=text,
        )
        self.set_plain_text_calls: list[str] = []
        self.replace_document_text_calls: list[str] = []
        self.replace_document_text_with_prompt_state_calls: list[
            tuple[str, object, object]
        ] = []
        self.blocked_signals: list[bool] = []
        self.focus_calls = 0
        self.pulse_emphasis_feedback_calls: list[tuple[int, int]] = []
        self.transient_neutral_emphasis_calls: list[tuple[int, int]] = []
        self._emphasis_adjustment_session: PromptEmphasisAdjustmentSession | None = None
        self._transient_neutral_emphasis_range: tuple[int, int] | None = None
        self._transient_neutral_emphasis_owner: (
            PromptTransientNeutralEmphasisOwner | None
        ) = None
        self.emphasis_content_boundary_calls: list[tuple[int, int, bool]] = []
        self.executed_weight_requests: list[PromptWeightActionRequest] = []
        self._source_revision = 0

    def execute_weight_action(
        self,
        request: PromptWeightActionRequest,
        *,
        mutation_service: PromptMutationService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> PromptWeightCommandResult[object]:
        """Execute a prepared weight command against the fake source state."""

        self.executed_weight_requests.append(request)
        cursor = self.textCursor()
        cursor_state = PromptCursorState(
            cursor_position=cursor.position(),
            anchor_position=cursor.anchor(),
        )
        session = PromptEditingSession[object](
            source_text=self.toPlainText(),
            source_revision=self._source_revision,
            cursor_state=cursor_state,
            max_undo_states=20,
            max_redo_states=20,
        )
        command = build_weight_action_command(
            request,
            mutation_service=mutation_service,
            syntax_service=syntax_service,
            syntax_profile=syntax_profile,
            normalizer=PromptSourceNormalizationService(),
            exact_source=False,
            record_undo=True,
            undo_snapshot=PromptUndoSnapshot[object](
                source_text=self.toPlainText(),
                cursor_state=cursor_state,
                source_revision=self._source_revision,
            ),
        )
        result = cast(
            PromptWeightCommandResult[object],
            execute_prompt_command(session, command),
        )
        edit_commit = result.edit_commit
        if edit_commit is not None:
            next_text = edit_commit.next_snapshot.source_text
            self._source_revision = edit_commit.next_snapshot.source_revision
            if result.mutation is not None and result.render_plan is not None:
                self.replace_document_text_with_prompt_state(
                    next_text,
                    document_view=result.mutation.document_view,
                    render_plan=result.render_plan,
                )
            else:
                self.replace_document_text(next_text)
        if result.cursor_state is not None:
            self.setTextCursor(
                MenuCursorDouble(
                    text=self.toPlainText(),
                    position=result.cursor_state.cursor_position,
                    anchor=result.cursor_state.anchor_position,
                )
            )
        return result

    def setPlainText(self, text: str) -> None:  # noqa: N802
        """Replace the backing prompt text and keep cursors in sync."""

        super().setPlainText(text)
        self.set_plain_text_calls.append(text)

    def replace_document_text(self, text: str) -> None:
        """Replace the backing prompt text through the undo-safe surface hook."""

        self.setPlainText(text)
        self.replace_document_text_calls.append(text)

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: object,
        render_plan: object,
    ) -> None:
        """Replace backing text through the prompt-state optimized hook."""

        self.setPlainText(text)
        self.replace_document_text_with_prompt_state_calls.append(
            (text, document_view, render_plan)
        )

    def blockSignals(self, blocked: bool) -> None:  # noqa: N802
        """Record signal blocking requested by controller mutations."""

        self.blocked_signals.append(blocked)

    def setFocus(self) -> None:  # noqa: N802
        """Record focus restoration after inline control clicks."""

        self.focus_calls += 1

    def pulse_emphasis_feedback(self, *, outer_start: int, outer_end: int) -> None:
        """Record transient emphasis feedback requests from the controller."""

        self.pulse_emphasis_feedback_calls.append((outer_start, outer_end))

    def set_emphasis_adjustment_session(
        self,
        *,
        owner: PromptEmphasisAdjustmentOwner,
        content_start: int,
        content_end: int,
        caret_boundary: PromptEmphasisCaretBoundary,
        wheel_intent_identity: PromptWeightControlIdentity | None = None,
    ) -> None:
        """Record one active emphasis-adjustment session owned by the controller."""

        self._emphasis_adjustment_session = PromptEmphasisAdjustmentSession(
            owner=owner,
            content_start=content_start,
            content_end=content_end,
            caret_boundary=caret_boundary,
            wheel_intent_identity=wheel_intent_identity,
        )

    def clear_emphasis_adjustment_session(self) -> None:
        """Clear the active emphasis-adjustment session."""

        self._emphasis_adjustment_session = None

    def emphasis_adjustment_session(self) -> PromptEmphasisAdjustmentSession | None:
        """Return the active emphasis-adjustment session when present."""

        return self._emphasis_adjustment_session

    def emphasis_adjustment_session_range(self) -> tuple[int, int] | None:
        """Return the active emphasis-adjustment content range when present."""

        session = self._emphasis_adjustment_session
        if session is None:
            return None
        return (session.content_start, session.content_end)

    def emphasis_adjustment_session_matches_range(
        self,
        *,
        content_start: int,
        content_end: int,
    ) -> bool:
        """Return whether the active emphasis-adjustment session owns one range."""

        session = self._emphasis_adjustment_session
        if session is None:
            return False
        return (
            session.content_start == content_start
            and session.content_end == content_end
        )

    def show_transient_neutral_emphasis(
        self,
        *,
        content_start: int,
        content_end: int,
        owner: PromptTransientNeutralEmphasisOwner = (
            PromptTransientNeutralEmphasisOwner.CARET
        ),
    ) -> None:
        """Record requests to project a temporary neutral emphasis shell."""

        self._transient_neutral_emphasis_range = (content_start, content_end)
        self._transient_neutral_emphasis_owner = owner
        self.transient_neutral_emphasis_calls.append((content_start, content_end))

    def clear_transient_neutral_emphasis(self) -> None:
        """Clear any temporary neutral emphasis shell."""

        self._transient_neutral_emphasis_range = None
        self._transient_neutral_emphasis_owner = None

    def clear_overlay_owned_transient_neutral_emphasis(self) -> None:
        """Clear the transient shell only when overlay interaction owns it."""

        if (
            self._transient_neutral_emphasis_owner
            is PromptTransientNeutralEmphasisOwner.OVERLAY
        ):
            self.clear_transient_neutral_emphasis()

    def transient_neutral_emphasis_range(self) -> tuple[int, int] | None:
        """Return the currently tracked temporary neutral emphasis range."""

        return self._transient_neutral_emphasis_range

    def transient_neutral_emphasis_owner(
        self,
    ) -> PromptTransientNeutralEmphasisOwner | None:
        """Return the owner of the currently tracked temporary neutral shell."""

        return self._transient_neutral_emphasis_owner

    def set_emphasis_caret_to_content_boundary(
        self,
        *,
        content_start: int,
        content_end: int,
        prefer_end: bool,
    ) -> bool:
        """Record one projected emphasis-content boundary placement request."""

        self.emphasis_content_boundary_calls.append(
            (content_start, content_end, prefer_end)
        )
        caret_position = content_end if prefer_end else content_start
        self.textCursor().setPosition(caret_position)
        return True
