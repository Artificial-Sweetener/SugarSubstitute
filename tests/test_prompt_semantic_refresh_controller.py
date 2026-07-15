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

"""Tests for prompt semantic refresh scheduling, identity, and observability."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptSyntaxProfile,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
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
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


class _FakeSemanticHost:
    """Provide semantic refresh host callbacks with explicit identity fields."""

    def __init__(self, *, source_text: str = "alpha") -> None:
        """Initialize current source and semantic identity state."""

        self.source_text = source_text
        self.document_source_text = source_text
        self.editor_session_id = "editor-session"
        self.source_revision = 1
        self.feature_profile_id = ("emphasis", "wildcard")
        self.scene_context_id: str | None = "scene-a"
        self.cube_context_id: str | None = "cube-a"
        self.applied_requests: list[PromptSemanticRefreshRequest] = []

    def current_semantic_source_text(self) -> str:
        """Return the current source text."""

        return self.source_text

    def current_semantic_document_source_text(self) -> str:
        """Return the source text represented by the cached semantic state."""

        return self.document_source_text

    def current_semantic_async_identity(
        self,
        *,
        request_id: int,
    ) -> PromptAsyncResultIdentity:
        """Return current identity for semantic stale-result checks."""

        return PromptAsyncResultIdentity(
            request_id=request_id,
            editor_session_id=self.editor_session_id,
            source_revision=self.source_revision,
            source_length=len(self.source_text),
            feature_profile_id=self.feature_profile_id,
            scene_context_id=self.scene_context_id,
            cube_context_id=self.cube_context_id,
        )

    def apply_fresh_semantic_refresh(
        self,
        request: PromptSemanticRefreshRequest,
    ) -> None:
        """Record applied semantic refresh requests."""

        self.applied_requests.append(request)
        self.document_source_text = request.source_text


class _FakeSemanticDebouncer:
    """Store the latest semantic refresh callback for deterministic delivery."""

    def __init__(self) -> None:
        """Initialize pending callback state."""

        self.pending_callback: Callable[[], None] | None = None
        self.request_reasons: list[str] = []
        self.cancel_reasons: list[str] = []

    @property
    def is_pending(self) -> bool:
        """Return whether a callback is waiting for delivery."""

        return self.pending_callback is not None

    def request(self, callback: Callable[[], None], *, reason: str) -> None:
        """Store the latest callback and reason."""

        self.pending_callback = callback
        self.request_reasons.append(reason)

    def flush(self, *, reason: str) -> bool:
        """Run the pending callback immediately."""

        _ = reason
        callback = self.pending_callback
        self.pending_callback = None
        if callback is None:
            return False
        callback()
        return True

    def cancel(self, *, reason: str) -> bool:
        """Cancel the pending callback."""

        self.cancel_reasons.append(reason)
        had_pending = self.pending_callback is not None
        self.pending_callback = None
        return had_pending

    def fire(self) -> None:
        """Deliver the queued callback."""

        assert self.flush(reason="test")


class _FakeSemanticTaskHandle(PromptEditorTaskHandle[PromptSemanticRefreshResult]):
    """Store one semantic async request until the test completes it."""

    def __init__(
        self,
        request: PromptAsyncRequest[PromptSemanticRefreshResult],
    ) -> None:
        """Initialize request and callback tracking."""

        self.request = request
        self.cancel_reasons: list[str] = []
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
        """Return whether this fake task has completed."""

        return self._outcome is not None

    @property
    def outcome(
        self,
    ) -> PromptAsyncTaskOutcome[PromptSemanticRefreshResult] | None:
        """Return the completed outcome when present."""

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
        """Record cancellation."""

        self.cancel_reasons.append(reason)

    def run_work(self) -> None:
        """Execute the request work and publish its result."""

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
        cancelled: bool = False,
    ) -> None:
        """Publish a fake async task outcome."""

        self._outcome = PromptAsyncTaskOutcome(
            identity=self.request.identity,
            context=self.request.context,
            result=result,
            error=error,
            cancelled=cancelled,
        )
        callbacks = tuple(self.callbacks)
        self.callbacks.clear()
        for callback in callbacks:
            callback(self._outcome)


class _Token:
    """Provide a never-cancelled token for semantic refresh tests."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class _FakeSemanticRequestChannel:
    """Mimic latest-wins cancellation generation for semantic tests."""

    def __init__(self) -> None:
        """Initialize active-handle and generation tracking."""

        self.handles: list[_FakeSemanticTaskHandle] = []
        self.cancel_reasons: list[str] = []
        self._generation = 0
        self._active_handle: _FakeSemanticTaskHandle | None = None

    def submit_latest(
        self,
        request: PromptAsyncRequest[PromptSemanticRefreshResult],
    ) -> _FakeSemanticTaskHandle:
        """Store the latest request and cancel the older active handle."""

        self._generation += 1
        request_with_generation = replace(
            request,
            identity=replace(
                request.identity,
                cancellation_generation=self._generation,
            ),
        )
        if self._active_handle is not None:
            self._active_handle.cancel(reason="superseded_by_latest_request")
        handle = _FakeSemanticTaskHandle(request_with_generation)
        self.handles.append(handle)
        self._active_handle = handle
        return handle

    def cancel_pending(self, *, reason: str) -> None:
        """Cancel the active request."""

        self.cancel_reasons.append(reason)
        if self._active_handle is not None:
            self._active_handle.cancel(reason=reason)
        self._active_handle = None


def test_semantic_refresh_coalesces_latest_request_identity_and_reason() -> None:
    """Queued source changes should submit only the latest semantic request."""

    host = _FakeSemanticHost(source_text="alpha")
    controller, debouncer, channel = _build_controller(host)
    host.source_text = "beta"
    host.source_revision = 2
    controller.queue_source_changed("beta", reason="first_edit")
    host.source_text = "gamma"
    host.source_revision = 3
    controller.queue_source_changed("gamma", reason="second_edit")

    debouncer.fire()
    channel.handles[0].run_work()

    assert len(channel.handles) == 1
    applied = host.applied_requests[-1]
    assert applied.source_text == "gamma"
    assert applied.reason == "second_edit"
    assert applied.coalesced_count == 1
    assert applied.identity.source_revision == 3
    assert applied.identity.feature_profile_id == ("emphasis", "wildcard")
    assert applied.identity.scene_context_id == "scene-a"
    assert applied.identity.cube_context_id == "cube-a"
    assert applied.identity.cancellation_generation == 1


def test_semantic_refresh_rejects_stale_source_revision_even_when_text_matches(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Freshness checks should reject stale source revisions before publication."""

    host = _FakeSemanticHost(source_text="beta")
    controller, debouncer, channel = _build_controller(host)
    caplog.set_level(logging.DEBUG)
    controller.queue_source_changed("beta", reason="edit")
    debouncer.fire()

    host.source_revision = 2
    channel.handles[0].run_work()

    assert host.applied_requests == []
    assert "prompt_semantic_refresh.dropped" in caplog.text
    assert "identity_mismatch" in caplog.text
    assert "source_revision" in caplog.text


def test_semantic_refresh_rejects_stale_scene_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scene context should participate in freshness when the host supplies it."""

    host = _FakeSemanticHost(source_text="beta")
    controller, debouncer, channel = _build_controller(host)
    caplog.set_level(logging.DEBUG)
    controller.queue_source_changed("beta", reason="scene_edit")
    debouncer.fire()

    host.scene_context_id = "scene-b"
    channel.handles[0].run_work()

    assert host.applied_requests == []
    assert "scene_context_id" in caplog.text
    assert "identity_mismatch" in caplog.text


def test_semantic_refresh_clears_active_task_after_success() -> None:
    """Successful current task completion should leave no active task."""

    host = _FakeSemanticHost(source_text="beta")
    controller, debouncer, channel = _build_controller(host)
    controller.queue_source_changed("beta", reason="edit")
    debouncer.fire()

    assert controller._active_task_count() == 1
    channel.handles[0].run_work()

    assert controller._active_task_count() == 0
    assert len(host.applied_requests) == 1


def test_semantic_refresh_failure_logs_prompt_safe_error_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Task failures should log type and timing without prompt text."""

    host = _FakeSemanticHost(source_text="secret prompt")
    document_service = PromptDocumentService()

    class _FailingSyntaxService:
        """Raise an exception whose message includes prompt text."""

        def build_render_plan(
            self,
            document_view: PromptDocumentView,
            syntax_profile: PromptSyntaxProfile,
        ) -> PromptSyntaxRenderPlan:
            """Reject render planning."""

            _ = document_view
            _ = syntax_profile
            message = f"{document_view.source_text} render failed"
            raise RuntimeError(message)

    controller, debouncer, channel = _build_controller(
        host,
        document_service=document_service,
        syntax_service=_FailingSyntaxService(),
    )
    controller.queue_source_changed("secret prompt", reason="edit")
    debouncer.fire()
    channel.handles[0].run_work()

    assert controller._active_task_count() == 0
    assert host.applied_requests == []
    assert "Prompt semantic refresh task failed" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "secret prompt" not in caplog.text


def test_semantic_refresh_request_context_includes_phase5_3_timing_fields() -> None:
    """Semantic refresh context should expose prompt-safe timing and identity."""

    host = _FakeSemanticHost(source_text="beta")
    controller, debouncer, channel = _build_controller(host)
    controller.queue_source_changed("beta", reason="edit")
    debouncer.fire()
    request = channel.handles[0].request
    safe_fields = dict(request.context.safe_fields)

    assert safe_fields["request_reason"] == "edit"
    assert safe_fields["source_length"] == len("beta")
    assert safe_fields["source_revision"] == 1
    assert safe_fields["feature_profile_id"] == ("emphasis", "wildcard")
    assert safe_fields["scene_context_id"] == "scene-a"
    assert safe_fields["cube_context_id"] == "cube-a"
    assert "queued_age_ms" in safe_fields
    assert "elapsed_ms" in safe_fields
    assert "duration_ms" in safe_fields


def _build_controller(
    host: _FakeSemanticHost,
    *,
    document_service: PromptDocumentService | None = None,
    syntax_service: Any | None = None,
) -> tuple[
    PromptSemanticRefreshController,
    _FakeSemanticDebouncer,
    _FakeSemanticRequestChannel,
]:
    """Build a semantic refresh controller with deterministic test seams."""

    debouncer = _FakeSemanticDebouncer()
    channel = _FakeSemanticRequestChannel()
    controller = PromptSemanticRefreshController(
        host=host,
        document_service=document_service or PromptDocumentService(),
        syntax_service=syntax_service
        or PromptSyntaxService(EmptyPromptWildcardCatalogGateway()),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        request_channel=channel,
        debouncer=debouncer,
        stale_result_guard=PromptStaleResultGuard(),
    )
    return controller, debouncer, channel
