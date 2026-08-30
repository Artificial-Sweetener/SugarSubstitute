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

"""Test mutation adoption and cached prompt state."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutation,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    syntax_renderer_double,
    syntax_service,
)

from tests.presentation.editor.prompt_editor.interactions.state.editor_double import (
    StateEditorDouble,
)
from tests.presentation.editor.prompt_editor.interactions.state.support import (
    build_controller,
)


def test_apply_mutation_refreshes_cached_prompt_state_even_when_text_is_unchanged() -> (
    None
):
    """Controller state refresh uses the mutation snapshot for unchanged text."""

    document_service = PromptDocumentService()
    initial_document_view = document_service.build_document_view("cat")
    stale_document_view = document_service.build_document_view("(cat:1.05)")
    refreshed_document_view = document_service.build_document_view("cat")
    editor = StateEditorDouble(text="cat", position=0)
    controller = build_controller(editor, document_service=document_service)
    controller._syntax_state.replace_prompt_state_with_render_plan(
        initial_document_view,
        syntax_service().build_render_plan(
            stale_document_view,
            prompt_syntax_profile("emphasis", "wildcard"),
        ),
    )

    controller._apply_mutation(
        PromptMutation(
            text="cat",
            selection_start=0,
            selection_end=3,
            document_view=refreshed_document_view,
        )
    )

    assert editor.toPlainText() == "cat"
    assert editor.replace_document_text_calls == []
    assert controller.document_view is refreshed_document_view
    assert controller.syntax_render_plan.syntax_spans == ()


def test_apply_mutation_rejects_source_changing_mutation_without_replacement() -> None:
    """Legacy mutation adoption does not reintroduce source replacement."""

    document_service = PromptDocumentService()
    syntax_renderers = syntax_renderer_double()
    editor = StateEditorDouble(text="cat", position=0)
    controller = build_controller(
        editor,
        document_service=document_service,
        syntax_renderers=syntax_renderers,
    )
    mutation_document_view = document_service.build_document_view("(cat:1.05)")
    initial_prompt_state_calls = tuple(syntax_renderers.prompt_state_calls)

    controller._apply_mutation(
        PromptMutation(
            text="(cat:1.05)",
            selection_start=1,
            selection_end=4,
            document_view=mutation_document_view,
        )
    )

    assert editor.toPlainText() == "cat"
    assert editor.replace_document_text_calls == []
    assert tuple(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls
