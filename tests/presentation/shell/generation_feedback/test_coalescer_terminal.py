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

"""Test terminal generation feedback delivery and cleanup."""

from __future__ import annotations


from substitute.application.generation import GenerationFailure, GenerationRunStarted
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCompleted,
    PreviewImageUpdate,
)
from substitute.presentation.shell.generation_feedback_coalescer import (
    GenerationFeedbackCoalescer,
)


from tests.presentation.shell.generation_feedback.coalescer_support import (
    _live_preview,
    _preview_update,
    _progress_update,
    _run_started,
)


def test_failures_are_not_coalesced() -> None:
    """Failure updates should remain lossless and ordered."""

    coalescer = GenerationFeedbackCoalescer()
    first = GenerationFailure(stage="queue", workflow_id="wf", message="first")
    second = GenerationFailure(stage="listen", workflow_id="wf", message="second")

    coalescer.submit_failure(first)
    coalescer.submit_failure(second)

    assert coalescer.drain_all().failures == (first, second)


def test_completions_are_not_coalesced() -> None:
    """Completion updates should remain lossless and ordered."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_run_started(
        GenerationRunStarted(
            workflow_id="wf-2",
            generation_run_id="run-2",
            output_session_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    first = ListenerCompleted(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )
    second = ListenerCompleted(
        workflow_id="wf-2",
        generation_run_id="run-2",
        prompt_id="pid-2",
    )

    coalescer.submit_completed(first)
    coalescer.submit_completed(second)

    assert coalescer.drain_all().completed_events == (first, second)


def test_timing_updates_are_not_coalesced_and_flush_immediately() -> None:
    """Timing updates should remain lossless durable metadata updates."""

    coalescer = GenerationFeedbackCoalescer()
    first = GenerationExecutionTiming(
        workflow_id="wf",
        prompt_id="pid-1",
        job_duration_ms=850.0,
    )
    second = GenerationExecutionTiming(
        workflow_id="wf",
        prompt_id="pid-2",
        job_duration_ms=1200.0,
    )

    first_intent = coalescer.submit_timing(first)
    second_intent = coalescer.submit_timing(second)

    assert first_intent.flush_now is True
    assert second_intent.flush_now is True
    assert coalescer.pending_counts().timing_count == 2
    assert coalescer.has_terminal_or_durable_updates() is True
    assert coalescer.drain_all().timing_updates == (first, second)


def test_failure_discards_stale_preview_for_failed_workflow() -> None:
    """Failure cleanup should not render stale pending previews first."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    failed_preview = PreviewImageUpdate(
        workflow_id="wf",
        image="failed",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        node_id="N1",
        source_key="wf:N1",
        source_label="Cube",
    )
    coalescer.submit_run_started(
        GenerationRunStarted(
            workflow_id="other",
            generation_run_id="other-run",
            output_session_id="other-run",
            prompt_id="other-pid",
            client_id="other-client",
        )
    )
    other_preview = PreviewImageUpdate(
        workflow_id="other",
        image="other",
        generation_run_id="other-run",
        prompt_id="other-pid",
        client_id="other-client",
        node_id="N1",
        source_key="other:N1",
        source_label="Cube",
    )
    failure = GenerationFailure(
        stage="listen",
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        message="failed",
    )

    coalescer.submit_preview(failed_preview)
    coalescer.submit_preview(other_preview)
    coalescer.submit_failure(failure)

    batch = coalescer.drain_all()

    assert batch.preview_updates == (_live_preview(other_preview),)
    assert batch.failures == (failure,)


def test_completion_forces_terminal_progress_and_discards_stale_preview() -> None:
    """Completion should flush terminal progress without rendering stale previews."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    preview = _preview_update(image="old")
    completed = ListenerCompleted(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )

    coalescer.submit_preview(preview)
    coalescer.submit_completed(completed)

    batch = coalescer.drain_all()

    assert batch.progress_updates == ()
    assert batch.progress_states == (
        ProgressViewState.hidden(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )
    assert batch.preview_updates == ()
    assert batch.completed_events == (completed,)


def test_failure_retires_matching_lifecycle() -> None:
    """Failure should hide matching active progress and preserve the failure event."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    failure = GenerationFailure(
        stage="listen",
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        message="failed",
    )

    coalescer.submit_progress(
        _progress_update(workflow_percent=43.0, sampler_percent=9.0)
    )
    coalescer.submit_failure(failure)

    batch = coalescer.drain_all()

    assert batch.progress_updates == ()
    assert batch.progress_states == (
        ProgressViewState.hidden(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )
    assert batch.failures == (failure,)
