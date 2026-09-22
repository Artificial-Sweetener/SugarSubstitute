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


def test_handle_text_changed_flushes_semantics_for_token_sensitive_edit() -> None:
    """Projection-classified token edits bypass ordinary typing debounce."""

    editor = build_editor("cat", position=3)
    editor.requires_immediate_semantic_refresh_result = True
    semantic_refresh = semantic_refresh_controller_double()
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh,
    )

    editor.setPlainText("cats")
    controller.handle_text_changed()

    assert semantic_refresh.queued_sources == [("cats", "text_changed")]
    assert semantic_refresh.flush_reasons == ["syntax_sensitive_edit"]


def test_semantic_boundary_flushes_only_after_syntax_sensitive_typing() -> None:
    """Plain typing avoids boundary work while possible syntax resolves once."""

    editor = build_editor("cat", position=3)
    semantic_refresh = semantic_refresh_controller_double()
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh,
    )

    editor.setPlainText("cats")
    controller.handle_text_changed()
    controller.flush_semantic_boundary_from_keymap(reason="plain_boundary")
    assert semantic_refresh.flush_reasons == []

    editor.requires_semantic_refresh_before_boundary_result = True
    editor.setPlainText("cats(")
    controller.handle_text_changed()
    controller.flush_semantic_boundary_from_keymap(reason="syntax_boundary")
    controller.flush_semantic_boundary_from_keymap(reason="duplicate_boundary")

    assert semantic_refresh.flush_reasons == ["syntax_boundary"]


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


def test_prepared_semantics_publish_without_a_second_document_build() -> None:
    """Canonical paste semantics should flow through refresh by exact identity."""

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
    editor = build_editor("cat", position=3)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller,
        document_service=document_service,
        syntax_profile=syntax_profile,
    )
    controller_holder.append(controller)
    build_calls.clear()
    source_text = "(cat:1.05), dog"

    prepared_state = controller._syntax_state.prepare_prompt_state(source_text)
    assert prepared_state is not None
    prepared_document, prepared_render_plan = prepared_state
    editor.setPlainText(source_text)
    controller.handle_text_changed()
    controller.flush_pending_semantic_refresh(reason="test")

    assert build_calls == [source_text]
    assert controller._syntax_state.document_view is prepared_document
    assert controller._syntax_state.render_plan is prepared_render_plan
    assert controller._syntax_state.pending_document_view is None
    assert controller._syntax_state.pending_render_plan is None


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
