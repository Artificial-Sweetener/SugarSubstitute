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

"""Test syntax-action state publication."""

from __future__ import annotations

from typing import cast


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutation,
    PromptMutationService,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptAdjustEmphasisContentAction,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.service_doubles import (
    DocumentServiceDouble,
    MutationServiceDouble,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.support import (
    build_controller,
    build_editor,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    syntax_renderer_double,
)


def test_modify_emphasis_uses_typed_mutation_result_to_refresh_cached_state() -> None:
    """Controller emphasis edits adopt the mutation snapshot without local reparsing."""

    document_service = PromptDocumentService()
    initial_document_service = DocumentServiceDouble(document_service, text="cat")
    updated_document_view = document_service.build_document_view("(cat:1.05)")
    mutation_service = MutationServiceDouble(
        apply_syntax_action_result=PromptMutation(
            text="(cat:1.05)",
            selection_start=1,
            selection_end=4,
            document_view=updated_document_view,
        )
    )
    editor = build_editor("cat", position=3, anchor=0)
    syntax_renderers = syntax_renderer_double()
    controller = build_controller(
        editor,
        document_service=cast(PromptDocumentService, initial_document_service),
        mutation_service=cast(PromptMutationService, mutation_service),
        syntax_renderers=syntax_renderers,
    )

    controller.weight_interaction.modify_emphasis(0.05)

    assert initial_document_service.build_calls == ["cat"]
    assert mutation_service.apply_syntax_action_calls == [
        (
            "cat",
            PromptAdjustEmphasisContentAction(
                content_start=0,
                content_end=3,
                delta=0.05,
            ),
        )
    ]
    assert mutation_service.adjust_calls == []
    assert editor.toPlainText() == "(cat:1.05)"
    assert editor.replace_document_text_calls == []
    assert len(editor.replace_document_text_with_prompt_state_calls) == 1
    replaced_text, replaced_document_view, replaced_render_plan = (
        editor.replace_document_text_with_prompt_state_calls[0]
    )
    assert replaced_text == "(cat:1.05)"
    assert replaced_document_view is updated_document_view
    assert replaced_render_plan is syntax_renderers.prompt_state_calls[-1].render_plan
    assert editor.textCursor().selectionStart() == 4
    assert editor.textCursor().selectionEnd() == 4
    assert editor.pulse_emphasis_feedback_calls == [(0, 10)]
    assert controller.document_view is updated_document_view
    assert len(controller.syntax_render_plan.syntax_spans) == 1
    assert controller.active_syntax_span == updated_document_view.syntax_spans[0]
