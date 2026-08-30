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

"""Test keyboard emphasis intent and caret contracts."""

from __future__ import annotations

from typing import cast


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptSetEmphasisWeightAction,
    PromptSetEmphasisWeightContentAction,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.service_doubles import (
    MutationServiceDouble,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.support import (
    build_controller,
    build_editor,
    build_mutation,
)


def test_modify_emphasis_places_keyboard_neutral_caret_at_content_boundary() -> None:
    """Keyboard emphasis unwrap places the caret at the token content boundary."""

    document_service = PromptDocumentService()
    mutation = build_mutation(document_service, "cat", 0, 3)
    editor = build_editor("(cat:1.05)", position=4, anchor=1)
    controller = build_controller(
        editor,
        document_service=document_service,
        mutation_service=cast(
            PromptMutationService,
            MutationServiceDouble(apply_syntax_action_result=mutation),
        ),
    )

    controller.weight_interaction.modify_emphasis(-0.05)

    assert editor.emphasis_content_boundary_calls == [(0, 3, True)]
    assert editor.emphasis_adjustment_session() == PromptEmphasisAdjustmentSession(
        owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
        content_start=0,
        content_end=3,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )


def test_apply_keyboard_emphasis_action_preserves_session_caret_boundary_preference() -> (
    None
):
    """Keyboard-session emphasis actions keep using the stored content boundary."""

    document_service = PromptDocumentService()
    mutation = build_mutation(document_service, "cat", 0, 3)
    editor = build_editor("(cat:1.05)", position=4, anchor=1)
    controller = build_controller(
        editor,
        document_service=document_service,
        mutation_service=cast(
            PromptMutationService,
            MutationServiceDouble(apply_syntax_action_result=mutation),
        ),
    )
    editor.set_emphasis_adjustment_session(
        owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
        content_start=1,
        content_end=4,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )

    controller.weight_interaction.modify_emphasis(-0.05)

    assert editor.emphasis_content_boundary_calls == [(0, 3, True)]


def test_apply_syntax_action_routes_exact_weight_actions_through_emphasis_path() -> (
    None
):
    """Exact-weight actions reuse the same no-selection emphasis-apply path."""

    document_service = PromptDocumentService()
    action = PromptSetEmphasisWeightAction(outer_start=0, outer_end=10, weight=1.20)
    mutation = build_mutation(document_service, "(cat:1.20)", 1, 4)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    editor = build_editor("(cat:1.05)", position=2)
    controller = build_controller(
        editor,
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.weight_interaction.apply_syntax_action(action)

    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert editor.toPlainText() == "(cat:1.20)"
    assert editor.pulse_emphasis_feedback_calls == [(0, 10)]
    assert editor.transient_neutral_emphasis_calls == []


def test_apply_syntax_action_keeps_transient_neutral_shell_after_exact_neutral_set() -> (
    None
):
    """Exact neutral sets preserve the transient `1.00` shell for continued editing."""

    document_service = PromptDocumentService()
    action = PromptSetEmphasisWeightContentAction(
        content_start=0,
        content_end=3,
        weight=1.00,
    )
    mutation = build_mutation(document_service, "cat", 0, 3)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    editor = build_editor("cat", position=2)
    controller = build_controller(
        editor,
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.weight_interaction.apply_syntax_action(action)

    assert mutation_service.apply_syntax_action_calls == [("cat", action)]
    assert editor.toPlainText() == "cat"
    assert editor.transient_neutral_emphasis_calls == [(0, 3)]
    assert editor.transient_neutral_emphasis_range() == (0, 3)
