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

"""Tests for prompt interaction semantic-refresh orchestration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptMutationService,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorTaskHandle,
    PromptSemanticRefreshController,
    PromptSemanticRefreshRequest,
    PromptSemanticRefreshResult,
    PromptStaleResultGuard,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_reorder_interaction_test_helpers import (
    ControllerEditorDouble,
    MenuCursorDouble,
    SyntaxRendererCoordinatorDouble,
    autocomplete_double,
    prompt_interaction_controller,
    semantic_refresh_controller_double,
    syntax_renderer_double,
    syntax_service,
)


class FakeSemanticDebouncer:
    """Store the latest semantic debounce callback for deterministic tests."""

    def __init__(self) -> None:
        """Initialize pending callback storage."""

        self.pending_callback: Callable[[], None] | None = None

    @property
    def is_pending(self) -> bool:
        """Return whether a semantic refresh callback is queued."""

        return self.pending_callback is not None

    def request(self, callback: Callable[[], None], *, reason: str) -> None:
        """Store the latest semantic refresh callback."""

        _ = reason
        self.pending_callback = callback

    def flush(self, *, reason: str) -> bool:
        """Run the latest callback immediately."""

        _ = reason
        callback = self.pending_callback
        self.pending_callback = None
        if callback is None:
            return False
        callback()
        return True

    def cancel(self, *, reason: str) -> bool:
        """Drop any queued semantic refresh callback."""

        _ = reason
        had_callback = self.pending_callback is not None
        self.pending_callback = None
        return had_callback

    def fire(self) -> None:
        """Deliver the queued callback when a test advances semantic debounce."""

        assert self.flush(reason="test")


class FakeSemanticTaskHandle(PromptEditorTaskHandle[PromptSemanticRefreshResult]):
    """Store one semantic async request until a test completes it."""

    def __init__(
        self,
        request: PromptAsyncRequest[PromptSemanticRefreshResult],
    ) -> None:
        """Store the request and callback list."""

        self.request = request
        self.cancel_calls: list[str] = []
        self.callbacks: list[
            Callable[[PromptAsyncTaskOutcome[PromptSemanticRefreshResult]], None]
        ] = []
        self._outcome: PromptAsyncTaskOutcome[PromptSemanticRefreshResult] | None = None

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self.request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether the fake task has completed."""

        return self._outcome is not None

    @property
    def outcome(
        self,
    ) -> PromptAsyncTaskOutcome[PromptSemanticRefreshResult] | None:
        """Return the completed outcome when available."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[PromptSemanticRefreshResult]], None],
        *,
        reason: str,
    ) -> None:
        """Record a completion callback."""

        _ = reason
        if self._outcome is not None:
            callback(self._outcome)
            return
        self.callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation without preventing explicit test completion."""

        self.cancel_calls.append(reason)

    def run_work(self) -> None:
        """Execute request work and publish one fake task outcome."""

        try:
            result = self.request.work(_Token())
        except BaseException as error:  # noqa: BLE001
            self.complete(error=error)
            return
        self.complete(result=result)

    def complete(
        self,
        *,
        result: PromptSemanticRefreshResult | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Publish a fake async task outcome to all callbacks."""

        self._outcome = PromptAsyncTaskOutcome(
            identity=self.request.identity,
            context=self.request.context,
            result=result,
            error=error,
        )
        callbacks = tuple(self.callbacks)
        self.callbacks.clear()
        for callback in callbacks:
            callback(self._outcome)


class _Token:
    """Provide a never-cancelled token for semantic interaction tests."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class FakeSemanticRequestChannel:
    """Record semantic async requests and return controllable fake handles."""

    def __init__(self) -> None:
        """Initialize request and cancellation tracking."""

        self.handles: list[FakeSemanticTaskHandle] = []
        self.cancel_reasons: list[str] = []

    def submit_latest(
        self,
        request: PromptAsyncRequest[PromptSemanticRefreshResult],
    ) -> FakeSemanticTaskHandle:
        """Store the latest semantic request for deterministic completion."""

        handle = FakeSemanticTaskHandle(request)
        self.handles.append(handle)
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Record request-channel cancellation."""

        self.cancel_reasons.append(reason)


class DeferredSemanticRefreshHost:
    """Delegate semantic refresh callbacks to a test controller after construction."""

    def __init__(self, controller_provider: Callable[[], Any]) -> None:
        """Store the provider used to resolve the constructed test controller."""

        self._controller_provider = controller_provider

    def current_semantic_source_text(self) -> str:
        """Return the editor source text that semantic refresh must match."""

        return cast(str, self._controller_provider().current_semantic_source_text())

    def current_semantic_document_source_text(self) -> str:
        """Return the source text represented by the current semantic snapshot."""

        return cast(
            str,
            self._controller_provider().current_semantic_document_source_text(),
        )

    def current_semantic_async_identity(
        self,
        *,
        request_id: int,
    ) -> PromptAsyncResultIdentity:
        """Return current editor identity for one semantic refresh request."""

        return cast(
            PromptAsyncResultIdentity,
            self._controller_provider().current_semantic_async_identity(
                request_id=request_id
            ),
        )

    def apply_fresh_semantic_refresh(
        self,
        request: PromptSemanticRefreshRequest,
    ) -> None:
        """Adopt one semantic request after freshness checks pass."""

        self._controller_provider().apply_fresh_semantic_refresh(request)


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
    semantic_refresh_controller = _semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=failing_syntax_service,
        syntax_profile=prompt_syntax_profile("lora"),
    )
    editor = _editor("alpha", position=0)
    controller = _controller(
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
    semantic_refresh_controller = _semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=flaky_syntax_service,
        syntax_profile=prompt_syntax_profile("lora"),
    )
    editor = _editor("alpha", position=0)
    controller = _controller(
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
    semantic_refresh_controller = _semantic_refresh_controller_for_test(
        controller_provider=lambda: controller_holder[0],
        document_service=document_service,
        syntax_profile=syntax_profile,
    )
    syntax_renderers = syntax_renderer_double()
    editor = _editor("cat", position=3)
    controller = _controller(
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
    assert syntax_renderers.prompt_state_calls[-1] == (
        refreshed_document_view,
        controller.syntax_render_plan,
    )
    assert syntax_renderers.active_span_calls[-1] == (
        refreshed_document_view.syntax_spans[0],
        3,
    )


def test_handle_text_changed_queues_semantic_refresh_until_flush() -> None:
    """Text changes leave semantic prompt state untouched until catch-up runs."""

    document_service = PromptDocumentService()
    syntax_profile = prompt_syntax_profile("emphasis", "wildcard")
    controller_holder: list[Any] = []
    semantic_refresh_controller = _semantic_refresh_controller_for_test(
        controller_provider=lambda: controller_holder[0],
        document_service=document_service,
        syntax_profile=syntax_profile,
    )
    syntax_renderers = syntax_renderer_double()
    editor = _editor("cat", position=3)
    controller = _controller(
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
    semantic_refresh_controller = _semantic_refresh_controller_for_test(
        controller_provider=lambda: controller_holder[0],
        document_service=document_service,
        syntax_profile=syntax_profile,
    )
    editor = _editor("alpha", position=5)
    controller = _controller(
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
    editor = _editor("alpha", position=5)
    controller = _controller(
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
    semantic_refresh_controller = _semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=syntax_service_,
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        request_channel=semantic_channel,
        debouncer=semantic_debouncer,
    )
    editor = _editor("alpha", position=5)
    controller = _controller(
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
    semantic_refresh_controller = _semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=failing_syntax_service,
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        request_channel=semantic_channel,
        debouncer=semantic_debouncer,
    )
    editor = _editor("alpha", position=5)
    controller = _controller(
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
    semantic_refresh_controller = _semantic_refresh_controller(
        document_service=document_service,
        syntax_service_=syntax_service(),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        request_channel=semantic_channel,
        debouncer=semantic_debouncer,
    )
    editor = _editor("alpha", position=5)
    controller = _controller(
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


def _semantic_refresh_controller_for_test(
    *,
    controller_provider: Callable[[], Any],
    document_service: Any,
    syntax_profile: Any,
) -> PromptSemanticRefreshController:
    """Build a real semantic refresh controller for coordinator behavior tests."""

    return PromptSemanticRefreshController(
        host=cast(Any, DeferredSemanticRefreshHost(controller_provider)),
        document_service=cast(Any, document_service),
        syntax_service=cast(Any, syntax_service()),
        syntax_profile=cast(Any, syntax_profile),
        request_channel=FakeSemanticRequestChannel(),
        debouncer=FakeSemanticDebouncer(),
        stale_result_guard=PromptStaleResultGuard(),
    )


def _semantic_refresh_controller(
    *,
    document_service: Any,
    syntax_service_: Any,
    syntax_profile: Any,
    request_channel: FakeSemanticRequestChannel | None = None,
    debouncer: FakeSemanticDebouncer | None = None,
) -> PromptSemanticRefreshController:
    """Build a semantic refresh controller with controllable async seams."""

    return PromptSemanticRefreshController(
        host=cast(Any, None),
        document_service=cast(Any, document_service),
        syntax_service=cast(Any, syntax_service_),
        syntax_profile=cast(Any, syntax_profile),
        request_channel=request_channel or FakeSemanticRequestChannel(),
        debouncer=debouncer or FakeSemanticDebouncer(),
        stale_result_guard=PromptStaleResultGuard(),
    )


def _controller(
    editor: ControllerEditorDouble,
    *,
    semantic_refresh_controller: object,
    syntax_renderers: SyntaxRendererCoordinatorDouble | None = None,
    document_service: object | None = None,
    syntax_service_: object | None = None,
    syntax_profile: object | None = None,
) -> Any:
    """Build a prompt interaction controller for semantic-refresh tests."""

    controller = prompt_interaction_controller(
        editor,
        autocomplete=autocomplete_double(),
        semantic_refresh_controller=semantic_refresh_controller,
        syntax_renderers=syntax_renderers or syntax_renderer_double(),
        document_service=cast(
            PromptDocumentService,
            document_service or PromptDocumentService(),
        ),
        mutation_service=PromptMutationService(),
        syntax_service_=cast(Any, syntax_service_ or syntax_service()),
        syntax_profile=cast(
            Any,
            syntax_profile or prompt_syntax_profile("emphasis", "wildcard"),
        ),
    )
    if hasattr(semantic_refresh_controller, "_host"):
        semantic_refresh_controller._host = controller._syntax_state
    return controller


def _editor(text: str, *, position: int) -> ControllerEditorDouble:
    """Return an editor double with matching click and caret cursors."""

    return ControllerEditorDouble(
        clicked_cursor=MenuCursorDouble(text=text, position=position),
        current_cursor=MenuCursorDouble(text=text, position=position),
        text=text,
    )
