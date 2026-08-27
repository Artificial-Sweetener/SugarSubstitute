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

"""Test syntax renderer state coordination."""

from __future__ import annotations


from substitute.application.prompt_editor.document.service import PromptDocumentService
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    syntax_renderer_double,
)

from tests.presentation.editor.prompt_editor.interactions.state.editor_double import (
    StateEditorDouble,
)
from tests.presentation.editor.prompt_editor.interactions.state.support import (
    build_controller,
)


def test_controller_initialization_pushes_cached_prompt_state_into_syntax_renderers() -> (
    None
):
    """Controller startup seeds the syntax-renderer seam from cached prompt state."""

    document_service = PromptDocumentService()
    syntax_renderers = syntax_renderer_double()
    controller = build_controller(
        StateEditorDouble(text="(cat:1.05)", position=3),
        document_service=document_service,
        syntax_renderers=syntax_renderers,
    )

    assert controller.document_view.source_text == "(cat:1.05)"
    assert len(syntax_renderers.prompt_state_calls) == 1
    snapshot = syntax_renderers.prompt_state_calls[0]
    assert snapshot.document is controller.document_view
    assert snapshot.render_plan is controller.syntax_render_plan
    assert syntax_renderers.active_span_calls[-1] == (
        controller.active_syntax_span,
        3,
    )


def test_handle_cursor_position_changed_updates_active_syntax_span() -> None:
    """Caret movement drives the syntax renderer's active span selection."""

    syntax_renderers = syntax_renderer_double()
    editor = StateEditorDouble(text="(cat:1.05), (dog:1.15)", position=3)
    controller = build_controller(editor, syntax_renderers=syntax_renderers)

    editor.textCursor().setPosition(16)
    controller.handle_cursor_position_changed()

    assert controller.active_syntax_span == controller.document_view.syntax_spans[1]
    assert syntax_renderers.active_span_calls[-1] == (
        controller.document_view.syntax_spans[1],
        16,
    )


def test_handle_hide_clears_syntax_renderer_transient_state() -> None:
    """Hide handling clears transient renderer state alongside autocomplete."""

    syntax_renderers = syntax_renderer_double()
    controller = build_controller(
        StateEditorDouble(text="(cat:1.05)", position=0),
        syntax_renderers=syntax_renderers,
    )

    controller.handle_hide()

    assert syntax_renderers.clear_transient_state_calls == 1
