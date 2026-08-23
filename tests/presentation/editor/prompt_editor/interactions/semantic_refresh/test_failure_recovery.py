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

"""Test semantic refresh failure retention and retry."""

from __future__ import annotations

from typing import Any

import pytest

from substitute.application.prompt_editor.document.service import PromptDocumentService
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.presentation.editor.prompt_editor.interactions.semantic_refresh.support import (
    build_editor,
    build_hosted_semantic_refresh_controller,
    build_interaction_controller,
    build_semantic_refresh_controller,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    syntax_renderer_double,
    syntax_service,
)


def test_interaction_controller_render_plan_failure_keeps_previous_prompt_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed render-plan refreshes do not mark the new source as applied."""

    document_service = PromptDocumentService()

    class FailingSyntaxService:
        """Fail once for the edited LoRA source while counting render requests."""

        def __init__(self) -> None:
            self._delegate = syntax_service()
            self.build_render_plan_calls = 0

        def build_render_plan(self, document_view: Any, syntax_profile: Any) -> Any:
            """Raise once for the LoRA source and delegate all other builds."""

            self.build_render_plan_calls += 1
            if document_view.source_text == "<lora:midna:1>":
                raise RuntimeError("render plan unavailable")
            return self._delegate.build_render_plan(document_view, syntax_profile)

    failing_syntax_service = FailingSyntaxService()
    syntax_renderers = syntax_renderer_double()
    semantic_refresh_controller = build_semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=failing_syntax_service,
        syntax_profile=prompt_syntax_profile("lora"),
    )
    editor = build_editor("alpha", position=0)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderers,
        document_service=document_service,
        syntax_service_=failing_syntax_service,
        syntax_profile=prompt_syntax_profile("lora"),
    )
    semantic_refresh_controller._host = controller._syntax_state
    initial_prompt_state_calls = len(syntax_renderers.prompt_state_calls)

    editor.setPlainText("<lora:midna:1>")
    controller.handle_text_changed()
    controller.flush_pending_semantic_refresh(reason="test")

    assert controller.document_view.source_text == "alpha"
    assert len(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls
    assert "Prompt syntax render-plan refresh failed" in caplog.text


def test_interaction_controller_retries_same_source_after_render_plan_failure() -> None:
    """The same source retries after a failed render-plan refresh."""

    document_service = PromptDocumentService()

    class FlakySyntaxService:
        """Fail once for the edited LoRA source and then recover."""

        def __init__(self) -> None:
            self._delegate = syntax_service()
            self.build_render_plan_calls = 0
            self.lora_source_calls = 0

        def build_render_plan(self, document_view: Any, syntax_profile: Any) -> Any:
            """Raise for the first LoRA source request, then delegate."""

            self.build_render_plan_calls += 1
            if document_view.source_text == "<lora:midna:1>":
                self.lora_source_calls += 1
                if self.lora_source_calls == 1:
                    raise RuntimeError("render plan unavailable")
            return self._delegate.build_render_plan(document_view, syntax_profile)

    flaky_syntax_service = FlakySyntaxService()
    syntax_renderers = syntax_renderer_double()
    semantic_refresh_controller = build_semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=flaky_syntax_service,
        syntax_profile=prompt_syntax_profile("lora"),
    )
    editor = build_editor("alpha", position=0)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderers,
        document_service=document_service,
        syntax_service_=flaky_syntax_service,
        syntax_profile=prompt_syntax_profile("lora"),
    )
    semantic_refresh_controller._host = controller._syntax_state
    initial_prompt_state_calls = len(syntax_renderers.prompt_state_calls)

    editor.setPlainText("<lora:midna:1>")
    controller.handle_text_changed()
    controller.flush_pending_semantic_refresh(reason="test")
    controller.handle_text_changed()
    controller.flush_pending_semantic_refresh(reason="test")

    assert flaky_syntax_service.lora_source_calls == 2
    assert controller.document_view.source_text == "<lora:midna:1>"
    assert len(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls + 1


def test_handle_text_changed_refreshes_syntax_renderers_from_rebuilt_document_view() -> (
    None
):
    """Text changes rebuild prompt state and push the refreshed render plan."""

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
    editor.setPlainText("(cat:1.05)")

    controller.handle_text_changed()
    controller.flush_pending_semantic_refresh(reason="test")

    refreshed_document_view = controller.document_view
    assert refreshed_document_view.source_text == "(cat:1.05)"
    snapshot = syntax_renderers.prompt_state_calls[-1]
    assert snapshot.document is refreshed_document_view
    assert snapshot.render_plan is controller.syntax_render_plan
    assert syntax_renderers.active_span_calls[-1] == (
        refreshed_document_view.syntax_spans[0],
        3,
    )
