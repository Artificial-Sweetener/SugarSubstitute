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

"""Verify weight results refer to canonical source and remain disposable."""

from __future__ import annotations

from decimal import Decimal

import pytest

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisAction,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.commands import weight_commands
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
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


def _adjust_cat(
    source: str, *, exact_source: bool = False
) -> tuple[PromptEditingSession[str], PromptWeightCommandResult[str]]:
    """Run a weight mutation through real source normalization and commit owners."""

    session: PromptEditingSession[str] = PromptEditingSession(
        source_text=source,
        source_revision=0,
        cursor_state=PromptCursorState(len(source), 0),
        max_undo_states=8,
        max_redo_states=8,
    )
    start = source.index("(cat:")
    command = build_weight_action_command(
        PromptWeightActionRequest(
            action=PromptAdjustEmphasisAction(
                outer_start=start,
                outer_end=source.index(")", start) + 1,
                delta=Decimal("0.05"),
            ),
            cursor_policy="preserve_cursor",
        ),
        mutation_service=PromptMutationService(),
        syntax_service=PromptSyntaxService(EmptyPromptWildcardCatalogGateway()),
        syntax_profile=prompt_syntax_profile("emphasis"),
        normalizer=PromptSourceNormalizationService(),
        exact_source=exact_source,
        record_undo=True,
        undo_snapshot=PromptUndoSnapshot(
            source_text=source,
            cursor_state=session.cursor_state,
            restoration_payload=source,
        ),
    )
    return session, command.execute(session)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("(cat:1.05), (dog)", "(cat:1.10), (dog:1.10)"),
        ("(dog), (cat:1.05)", "(dog:1.10), (cat:1.10)"),
        ("🐈 café (dog), (cat:1.05)", "🐈 café (dog:1.10), (cat:1.10)"),
    ],
)
def test_weight_feedback_matches_normalized_source_and_selection(
    source: str, expected: str
) -> None:
    """Map feedback content, prepared semantics, and cursor across normalization."""

    session, result = _adjust_cat(source)

    assert result.status == "applied"
    assert session.source_text == expected
    assert result.mutation is not None
    assert result.mutation.text == expected
    assert result.mutation.document_view.source_text == expected
    assert result.mutation.selection_start == expected.index("cat")
    assert result.mutation.selection_end == expected.index("cat") + 3
    assert result.cursor_state == PromptCursorState(len(expected), 0)
    assert result.render_plan is not None
    assert result.edit_commit is not None
    assert result.edit_commit.prepared_state is not None
    assert session.can_undo()


def test_weight_feedback_preserves_exact_source_mode() -> None:
    """Keep intentionally unnormalized neighboring source in exact-source mode."""

    session, result = _adjust_cat("(dog), (cat:1.05)", exact_source=True)

    assert session.source_text == "(dog), (cat:1.10)"
    assert result.mutation is not None
    assert result.mutation.text == session.source_text
    assert result.mutation.selection_start == 8
    assert result.mutation.selection_end == 11


def test_weight_feedback_rebuild_failure_keeps_committed_edit(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Treat optional canonical feedback failure as a recoverable optimization miss."""

    class FailedFeedbackProjector(PromptDocumentProjector):
        """Fail only the command's post-normalization feedback projection."""

        def build_document_view(self, text: str) -> PromptDocumentView:
            """Inject a rebuild failure after the editing session commits source."""

            raise ValueError("injected feedback failure")

    monkeypatch.setattr(
        weight_commands, "PromptDocumentProjector", FailedFeedbackProjector
    )

    session, result = _adjust_cat("(cat:1.05), (dog)")

    assert result.status == "applied"
    assert session.source_text == "(cat:1.10), (dog:1.10)"
    assert result.mutation is None
    assert result.render_plan is None
    assert result.edit_commit is not None
    assert result.edit_commit.prepared_state is None
    assert session.can_undo()
    assert "Prompt weight feedback preparation failed" in caplog.text
    assert session.source_text not in caplog.text
