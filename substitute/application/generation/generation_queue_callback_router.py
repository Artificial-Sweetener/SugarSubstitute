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

"""Route listener callbacks through the generation queue's state boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.application.generation.generation_job_output_store import (
    GenerationOutputUpdate,
)
from substitute.application.generation.generation_models import (
    GenerationCallbacks,
    GenerationFailure,
    GenerationRunStarted,
)
from substitute.application.ports.comfy_gateway import (
    GenerationExecutionTiming,
    ListenerCompleted,
    OutputImageUpdate,
    OutputVideoUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
    ModelLoadProgressUpdate,
)
from substitute.domain.generation import GenerationQueueJob


_ACTIVE_STATUSES = frozenset({"dispatching", "comfy_pending", "running"})


class GenerationQueueCallbackTarget(Protocol):
    """Expose the queue transitions required by listener callback routing."""

    _transition_scheduler: Callable[[Callable[[], None]], None]

    def _handle_generation_output(
        self, job_id: str, event: GenerationOutputUpdate
    ) -> None:
        """Record one accepted final output."""

    def _handle_generation_progress(self, job_id: str, event: ProgressUpdate) -> bool:
        """Record progress and report whether it is current."""

    def _handle_generation_timing(
        self, job_id: str, event: GenerationExecutionTiming
    ) -> None:
        """Record execution timing for a completed prompt."""

    def _replace_job(
        self,
        job_id: str,
        *,
        prompt_id: str | None = None,
        generation_run_id: str | None = None,
        client_id: str | None = None,
    ) -> None:
        """Update prompt identity for the active stage."""

    def _handle_generation_failure_profiled(
        self, job_id: str, failure: GenerationFailure, callbacks: GenerationCallbacks
    ) -> None:
        """Apply a failed prompt transition."""

    def _handle_generation_completed_profiled(
        self, job_id: str, event: ListenerCompleted, callbacks: GenerationCallbacks
    ) -> None:
        """Apply a completed run transition."""

    def _job_by_id(self, job_id: str) -> GenerationQueueJob | None:
        """Find a current queue job."""


def wrap_generation_queue_callbacks(
    target: GenerationQueueCallbackTarget,
    job_id: str,
    callbacks: GenerationCallbacks,
) -> GenerationCallbacks:
    """Schedule listener effects and gate stage advancement by queue state."""

    def on_output_image(event: OutputImageUpdate) -> None:
        """Forward an image after updating queue output state."""

        def handle_output() -> None:
            target._handle_generation_output(job_id, event)
            callbacks.on_output_image(event)

        target._transition_scheduler(handle_output)

    def on_output_video(event: OutputVideoUpdate) -> None:
        """Forward a video after updating queue output state."""

        def handle_output() -> None:
            target._handle_generation_output(job_id, event)
            callbacks.on_output_video(event)

        target._transition_scheduler(handle_output)

    def on_progress(event: ProgressUpdate) -> None:
        """Forward current prompt progress only."""

        def handle_progress() -> None:
            if target._handle_generation_progress(job_id, event):
                callbacks.on_progress(event)

        target._transition_scheduler(handle_progress)

    def on_timing(event: GenerationExecutionTiming) -> None:
        """Forward recorded execution timing."""

        def handle_timing() -> None:
            target._handle_generation_timing(job_id, event)
            callbacks.on_timing(event)

        target._transition_scheduler(handle_timing)

    def on_model_load_progress(event: ModelLoadProgressUpdate) -> None:
        """Forward model load progress on the queue owner thread."""

        target._transition_scheduler(lambda: callbacks.on_model_load_progress(event))

    def on_preview(event: PreviewImageUpdate) -> None:
        """Forward a preview on the queue owner thread."""

        target._transition_scheduler(lambda: callbacks.on_preview(event))

    def on_run_started(event: GenerationRunStarted) -> None:
        """Move the active queue job to its new prompt identity."""

        def handle_run_started() -> None:
            target._replace_job(
                job_id,
                prompt_id=event.prompt_id,
                generation_run_id=event.generation_run_id,
                client_id=event.client_id,
            )
            if callbacks.on_run_started is not None:
                callbacks.on_run_started(event)

        target._transition_scheduler(handle_run_started)

    def on_failure(failure: GenerationFailure) -> None:
        """Apply failure after other queued transitions."""

        target._transition_scheduler(
            lambda: target._handle_generation_failure_profiled(
                job_id, failure, callbacks
            )
        )

    def on_completed(event: ListenerCompleted) -> None:
        """Complete the user job after its final prompt."""

        target._transition_scheduler(
            lambda: target._handle_generation_completed_profiled(
                job_id, event, callbacks
            )
        )

    def request_stage_advance(advance: Callable[[], None]) -> None:
        """Advance only if cancellation has not made the queue job terminal."""

        def advance_active_job() -> None:
            job = target._job_by_id(job_id)
            if job is not None and job.status in _ACTIVE_STATUSES:
                advance()

        target._transition_scheduler(advance_active_job)

    return GenerationCallbacks(
        on_run_started=on_run_started,
        on_progress=on_progress,
        on_model_load_progress=on_model_load_progress,
        on_preview=on_preview,
        on_output_image=on_output_image,
        on_output_video=on_output_video,
        on_failure=on_failure,
        on_timing=on_timing,
        on_completed=on_completed,
        request_stage_advance=request_stage_advance,
    )


__all__ = ["GenerationQueueCallbackTarget", "wrap_generation_queue_callbacks"]
