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

"""Test semantic refresh debounce and source freshness."""

from __future__ import annotations

from typing import Any


from substitute.application.prompt_editor.document.service import PromptDocumentService
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.presentation.editor.prompt_editor.interactions.semantic_refresh.support import (
    build_editor,
    build_hosted_semantic_refresh_controller,
    build_interaction_controller,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    semantic_refresh_controller_double,
    syntax_renderer_double,
)


def test_handle_text_changed_queues_semantic_refresh_until_flush() -> None:
    """Text changes leave semantic prompt state untouched until catch-up runs."""

    document_service = PromptDocumentService()
    syntax_profile = prompt_syntax_profile("emphasis", "wildcard")
    controller_holder: list[Any] = []
    semantic_refresh_controller = build_hosted_semantic_refresh_controller(
        controller_provider=lambda: controller_holder[0],
        document_service=document_service,
        syntax_profile=syntax_profile,
    )
    syntax_renderers = syntax_renderer_double()
    editor = build_editor("cat", position=3)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderers,
        document_service=document_service,
        syntax_profile=syntax_profile,
    )
    controller_holder.append(controller)
    initial_prompt_state_calls = len(syntax_renderers.prompt_state_calls)

    editor.setPlainText("(cat:1.05)")
    controller.handle_text_changed()

    assert controller.document_view.source_text == "cat"
    assert len(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls

    controller.flush_pending_semantic_refresh(reason="test")

    assert controller.document_view.source_text == "(cat:1.05)"
    assert len(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls + 1


def test_handle_text_changed_coalesces_semantic_refresh_to_latest_text() -> None:
    """Queued semantic refresh builds only the latest pending source."""

    real_document_service = PromptDocumentService()
    build_calls: list[str] = []

    class CountingDocumentService:
        """Count document-view builds while delegating to the real service."""

        def build_document_view(self, text: str) -> Any:
            """Build one document view and record the requested text."""

            build_calls.append(text)
            return real_document_service.build_document_view(text)

    document_service = CountingDocumentService()
    syntax_profile = prompt_syntax_profile("emphasis", "wildcard")
    controller_holder: list[Any] = []
    semantic_refresh_controller = build_hosted_semantic_refresh_controller(
        controller_provider=lambda: controller_holder[0],
        document_service=document_service,
        syntax_profile=syntax_profile,
    )
    editor = build_editor("alpha", position=5)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller,
        document_service=document_service,
        syntax_profile=syntax_profile,
    )
    controller_holder.append(controller)
    build_calls.clear()

    editor.setPlainText("beta")
    controller.handle_text_changed()
    editor.setPlainText("gamma")
    controller.handle_text_changed()

    assert controller.document_view.source_text == "alpha"

    controller.flush_pending_semantic_refresh(reason="test")

    assert build_calls == ["gamma"]
    assert controller.document_view.source_text == "gamma"


def test_pending_semantic_refresh_drops_stale_text_snapshot() -> None:
    """A queued semantic refresh does not apply after the editor text changes."""

    document_service = PromptDocumentService()
    syntax_renderers = syntax_renderer_double()
    editor = build_editor("alpha", position=5)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller_double(),
        syntax_renderers=syntax_renderers,
        document_service=document_service,
    )
    initial_prompt_state_calls = len(syntax_renderers.prompt_state_calls)

    editor.setPlainText("beta")
    controller.handle_text_changed()
    editor.setPlainText("gamma")

    controller.flush_pending_semantic_refresh(reason="test")

    assert controller.document_view.source_text == "alpha"
    assert len(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls
