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

"""Test transient emphasis ownership and cleanup."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisAction,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptEmphasisAdjustmentOwner,
    PromptEmphasisAdjustmentSession,
    PromptEmphasisCaretBoundary,
    PromptTransientNeutralEmphasisOwner,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.service_doubles import (
    MutationServiceDouble,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.support import (
    build_controller,
    build_editor,
    build_mutation,
    key_event,
)


def test_apply_syntax_action_keeps_transient_neutral_shell_visible_after_unwrap() -> (
    None
):
    """Neutral unwrap keeps one temporary `1.00` shell visible for adjustment."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=-0.05)
    mutation = build_mutation(document_service, "cat", 0, 3)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    editor = build_editor("(cat:1.05)", position=2)
    controller = build_controller(
        editor,
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.weight_interaction.apply_syntax_action(action)

    assert mutation_service.apply_syntax_action_calls == [("(cat:1.05)", action)]
    assert editor.toPlainText() == "cat"
    assert editor.transient_neutral_emphasis_calls == [(0, 3)]
    assert editor.transient_neutral_emphasis_range() == (0, 3)
    assert editor.pulse_emphasis_feedback_calls == []


def test_apply_overlay_syntax_action_marks_transient_neutral_shell_as_overlay_owned() -> (
    None
):
    """Overlay-owned actions keep neutral emphasis alive independently of caret ownership."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=-0.05)
    mutation = build_mutation(document_service, "cat", 0, 3)
    mutation_service = MutationServiceDouble(apply_syntax_action_result=mutation)
    editor = build_editor("(cat:1.05)", position=10)
    controller = build_controller(
        editor,
        document_service=document_service,
        mutation_service=cast(PromptMutationService, mutation_service),
    )

    controller.weight_interaction.apply_overlay_syntax_action(action)

    assert editor.transient_neutral_emphasis_range() == (0, 3)
    assert (
        editor.transient_neutral_emphasis_owner()
        is PromptTransientNeutralEmphasisOwner.OVERLAY
    )


def test_apply_overlay_syntax_action_starts_overlay_emphasis_adjustment_session() -> (
    None
):
    """Overlay emphasis actions persist one shared overlay-owned session."""

    document_service = PromptDocumentService()
    action = PromptAdjustEmphasisAction(outer_start=0, outer_end=10, delta=0.05)
    mutation = build_mutation(document_service, "(cat:1.10)", 1, 4)
    editor = build_editor("(cat:1.05)", position=4)
    controller = build_controller(
        editor,
        document_service=document_service,
        mutation_service=cast(
            PromptMutationService,
            MutationServiceDouble(apply_syntax_action_result=mutation),
        ),
    )

    controller.weight_interaction.apply_overlay_syntax_action(action)

    assert editor.emphasis_adjustment_session() == PromptEmphasisAdjustmentSession(
        owner=PromptEmphasisAdjustmentOwner.OVERLAY,
        content_start=1,
        content_end=4,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )


def test_handle_key_release_clears_keyboard_owned_transient_neutral_emphasis() -> None:
    """Releasing Ctrl ends keyboard adjustment and removes keyboard-owned neutral deco."""

    editor = build_editor("cat", position=3)
    controller = build_controller(
        editor,
        mutation_service=cast(PromptMutationService, MutationServiceDouble()),
    )
    editor.show_transient_neutral_emphasis(
        content_start=0,
        content_end=3,
        owner=PromptTransientNeutralEmphasisOwner.KEYBOARD,
    )
    editor.set_emphasis_adjustment_session(
        owner=PromptEmphasisAdjustmentOwner.KEYBOARD,
        content_start=0,
        content_end=3,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )

    handled = controller.handle_key_release(key_event(Qt.Key.Key_Control))

    assert handled is False
    assert editor.transient_neutral_emphasis_range() is None
    assert editor.emphasis_adjustment_session() is None


def test_handle_overlay_visible_token_changed_clears_overlay_owned_session_and_shell() -> (
    None
):
    """Losing overlay token ownership clears overlay-owned session state."""

    editor = build_editor("cat", position=3)
    controller = build_controller(
        editor,
        mutation_service=cast(PromptMutationService, MutationServiceDouble()),
    )
    editor.set_emphasis_adjustment_session(
        owner=PromptEmphasisAdjustmentOwner.OVERLAY,
        content_start=0,
        content_end=3,
        caret_boundary=PromptEmphasisCaretBoundary.END,
    )
    editor.show_transient_neutral_emphasis(
        content_start=0,
        content_end=3,
        owner=PromptTransientNeutralEmphasisOwner.OVERLAY,
    )

    controller.weight_interaction.handle_visible_token_content_range_changed(None)

    assert editor.emphasis_adjustment_session() is None
    assert editor.transient_neutral_emphasis_range() is None
