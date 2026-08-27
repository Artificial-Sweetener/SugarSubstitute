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

"""Test generation progress lifecycle coalescing."""

from __future__ import annotations


from substitute.application.generation import GenerationRunStarted
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import (
    ListenerCompleted,
)
from substitute.presentation.shell.generation_feedback_coalescer import (
    GenerationFeedbackCoalescer,
)


from tests.presentation.shell.generation_feedback.coalescer_support import (
    _progress_update,
    _run_started,
)


def test_progress_latest_value_wins_before_flush() -> None:
    """Progress coalescing should deliver only the newest pending value."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_progress(
        _progress_update(workflow_percent=10.0, sampler_percent=1.0)
    )
    coalescer.submit_progress(
        _progress_update(workflow_percent=20.0, sampler_percent=2.0)
    )

    batch = coalescer.drain_due()

    assert batch.progress_updates == (
        _progress_update(workflow_percent=20.0, sampler_percent=2.0),
    )


def test_progress_latest_value_wins_per_workflow_before_flush() -> None:
    """Progress coalescing should retain newest progress for each workflow."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started(workflow_id="wf-a"))
    coalescer.submit_run_started(_run_started(workflow_id="wf-b"))

    coalescer.submit_progress(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=10.0,
            sampler_percent=1.0,
        )
    )
    coalescer.submit_progress(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        )
    )
    coalescer.submit_progress(
        _progress_update(
            workflow_id="wf-b",
            workflow_percent=70.0,
            sampler_percent=7.0,
        )
    )

    assert coalescer.drain_due().progress_updates == (
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=20.0,
            sampler_percent=2.0,
        ),
        _progress_update(
            workflow_id="wf-b",
            workflow_percent=70.0,
            sampler_percent=7.0,
        ),
    )


def test_starting_other_workflow_does_not_retire_current_progress() -> None:
    """Run registration for wf-b must not emit hidden progress for wf-a."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started(workflow_id="wf-a"))
    coalescer.submit_progress(
        _progress_update(
            workflow_id="wf-a",
            workflow_percent=10.0,
            sampler_percent=1.0,
        )
    )
    coalescer.drain_all()

    intent = coalescer.submit_run_started(_run_started(workflow_id="wf-b"))

    assert intent.flush_now is False
    assert coalescer.drain_all().progress_states == ()


def test_progress_without_active_lifecycle_is_ignored() -> None:
    """Progress cannot become visible without an active generation lifecycle."""

    coalescer = GenerationFeedbackCoalescer()

    coalescer.submit_progress(
        _progress_update(workflow_percent=20.0, sampler_percent=2.0)
    )

    assert coalescer.drain_due().progress_updates == ()


def test_progress_completion_forces_immediate_flush() -> None:
    """Progress completion should request immediate GUI delivery."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    intent = coalescer.submit_progress(
        _progress_update(workflow_percent=100.0, sampler_percent=None)
    )

    assert intent.flush_now is True


def test_progress_sampler_start_forces_immediate_flush() -> None:
    """Sampler start should flush promptly so model-load overlays clear."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_progress(
        _progress_update(workflow_percent=0.0, sampler_percent=0.0)
    )

    intent = coalescer.submit_progress(
        _progress_update(workflow_percent=5.0, sampler_percent=0.5)
    )

    assert intent.flush_now is True


def test_retire_progress_drops_pending_progress_and_emits_hidden_state() -> None:
    """Explicit retirement should clear stale pending progress and hide surfaces."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_progress(
        _progress_update(workflow_percent=43.0, sampler_percent=9.0)
    )

    coalescer.retire_progress(reason="stopped")
    batch = coalescer.drain_all()

    assert batch.progress_updates == ()
    assert batch.progress_states == (
        ProgressViewState.hidden(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )


def test_late_progress_after_retire_is_ignored() -> None:
    """Progress from a retired lifecycle should not reopen the overlay."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.retire_progress(reason="stopped")
    coalescer.drain_all()

    coalescer.submit_progress(
        _progress_update(workflow_percent=43.0, sampler_percent=9.0)
    )

    assert coalescer.drain_due().progress_updates == ()


def test_progress_for_old_lifecycle_is_ignored_after_replacement() -> None:
    """A newer run for the workflow should make the previous run's progress stale."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_run_started(
        GenerationRunStarted(
            workflow_id="wf",
            generation_run_id="run-2",
            output_session_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    coalescer.drain_all()

    coalescer.submit_progress(
        _progress_update(workflow_percent=40.0, sampler_percent=4.0)
    )
    coalescer.submit_progress(
        _progress_update(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
            workflow_percent=50.0,
            sampler_percent=5.0,
        )
    )

    assert coalescer.drain_due().progress_updates == (
        _progress_update(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
            workflow_percent=50.0,
            sampler_percent=5.0,
        ),
    )


def test_old_lifecycle_retirement_does_not_hide_new_active_progress() -> None:
    """A stale explicit retirement should not clear a newer active run."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_run_started(
        _run_started(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    coalescer.drain_all()

    coalescer.retire_progress(
        reason="completed",
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
    )
    current_progress = _progress_update(
        generation_run_id="run-2",
        prompt_id="pid-2",
        client_id="client-2",
        workflow_percent=50.0,
        sampler_percent=5.0,
    )
    coalescer.submit_progress(current_progress)

    batch = coalescer.drain_all()

    assert batch.progress_states == ()
    assert batch.progress_updates == (current_progress,)


def test_stale_completion_does_not_retire_newer_lifecycle() -> None:
    """Completion from run A should not hide or complete run B."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_run_started(
        _run_started(
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    coalescer.drain_all()

    coalescer.submit_completed(
        ListenerCompleted(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        )
    )
    current_progress = _progress_update(
        generation_run_id="run-2",
        prompt_id="pid-2",
        client_id="client-2",
        workflow_percent=55.0,
        sampler_percent=6.0,
    )
    coalescer.submit_progress(current_progress)

    batch = coalescer.drain_all()

    assert batch.completed_events == ()
    assert batch.progress_states == ()
    assert batch.progress_updates == (current_progress,)


def test_scene_lifecycle_progress_is_keyed_by_generation_run() -> None:
    """Scene jobs sharing a workflow id should reject prior scene-run progress."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started(generation_run_id="scene-a"))
    coalescer.submit_run_started(
        _run_started(
            generation_run_id="scene-b",
            prompt_id="pid-b",
            client_id="client-b",
        )
    )
    coalescer.drain_all()

    coalescer.submit_progress(
        _progress_update(
            generation_run_id="scene-a",
            prompt_id="pid-1",
            client_id="client-1",
            workflow_percent=40.0,
            sampler_percent=4.0,
        )
    )
    scene_b_progress = _progress_update(
        generation_run_id="scene-b",
        prompt_id="pid-b",
        client_id="client-b",
        workflow_percent=60.0,
        sampler_percent=7.0,
    )
    coalescer.submit_progress(scene_b_progress)

    assert coalescer.drain_due().progress_updates == (scene_b_progress,)
