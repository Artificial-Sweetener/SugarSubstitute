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

"""Build focused syntax-action interaction scenarios."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import Qt

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.editing.mutation_service import (
    PromptMutation,
    PromptMutationService,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    SyntaxRendererCoordinatorDouble,
    autocomplete_double,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)
from tests.presentation.editor.prompt_editor.interactions.support.controller import (
    prompt_interaction_controller,
)
from tests.presentation.editor.prompt_editor.interactions.support.editor import (
    MenuCursorDouble,
)
from tests.presentation.editor.prompt_editor.interactions.syntax_actions.editor_double import (
    SyntaxActionEditorDouble,
)
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile


def build_controller(
    editor: SyntaxActionEditorDouble,
    *,
    autocomplete: object | None = None,
    document_service: PromptDocumentService | None = None,
    mutation_service: PromptMutationService | None = None,
    syntax_renderers: SyntaxRendererCoordinatorDouble | None = None,
) -> Any:
    """Build a prompt interaction controller for one syntax-action scenario."""

    return prompt_interaction_controller(
        editor,
        autocomplete=autocomplete or autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderers or syntax_renderer_double(),
        document_service=document_service or PromptDocumentService(),
        mutation_service=mutation_service or PromptMutationService(),
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )


def build_editor(
    text: str, *, position: int, anchor: int | None = None
) -> SyntaxActionEditorDouble:
    """Return a syntax-action editor double with matching click and caret cursors."""

    return SyntaxActionEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=position, anchor=anchor),
        current_cursor=MenuCursorDouble(text=text, position=position, anchor=anchor),
        text=text,
    )


def build_mutation(
    document_service: PromptDocumentService,
    text: str,
    selection_start: int,
    selection_end: int,
) -> PromptMutation:
    """Return a mutation carrying a document view for the supplied text."""

    return PromptMutation(
        text=text,
        selection_start=selection_start,
        selection_end=selection_end,
        document_view=document_service.build_document_view(text),
    )


def autocomplete_with_clear_calls(clear_calls: list[str]) -> SimpleNamespace:
    """Return an autocomplete double that records clear requests."""

    return SimpleNamespace(
        handle_key_press=lambda _event: False,
        refresh_for_query=lambda _query, **_kwargs: None,
        dismiss_autocomplete=lambda _reason: clear_calls.append("clear"),
        refresh_geometry=lambda: None,
    )


def record_applied_mutations(
    applied_mutations: list[tuple[PromptMutation, bool]],
) -> object:
    """Return an `_apply_mutation` replacement that records direct applications."""

    def apply_mutation_double(
        result: PromptMutation,
        *,
        block_signals: bool = False,
        render_plan: object | None = None,
    ) -> None:
        _ = render_plan
        applied_mutations.append((result, block_signals))

    return apply_mutation_double


def key_event(
    key: int,
    *,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    text: str = "",
) -> SimpleNamespace:
    """Return the minimal key-event shape consumed by controller tests."""

    return SimpleNamespace(
        key=lambda: key,
        modifiers=lambda: modifiers,
        text=lambda: text,
    )
