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

"""Tests for prompt interaction cached-state and renderer coordination."""

from __future__ import annotations

from typing import Any

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptMutation,
    PromptMutationService,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    OverlayDouble,
    SyntaxRendererCoordinatorDouble,
    autocomplete_double,
    prompt_interaction_controller,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)


class StateEditorDouble(ControllerEditorDouble):
    """Add mutation replacement tracking to the shared controller editor double."""

    def __init__(self, *, text: str, position: int) -> None:
        """Initialize the editor with matching click and caret cursors."""

        super().__init__(
            clicked_cursor=MenuCursorDouble(text=text, position=position),
            current_cursor=MenuCursorDouble(text=text, position=position),
            text=text,
        )
        self.replace_document_text_calls: list[str] = []
        self.replace_document_text_with_prompt_state_calls: list[
            tuple[str, object, object]
        ] = []
        self.blocked_signals: list[bool] = []

    def replace_document_text(self, text: str) -> None:
        """Replace backing text through the undo-safe surface hook."""

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


def test_apply_mutation_refreshes_cached_prompt_state_even_when_text_is_unchanged() -> (
    None
):
    """Controller state refresh uses the mutation snapshot for unchanged text."""

    document_service = PromptDocumentService()
    initial_document_view = document_service.build_document_view("cat")
    stale_document_view = document_service.build_document_view("(cat:1.05)")
    refreshed_document_view = document_service.build_document_view("cat")
    editor = StateEditorDouble(text="cat", position=0)
    controller = _controller(editor, document_service=document_service)
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


def test_controller_initialization_pushes_cached_prompt_state_into_syntax_renderers() -> (
    None
):
    """Controller startup seeds the syntax-renderer seam from cached prompt state."""

    document_service = PromptDocumentService()
    syntax_renderers = syntax_renderer_double()
    controller = _controller(
        StateEditorDouble(text="(cat:1.05)", position=3),
        document_service=document_service,
        syntax_renderers=syntax_renderers,
    )

    assert controller.document_view.source_text == "(cat:1.05)"
    assert syntax_renderers.prompt_state_calls == [
        (controller.document_view, controller.syntax_render_plan)
    ]
    assert syntax_renderers.active_span_calls[-1] == (
        controller.active_syntax_span,
        3,
    )


def test_handle_cursor_position_changed_updates_active_syntax_span() -> None:
    """Caret movement drives the syntax renderer's active span selection."""

    syntax_renderers = syntax_renderer_double()
    editor = StateEditorDouble(text="(cat:1.05), (dog:1.15)", position=3)
    controller = _controller(editor, syntax_renderers=syntax_renderers)

    editor.textCursor().setPosition(16)
    controller.handle_cursor_position_changed()

    assert controller.active_syntax_span == controller.document_view.syntax_spans[1]
    assert syntax_renderers.active_span_calls[-1] == (
        controller.document_view.syntax_spans[1],
        16,
    )


def test_handle_resize_and_scroll_refresh_syntax_renderer_geometry() -> None:
    """Resize, move, and scroll updates request renderer geometry recomputation."""

    syntax_renderers = syntax_renderer_double()
    controller = _controller(
        StateEditorDouble(text="(cat:1.05)", position=3),
        syntax_renderers=syntax_renderers,
    )
    overlay = OverlayDouble([0], has_reordered=False)
    controller._reorder._segment_overlay = overlay
    initial_refresh_calls = syntax_renderers.refresh_geometry_calls

    controller.handle_resize()
    controller.handle_move()
    controller.handle_viewport_scroll()

    assert syntax_renderers.refresh_geometry_calls == initial_refresh_calls + 3
    assert overlay.refresh_geometry_calls == 2


def test_apply_mutation_rejects_source_changing_mutation_without_replacement() -> None:
    """Legacy mutation adoption does not reintroduce source replacement."""

    document_service = PromptDocumentService()
    syntax_renderers = syntax_renderer_double()
    editor = StateEditorDouble(text="cat", position=0)
    controller = _controller(
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


def test_handle_hide_clears_syntax_renderer_transient_state() -> None:
    """Hide handling clears transient renderer state alongside autocomplete."""

    syntax_renderers = syntax_renderer_double()
    controller = _controller(
        StateEditorDouble(text="(cat:1.05)", position=0),
        syntax_renderers=syntax_renderers,
    )

    controller.handle_hide()

    assert syntax_renderers.clear_transient_state_calls == 1


def _controller(
    editor: StateEditorDouble,
    *,
    document_service: PromptDocumentService | None = None,
    syntax_renderers: SyntaxRendererCoordinatorDouble | None = None,
) -> Any:
    """Build a prompt interaction controller for state-coordination tests."""

    return prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderers or syntax_renderer_double(),
        document_service=document_service or PromptDocumentService(),
        mutation_service=PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )
