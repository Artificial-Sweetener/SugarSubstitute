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

"""Test semantic refresh background task publication."""

from __future__ import annotations

from typing import Any

import pytest

from substitute.application.prompt_editor.document.service import PromptDocumentService
from tests.support.prompt_editor.autocomplete_support import prompt_syntax_profile
from tests.presentation.editor.prompt_editor.interactions.semantic_refresh.debouncer import (
    FakeSemanticDebouncer,
)
from tests.presentation.editor.prompt_editor.interactions.semantic_refresh.task_channel import (
    FakeSemanticRequestChannel,
)
from tests.presentation.editor.prompt_editor.interactions.semantic_refresh.support import (
    build_editor,
    build_interaction_controller,
    build_semantic_refresh_controller,
)
from tests.presentation.editor.prompt_editor.interactions.support.collaborators import (
    syntax_renderer_double,
    syntax_service,
)


def test_scheduled_semantic_refresh_builds_document_view_in_background_task() -> None:
    """Scheduled catch-up moves semantic snapshot builds out of the timer."""

    real_document_service = PromptDocumentService()
    build_calls: list[str] = []
    render_plan_calls: list[str] = []

    class CountingDocumentService:
        """Count document-view builds while delegating to the real service."""

        def build_document_view(self, text: str) -> Any:
            """Build one document view and record the requested text."""

            build_calls.append(text)
            return real_document_service.build_document_view(text)

    class CountingSyntaxService:
        """Count render-plan builds while delegating to the real service."""

        def __init__(self) -> None:
            """Initialize the delegate used for real render-plan construction."""

            self._delegate = syntax_service()

        def build_render_plan(self, document_view: Any, syntax_profile: Any) -> Any:
            """Build one render plan and record the source text."""

            render_plan_calls.append(document_view.source_text)
            return self._delegate.build_render_plan(document_view, syntax_profile)

    semantic_debouncer = FakeSemanticDebouncer()
    semantic_channel = FakeSemanticRequestChannel()
    syntax_renderers = syntax_renderer_double()
    syntax_service_ = CountingSyntaxService()
    document_service = CountingDocumentService()
    semantic_refresh_controller = build_semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=syntax_service_,
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        request_channel=semantic_channel,
        debouncer=semantic_debouncer,
    )
    editor = build_editor("alpha", position=5)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderers,
        document_service=document_service,
        syntax_service_=syntax_service_,
    )
    semantic_refresh_controller._host = controller._syntax_state
    build_calls.clear()
    render_plan_calls.clear()
    initial_prompt_state_calls = len(syntax_renderers.prompt_state_calls)

    editor.setPlainText("beta")
    controller.handle_text_changed()
    semantic_debouncer.fire()

    assert build_calls == []
    assert render_plan_calls == []
    assert semantic_channel.handles
    assert controller.document_view.source_text == "alpha"

    semantic_channel.handles[0].run_work()

    assert build_calls == ["beta"]
    assert render_plan_calls == ["beta"]
    assert controller.document_view.source_text == "beta"
    assert len(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls + 1


def test_scheduled_semantic_refresh_logs_task_render_plan_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Task render-plan failures are logged without applying stale state."""

    document_service = PromptDocumentService()

    class FailingSyntaxService:
        """Raise for background render-plan builds."""

        def build_render_plan(self, document_view: Any, syntax_profile: Any) -> Any:
            """Reject the edited source during scheduled semantic catch-up."""

            if document_view.source_text == "beta":
                raise RuntimeError("render plan unavailable")
            return syntax_service().build_render_plan(document_view, syntax_profile)

    semantic_debouncer = FakeSemanticDebouncer()
    semantic_channel = FakeSemanticRequestChannel()
    syntax_renderers = syntax_renderer_double()
    failing_syntax_service = FailingSyntaxService()
    semantic_refresh_controller = build_semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=failing_syntax_service,
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        request_channel=semantic_channel,
        debouncer=semantic_debouncer,
    )
    editor = build_editor("alpha", position=5)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderers,
        document_service=document_service,
        syntax_service_=failing_syntax_service,
    )
    semantic_refresh_controller._host = controller._syntax_state
    initial_prompt_state_calls = len(syntax_renderers.prompt_state_calls)

    editor.setPlainText("beta")
    controller.handle_text_changed()
    semantic_debouncer.fire()
    semantic_channel.handles[0].run_work()

    assert controller.document_view.source_text == "alpha"
    assert len(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls
    assert "Prompt semantic refresh task failed" in caplog.text


def test_scheduled_semantic_refresh_drops_stale_task_result() -> None:
    """Background semantic results are ignored after newer source changes."""

    document_service = PromptDocumentService()
    semantic_debouncer = FakeSemanticDebouncer()
    semantic_channel = FakeSemanticRequestChannel()
    syntax_renderers = syntax_renderer_double()
    semantic_refresh_controller = build_semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        request_channel=semantic_channel,
        debouncer=semantic_debouncer,
    )
    editor = build_editor("alpha", position=5)
    controller = build_interaction_controller(
        editor,
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderers,
        document_service=document_service,
    )
    semantic_refresh_controller._host = controller._syntax_state
    initial_prompt_state_calls = len(syntax_renderers.prompt_state_calls)

    editor.setPlainText("beta")
    controller.handle_text_changed()
    semantic_debouncer.fire()
    assert len(semantic_channel.handles) == 1

    editor.setPlainText("gamma")
    controller.handle_text_changed()
    semantic_debouncer.fire()
    assert len(semantic_channel.handles) == 2

    semantic_channel.handles[0].run_work()

    assert controller.document_view.source_text == "alpha"
    assert len(syntax_renderers.prompt_state_calls) == initial_prompt_state_calls

    assert len(semantic_channel.handles) == 2
    semantic_channel.handles[1].run_work()

    assert controller.document_view.source_text == "gamma"
