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

"""End-to-end proof tests for the prompt-editor async execution boundary."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import cast

import pytest

from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncRequestContext,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorExecutor,
    PromptEditorCancellationToken,
    PromptEditorRequestChannel,
    PromptEditorTaskHandle,
    PromptLatestWinsRequestChannel,
    PromptStaleResultGuard,
    log_prompt_async_debug,
    log_prompt_async_warning,
    prompt_async_freshness_log_fields,
    prompt_async_outcome_log_fields,
)
from tests.execution_test_helpers import prompt_task_executor


def test_proof_adapter_submits_work_and_publishes_fresh_result() -> None:
    """A feature adapter should publish only after execution and freshness proof."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    current_identity = PromptAsyncResultIdentity(
        request_id=2,
        editor_session_id="session",
        source_revision=4,
        cancellation_generation=1,
    )
    adapter = _ProofAsyncFeatureAdapter(
        channel=PromptLatestWinsRequestChannel(
            executor=cast(PromptEditorExecutor, executor)
        ),
        current_identity=lambda: current_identity,
    )

    adapter.submit(
        request_id=1,
        source_revision=4,
        work=lambda _token: 7,
    )

    assert adapter.wait_for_completion()
    assert adapter.published_results == [7]
    assert adapter.completion_identities[0].cancellation_generation == 1
    assert dispatcher.reasons == [
        "execution_policy_completed",
        "proof_adapter_completion",
    ]
    executor.shutdown()


def test_proof_adapter_rejects_stale_result_before_publication() -> None:
    """The proof adapter should reject stale outcomes before visible publication."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    current_identity = _MutableIdentity(
        identity=PromptAsyncResultIdentity(
            request_id=2,
            editor_session_id="session",
            source_revision=4,
            cancellation_generation=1,
        )
    )
    adapter = _ProofAsyncFeatureAdapter(
        channel=PromptLatestWinsRequestChannel(
            executor=cast(PromptEditorExecutor, executor)
        ),
        current_identity=current_identity.current,
    )
    allow_work = Event()

    def work(_token: PromptEditorCancellationToken) -> int:
        """Wait until the test has moved current identity forward."""

        assert allow_work.wait(3.0)
        return 11

    adapter.submit(request_id=1, source_revision=4, work=work)
    current_identity.identity = PromptAsyncResultIdentity(
        request_id=3,
        editor_session_id="session",
        source_revision=5,
        cancellation_generation=1,
    )
    allow_work.set()

    assert adapter.wait_for_completion()
    assert adapter.published_results == []
    assert adapter.stale_drop_reasons == ["identity_mismatch"]
    assert adapter.stale_mismatch_fields == ["source_revision"]
    executor.shutdown()


def test_proof_adapter_latest_wins_cancels_superseded_work() -> None:
    """Latest-wins submission should prevent older outcomes from publishing."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    current_identity = _MutableIdentity(
        identity=PromptAsyncResultIdentity(
            request_id=3,
            editor_session_id="session",
            source_revision=2,
            cancellation_generation=1,
        )
    )
    channel: PromptLatestWinsRequestChannel[int] = PromptLatestWinsRequestChannel(
        executor=cast(PromptEditorExecutor, executor)
    )
    adapter = _ProofAsyncFeatureAdapter(
        channel=channel,
        current_identity=current_identity.current,
    )
    first_started = Event()
    release_first = Event()

    def first_work(_token: PromptEditorCancellationToken) -> int:
        """Block the first request so a later request can supersede it."""

        first_started.set()
        assert release_first.wait(3.0)
        return 1

    adapter.submit(request_id=1, source_revision=1, work=first_work)
    assert first_started.wait(3.0)

    current_identity.identity = PromptAsyncResultIdentity(
        request_id=3,
        editor_session_id="session",
        source_revision=2,
        cancellation_generation=2,
    )
    second_handle = adapter.submit(
        request_id=2,
        source_revision=2,
        work=lambda _token: 2,
    )
    release_first.set()

    assert adapter.wait_for_completion(expected_count=2)
    assert adapter.published_results == [2]
    assert adapter.cancelled_count == 1
    assert adapter.stale_drop_reasons == []
    assert channel.active_handle is None
    assert second_handle.identity.cancellation_generation == 2
    executor.shutdown()


def test_proof_adapter_cancel_pending_prevents_publication() -> None:
    """Explicit pending cancellation should clear active work without publication."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    channel: PromptLatestWinsRequestChannel[int] = PromptLatestWinsRequestChannel(
        executor=cast(PromptEditorExecutor, executor)
    )
    adapter = _ProofAsyncFeatureAdapter(
        channel=channel,
        current_identity=lambda: PromptAsyncResultIdentity(
            request_id=1,
            editor_session_id="session",
            source_revision=1,
            cancellation_generation=1,
        ),
    )
    blocker_started = Event()
    release_blocker = Event()
    queued_work_ran = False

    def blocking_work(_token: PromptEditorCancellationToken) -> int:
        """Occupy the single execution slot while the test queues cancellable work."""

        blocker_started.set()
        assert release_blocker.wait(3.0)
        return 1

    def queued_work(_token: PromptEditorCancellationToken) -> int:
        """Record whether pending cancellation failed to stop queued work."""

        nonlocal queued_work_ran
        queued_work_ran = True
        return 2

    blocking_handle = executor.submit(
        _request(request_id=100, source_revision=1, work=blocking_work),
        cancellation=_Token(),
    )
    blocking_done = Event()
    blocking_handle.add_done_callback(
        lambda _outcome: blocking_done.set(),
        reason="blocking_setup_finished",
    )
    assert blocker_started.wait(3.0)
    adapter.submit(request_id=1, source_revision=1, work=queued_work)

    channel.cancel_pending(reason="editor_closed")
    release_blocker.set()

    assert adapter.wait_for_completion()
    assert blocking_done.wait(3.0)
    assert adapter.published_results == []
    assert adapter.cancelled_count == 1
    assert queued_work_ran is False
    assert channel.active_handle is None
    executor.shutdown()


def test_proof_adapter_logs_failure_without_prompt_content(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Async failures should keep traceback context without logging prompt text."""

    dispatcher = _RecordingDispatcher()
    executor = prompt_task_executor(dispatcher=dispatcher)
    current_identity = PromptAsyncResultIdentity(
        request_id=1,
        editor_session_id="session",
        source_revision=1,
        source_length=31,
        cancellation_generation=1,
    )
    adapter = _ProofAsyncFeatureAdapter(
        channel=PromptLatestWinsRequestChannel(
            executor=cast(PromptEditorExecutor, executor)
        ),
        current_identity=lambda: current_identity,
    )
    caplog.set_level(logging.WARNING, logger=_LOGGER.name)

    def work(_token: PromptEditorCancellationToken) -> int:
        raise RuntimeError("prompt text should not leak")

    adapter.submit(request_id=1, source_revision=1, work=work, source_length=31)

    assert adapter.wait_for_completion()
    assert adapter.published_results == []
    assert adapter.failure_count == 1
    warning_records = [
        record for record in caplog.records if record.message.startswith("proof.failed")
    ]
    assert len(warning_records) == 1
    assert warning_records[0].exc_info is not None
    assert "error_type=RuntimeError" in warning_records[0].message
    assert "source_length=31" in warning_records[0].message
    assert "prompt text should not leak" not in warning_records[0].message
    executor.shutdown()


_LOGGER = logging.getLogger("tests.prompt_async_boundary_proof")


class _ProofAsyncFeatureAdapter:
    """Compose the async boundary the way a later feature owner should."""

    def __init__(
        self,
        *,
        channel: PromptEditorRequestChannel[int],
        current_identity: Callable[[], PromptAsyncResultIdentity],
    ) -> None:
        """Store protocol-shaped collaborators for proof submissions."""

        self._channel = channel
        self._current_identity = current_identity
        self._guard = PromptStaleResultGuard()
        self._completion_event = Event()
        self._completion_count = 0
        self.published_results: list[int] = []
        self.completion_identities: list[PromptAsyncResultIdentity] = []
        self.stale_drop_reasons: list[str] = []
        self.stale_mismatch_fields: list[str] = []
        self.cancelled_count = 0
        self.failure_count = 0

    def submit(
        self,
        *,
        request_id: int,
        source_revision: int,
        work: Callable[[PromptEditorCancellationToken], int],
        source_length: int = 0,
    ) -> PromptEditorTaskHandle[int]:
        """Submit one proof request through the latest-wins channel."""

        request = _request(
            request_id=request_id,
            source_revision=source_revision,
            work=work,
            source_length=source_length,
        )
        handle = self._channel.submit_latest(request)
        handle.add_done_callback(
            self._publish_if_current,
            reason="proof_adapter_completion",
        )
        return handle

    def wait_for_completion(self, *, expected_count: int = 1) -> bool:
        """Wait for the proof adapter to process the expected completions."""

        if self._completion_count >= expected_count:
            return True
        while self._completion_event.wait(3.0):
            if self._completion_count >= expected_count:
                return True
            self._completion_event.clear()
        return self._completion_count >= expected_count

    def _publish_if_current(self, outcome: PromptAsyncTaskOutcome[int]) -> None:
        """Validate completion freshness before publishing visible state."""

        self._completion_count += 1
        self.completion_identities.append(outcome.identity)
        try:
            if outcome.cancelled:
                self.cancelled_count += 1
                return
            if outcome.error is not None:
                self.failure_count += 1
                fields = prompt_async_outcome_log_fields(outcome)
                log_prompt_async_warning(
                    _LOGGER,
                    "proof.failed",
                    error=outcome.error,
                    **fields,
                )
                return

            decision = self._guard.validate(
                result_identity=outcome.identity,
                current_identity=self._current_identity(),
                required_fields=(
                    "editor_session_id",
                    "source_revision",
                    "cancellation_generation",
                ),
            )
            if not decision.is_fresh:
                self.stale_drop_reasons.append(decision.drop_reason)
                self.stale_mismatch_fields.extend(
                    mismatch.field_name for mismatch in decision.mismatches
                )
                log_prompt_async_debug(
                    _LOGGER,
                    "proof.stale",
                    **prompt_async_freshness_log_fields(decision),
                )
                return
            if outcome.result is not None:
                self.published_results.append(outcome.result)
        finally:
            self._completion_event.set()


def _request(
    *,
    request_id: int,
    source_revision: int,
    work: Callable[[PromptEditorCancellationToken], int],
    source_length: int = 0,
) -> PromptAsyncRequest[int]:
    """Create one proof request with publication identity and safe context."""

    return PromptAsyncRequest(
        identity=PromptAsyncResultIdentity(
            request_id=request_id,
            editor_session_id="session",
            source_revision=source_revision,
            source_length=source_length,
        ),
        context=PromptAsyncRequestContext(
            operation="proof_async_feature",
            reason="unit",
            safe_fields=(("source_length", source_length),),
        ),
        work=work,
    )


class _RecordingDispatcher:
    """Synchronously execute dispatcher publications while recording reasons."""

    def __init__(self) -> None:
        """Create an empty publication recorder."""

        self.reasons: list[str] = []

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Record one dispatcher publication and execute it immediately."""

        self.reasons.append(reason)
        callback()


@dataclass(slots=True)
class _MutableIdentity:
    """Provide a mutable current identity for stale-result proof tests."""

    identity: PromptAsyncResultIdentity

    def current(self) -> PromptAsyncResultIdentity:
        """Return the currently configured identity."""

        return self.identity


@dataclass(frozen=True, slots=True)
class _Token:
    """Provide the cancellation-token protocol for direct task-executor setup."""

    generation: int = 0
    is_cancelled: bool = False
    reason: str | None = None
