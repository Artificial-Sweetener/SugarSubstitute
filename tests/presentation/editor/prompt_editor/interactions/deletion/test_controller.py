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

"""Verify immutable grapheme and selection deletion intents."""

from __future__ import annotations

from typing import cast

from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.presentation.editor.prompt_editor.commands.execution import (
    PromptEditExecution,
)
from substitute.presentation.editor.prompt_editor.commands.source_service import (
    PromptSourceCommandService,
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
from substitute.presentation.editor.prompt_editor.interactions.deletion_controller import (
    PromptDeletionContext,
    PromptDeletionDirection,
    PromptDeletionResolver,
    PromptSurfaceDeletionController,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
    PromptProjectionSelection,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)


class _ProjectionDocument:
    """Provide only the source identity needed by stale raw deletion."""

    def __init__(self, source_text: str) -> None:
        """Store the committed projection source."""

        self.source_text = source_text


class _Boundary:
    """Record commits while providing inert edit boundary ports."""

    def __init__(self) -> None:
        """Create an empty commit log."""

        self.commits: list[PromptEditCommit[str]] = []

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


class _ContextProvider:
    """Return one replaceable immutable deletion context."""

    def __init__(self, context: PromptDeletionContext) -> None:
        """Store the current context."""

        self.context = context

    def deletion_context(self) -> PromptDeletionContext:
        """Return the current deletion context."""

        return self.context


class _ProjectionEffects:
    """Record projection-only deletion effects."""

    def __init__(self) -> None:
        """Create empty effect logs."""

        self.synchronizations: list[tuple[str, bool]] = []
        self.expanded_tokens: list[PromptProjectionToken] = []

    def synchronize_deletion_projection(
        self,
        *,
        reason: str,
        cancel_stale_safe_first: bool,
    ) -> None:
        """Record one synchronization request."""

        self.synchronizations.append((reason, cancel_stale_safe_first))

    def expand_token_for_deletion(self, token: PromptProjectionToken) -> None:
        """Record one token expansion."""

        self.expanded_tokens.append(token)


def _context(
    source_text: str,
    *,
    cursor_position: int,
    anchor_position: int | None = None,
    projection_source_text: str | None = None,
    stale_projection_geometry: bool = False,
) -> PromptDeletionContext:
    """Return a plain-source deletion context."""

    anchor = cursor_position if anchor_position is None else anchor_position
    caret = PromptProjectionCaretState(source_position=cursor_position)
    anchor_state = PromptProjectionCaretState(source_position=anchor)
    projection_document = cast(
        PromptProjectionDocument,
        _ProjectionDocument(
            source_text if projection_source_text is None else projection_source_text
        ),
    )
    return PromptDeletionContext(
        source_text=source_text,
        cursor_position=cursor_position,
        cursor_state=caret,
        anchor_state=anchor_state,
        selection=PromptProjectionSelection(anchor, cursor_position),
        projection_document=projection_document,
        focused_token=None,
        focused_token_expanded=False,
        stale_projection_geometry=stale_projection_geometry,
    )


def test_raw_backspace_resolves_one_complete_unicode_grapheme() -> None:
    """A stale-safe raw deletion must never split a joined emoji."""

    source_text = "A👩‍🚀"
    context = _context(
        source_text,
        cursor_position=len(source_text),
        projection_source_text="A",
        stale_projection_geometry=True,
    )

    intent = PromptDeletionResolver().raw_boundary_intent(
        context,
        PromptDeletionDirection.BACKWARD,
    )

    assert intent is not None
    assert (intent.start, intent.end) == (1, len(source_text))


def test_selection_deletion_submits_exactly_one_edit_commit() -> None:
    """Selection deletion should bypass surface mutation callbacks entirely."""

    source_text = "alpha beta"
    context_provider = _ContextProvider(
        _context(
            source_text,
            cursor_position=len(source_text),
            anchor_position=6,
        )
    )
    effects = _ProjectionEffects()
    boundary = _Boundary()
    session = PromptEditingSession[str](
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(len(source_text), 6),
        max_undo_states=8,
        max_redo_states=8,
    )
    execution = PromptEditExecution(
        session=session,
        undo_payload_provider=boundary,
        availability_signal_sink=boundary,
        commit_sink=boundary,
    )
    source_commands = PromptSourceCommandService(
        execution=execution,
        normalizer=PromptSourceNormalizationService(),
        exact_source_enabled=lambda: True,
    )
    controller = PromptSurfaceDeletionController(
        context_provider=context_provider,
        projection_effects=effects,
        source_commands=source_commands,
    )

    controller.backspace()

    assert session.source_text == "alpha "
    assert len(boundary.commits) == 1
    assert effects.synchronizations == [("backspace", False)]
    assert effects.expanded_tokens == []
