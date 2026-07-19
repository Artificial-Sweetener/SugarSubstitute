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

"""Marshal generation feedback onto the Qt GUI thread before UI updates."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot

from substitute.application.generation import GenerationFailure, GenerationRunStarted
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import (
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.presentation.shell.generation_feedback_coalescer import (
    FeedbackFlushIntent,
    GenerationFeedbackBatch,
    GenerationFeedbackCoalescer,
    GenerationProgressRetirement,
    GenerationProgressRetirementReason,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    LivePreviewEvent,
)
from substitute.presentation.ui_load_activity import (
    default_prompt_projection_ui_load_activity,
)

_DEFAULT_FLUSH_INTERVAL_MS = 33


class GenerationFeedbackSink(Protocol):
    """Describe UI operations used by the generation feedback dispatcher."""

    def apply_generation_progress(self, update: ProgressUpdate) -> None:
        """Apply one progress update on the GUI thread."""

    def apply_generation_progress_state(self, state: ProgressViewState) -> None:
        """Apply one projected progress presentation state on the GUI thread."""

    def apply_generation_model_load_progress(
        self,
        update: ModelLoadProgressUpdate,
    ) -> None:
        """Apply one model-load progress update on the GUI thread."""

    def apply_generation_preview(self, update: LivePreviewEvent) -> None:
        """Apply one preview image update on the GUI thread."""

    def apply_generation_output_image(self, update: LiveFinalOutputEvent) -> None:
        """Apply one final output image update on the GUI thread."""

    def apply_generation_timing(self, update: GenerationExecutionTiming) -> None:
        """Apply one generation timing update on the GUI thread."""

    def apply_generation_failure(self, failure: GenerationFailure) -> None:
        """Apply one generation failure on the GUI thread."""

    def apply_generation_completed(self, event: ListenerCompleted) -> None:
        """Apply one generation completion on the GUI thread."""


class GenerationFeedbackDispatcher(QObject):
    """Marshal generation feedback onto the GUI thread and coalesce repaint work."""

    _progress_submitted = Signal(object)
    _model_load_progress_submitted = Signal(object)
    _preview_submitted = Signal(object)
    _output_image_submitted = Signal(object)
    _timing_submitted = Signal(object)
    _failure_submitted = Signal(object)
    _completed_submitted = Signal(object)
    _run_started_submitted = Signal(object)
    _progress_retirement_submitted = Signal(object)

    def __init__(
        self,
        *,
        sink: GenerationFeedbackSink,
        coalescer: GenerationFeedbackCoalescer | None = None,
        flush_interval_ms: int = _DEFAULT_FLUSH_INTERVAL_MS,
        prompt_interaction_active: Callable[[], bool] | None = None,
        prompt_interaction_elapsed_ms: Callable[[], float | None] | None = None,
        output_activity_marker: Callable[[str], None] | None = None,
        active_prompt_flush_interval_ms: int | None = None,
        idle_flush_interval_ms: int | None = None,
    ) -> None:
        """Create a GUI-thread dispatcher for generation feedback callbacks."""

        super().__init__()
        self._sink = sink
        self._coalescer = coalescer or GenerationFeedbackCoalescer()
        self._prompt_interaction_active = (
            prompt_interaction_active or _prompt_interaction_inactive
        )
        self._prompt_interaction_elapsed_ms = (
            prompt_interaction_elapsed_ms or _prompt_interaction_elapsed_unknown
        )
        self._output_activity_marker = (
            output_activity_marker or _default_output_activity_marker
        )
        self._idle_flush_interval_ms = max(
            1,
            int(
                flush_interval_ms
                if idle_flush_interval_ms is None
                else idle_flush_interval_ms
            ),
        )
        self._active_prompt_flush_interval_ms = max(
            1,
            int(
                self._idle_flush_interval_ms
                if active_prompt_flush_interval_ms is None
                else active_prompt_flush_interval_ms
            ),
        )
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(self._idle_flush_interval_ms)
        self._flush_timer.timeout.connect(self._flush_due)
        self._connect_queued_ingress()

    def on_progress(self, update: ProgressUpdate) -> None:
        """Queue one progress update for GUI-thread coalescing."""

        self._progress_submitted.emit(update)

    def on_run_started(self, event: GenerationRunStarted) -> None:
        """Queue active-run registration for GUI-thread coalescing."""

        self._run_started_submitted.emit(event)

    def on_model_load_progress(self, update: ModelLoadProgressUpdate) -> None:
        """Queue one model-load progress update for GUI-thread coalescing."""

        if QThread.currentThread() == self.thread():
            self._receive_model_load_progress(update)
            return
        self._model_load_progress_submitted.emit(update)

    def on_preview(self, update: PreviewImageUpdate) -> None:
        """Queue one preview update for GUI-thread coalescing."""

        self._preview_submitted.emit(update)

    def on_output_image(self, update: OutputImageUpdate) -> None:
        """Queue one output image update for GUI-thread delivery."""

        self._output_image_submitted.emit(update)

    def on_timing(self, update: GenerationExecutionTiming) -> None:
        """Queue one timing update for GUI-thread delivery."""

        self._timing_submitted.emit(update)

    def on_failure(self, failure: GenerationFailure) -> None:
        """Queue one generation failure for immediate GUI-thread delivery."""

        self._failure_submitted.emit(failure)

    def on_completed(self, event: ListenerCompleted) -> None:
        """Queue one generation completion for immediate GUI-thread delivery."""

        self._completed_submitted.emit(event)

    def retire_progress(
        self,
        *,
        reason: GenerationProgressRetirementReason,
        workflow_id: str | None = None,
        generation_run_id: str | None = None,
        prompt_id: str | None = None,
        client_id: str | None = None,
    ) -> None:
        """Retire progress on the GUI thread and publish hidden progress state."""

        retirement = GenerationProgressRetirement(
            reason=reason,
            workflow_id=workflow_id,
            generation_run_id=generation_run_id,
            prompt_id=prompt_id,
            client_id=client_id,
        )
        if QThread.currentThread() == self.thread():
            self._receive_progress_retirement(retirement)
            return
        self._progress_retirement_submitted.emit(retirement)

    def flush_now(self) -> None:
        """Immediately deliver every pending feedback update on the GUI thread."""

        self._flush_all()

    def _connect_queued_ingress(self) -> None:
        """Connect public callback ingress to private queued GUI-thread slots."""

        connection = Qt.ConnectionType.QueuedConnection
        self._progress_submitted.connect(self._receive_progress, connection)
        self._model_load_progress_submitted.connect(
            self._receive_model_load_progress,
            connection,
        )
        self._preview_submitted.connect(self._receive_preview, connection)
        self._output_image_submitted.connect(self._receive_output_image, connection)
        self._timing_submitted.connect(self._receive_timing, connection)
        self._failure_submitted.connect(self._receive_failure, connection)
        self._completed_submitted.connect(self._receive_completed, connection)
        self._run_started_submitted.connect(self._receive_run_started, connection)
        self._progress_retirement_submitted.connect(
            self._receive_progress_retirement,
            connection,
        )

    @Slot(object)
    def _receive_run_started(self, event: object) -> None:
        """Receive run-start registration on the GUI thread."""

        typed_event = cast(GenerationRunStarted, event)
        self._handle_intent(self._coalescer.submit_run_started(typed_event))

    @Slot(object)
    def _receive_progress(self, update: object) -> None:
        """Receive progress on the GUI thread and apply coalescing policy."""

        typed_update = cast(ProgressUpdate, update)
        self._handle_intent(self._coalescer.submit_progress(typed_update))

    @Slot(object)
    def _receive_model_load_progress(self, update: object) -> None:
        """Receive model-load progress on the GUI thread and coalesce it."""

        typed_update = cast(ModelLoadProgressUpdate, update)
        self._handle_intent(self._coalescer.submit_model_load_progress(typed_update))

    @Slot(object)
    def _receive_preview(self, update: object) -> None:
        """Receive preview feedback on the GUI thread and coalesce it."""

        typed_update = cast(PreviewImageUpdate, update)
        self._handle_intent(self._coalescer.submit_preview(typed_update))

    @Slot(object)
    def _receive_output_image(self, update: object) -> None:
        """Receive output image feedback on the GUI thread without dropping it."""

        typed_update = cast(OutputImageUpdate, update)
        intent = self._coalescer.submit_output_image(typed_update)
        self._handle_intent(intent)

    @Slot(object)
    def _receive_timing(self, update: object) -> None:
        """Receive timing feedback on the GUI thread without dropping it."""

        typed_update = cast(GenerationExecutionTiming, update)
        self._handle_intent(self._coalescer.submit_timing(typed_update))

    @Slot(object)
    def _receive_failure(self, failure: object) -> None:
        """Receive failure feedback on the GUI thread without delaying cleanup."""

        typed_failure = cast(GenerationFailure, failure)
        self._handle_intent(self._coalescer.submit_failure(typed_failure))

    @Slot(object)
    def _receive_completed(self, event: object) -> None:
        """Receive completion feedback on the GUI thread without delaying cleanup."""

        typed_event = cast(ListenerCompleted, event)
        self._handle_intent(self._coalescer.submit_completed(typed_event))

    @Slot(object)
    def _receive_progress_retirement(self, retirement: object) -> None:
        """Receive progress retirement on the GUI thread without deferral."""

        typed_retirement = cast(GenerationProgressRetirement, retirement)
        self._handle_intent(
            self._coalescer.retire_progress(
                reason=typed_retirement.reason,
                workflow_id=typed_retirement.workflow_id,
                generation_run_id=typed_retirement.generation_run_id,
                prompt_id=typed_retirement.prompt_id,
                client_id=typed_retirement.client_id,
            )
        )

    def _handle_intent(self, intent: FeedbackFlushIntent) -> None:
        """Apply the flush behavior requested by the coalescing policy."""

        if intent.flush_now:
            if self._should_defer_immediate_flush_for_prompt_interaction():
                self._schedule_flush()
                return
            self._flush_all()
            return
        self._schedule_flush()

    @Slot()
    def _flush_due(self) -> None:
        """Deliver normally scheduled feedback updates."""

        self._apply_batch(self._coalescer.drain_due())

    def _flush_all(self) -> None:
        """Deliver all pending feedback updates and stop any scheduled flush."""

        if self._flush_timer.isActive():
            self._flush_timer.stop()
        self._apply_batch(self._coalescer.drain_all())

    def _apply_batch(self, batch: GenerationFeedbackBatch) -> None:
        """Apply one coalesced batch to the GUI-thread sink."""

        if batch.is_empty():
            return
        for progress_state in batch.progress_states:
            self._sink.apply_generation_progress_state(progress_state)
        for progress_update in batch.progress_updates:
            self._sink.apply_generation_progress(progress_update)
        for model_load_update in batch.model_load_updates:
            self._sink.apply_generation_model_load_progress(model_load_update)
        for preview_update in batch.preview_updates:
            self._sink.apply_generation_preview(preview_update)
        for output_image_update in batch.output_image_updates:
            self._sink.apply_generation_output_image(output_image_update)
        for timing_update in batch.timing_updates:
            self._sink.apply_generation_timing(timing_update)
        for failure in batch.failures:
            self._sink.apply_generation_failure(failure)
        for completed_event in batch.completed_events:
            self._sink.apply_generation_completed(completed_event)
        self._output_activity_marker("generation_feedback_adaptive_flush")

    def _should_defer_immediate_flush_for_prompt_interaction(self) -> bool:
        """Return whether urgent repaint-only work should wait for a frame slot."""

        return (
            self._is_prompt_interaction_active()
            and not self._coalescer.has_terminal_or_durable_updates()
        )

    def _schedule_flush(self) -> None:
        """Start or tighten the flush timer for the current prompt interaction state."""

        interval_ms = self._current_flush_interval_ms()
        self._flush_timer.setInterval(interval_ms)
        if not self._flush_timer.isActive():
            self._flush_timer.start()
            return
        remaining_ms = self._flush_timer.remainingTime()
        if remaining_ms < 0 or remaining_ms <= interval_ms:
            return
        self._flush_timer.stop()
        self._flush_timer.start(interval_ms)

    def _current_flush_interval_ms(self) -> int:
        """Return the feedback interval appropriate for current prompt interaction."""

        if self._is_prompt_interaction_active():
            return self._active_prompt_flush_interval_ms
        return self._idle_flush_interval_ms

    def _is_prompt_interaction_active(self) -> bool:
        """Call the prompt activity predicate defensively for scheduler use."""

        return bool(self._prompt_interaction_active())


def _prompt_interaction_inactive() -> bool:
    """Return the default prompt-interaction inactive state."""

    return False


def _prompt_interaction_elapsed_unknown() -> float | None:
    """Return no elapsed prompt-interaction timing when no tracker is installed."""

    return None


def _default_output_activity_marker(reason: str) -> None:
    """Mark default presentation load after generation feedback reaches the UI."""

    default_prompt_projection_ui_load_activity().mark_output_activity(reason=reason)


def _format_elapsed_ms(elapsed_ms: float | None) -> str | None:
    """Format optional elapsed milliseconds for structured logs."""

    if elapsed_ms is None:
        return None
    return f"{elapsed_ms:.3f}"


def _batch_context(batch: GenerationFeedbackBatch) -> dict[str, object]:
    """Return profiler context for one coalesced feedback batch."""

    return {
        "progress_state_count": len(batch.progress_states),
        "progress_count": len(batch.progress_updates),
        "model_load_count": len(batch.model_load_updates),
        "preview_count": len(batch.preview_updates),
        "output_image_count": len(batch.output_image_updates),
        "timing_count": len(batch.timing_updates),
        "failure_count": len(batch.failures),
        "completed_count": len(batch.completed_events),
    }


def _progress_context(update: ProgressUpdate) -> dict[str, object]:
    """Return profiler context for one progress update."""

    return {
        "workflow_id": update.workflow_id,
        "generation_run_id": update.generation_run_id,
        "prompt_id": update.prompt_id,
        "workflow_percent": (
            "" if update.workflow_percent is None else update.workflow_percent
        ),
        "sampler_percent": (
            "" if update.sampler_percent is None else update.sampler_percent
        ),
    }


def _progress_state_context(state: ProgressViewState) -> dict[str, object]:
    """Return profiler context for one progress presentation state."""

    return {
        "active": state.active,
        "show_overlay": state.show_overlay,
        "workflow_value": state.workflow_value,
        "sampler_value": state.sampler_value,
        "workflow_id": state.workflow_id or "",
        "generation_run_id": state.generation_run_id or "",
        "prompt_id": state.prompt_id or "",
    }


def _model_load_context(update: ModelLoadProgressUpdate) -> dict[str, object]:
    """Return profiler context for one model-load progress update."""

    return {
        "workflow_id": update.workflow_id,
        "prompt_id": update.prompt_id or "",
        "node_id": update.node_id,
        "source_node_id": update.source_node_id or "",
        "source_cube_alias": update.source_cube_alias or "",
        "source_input_key": update.source_input_key or "",
        "phase": update.phase,
        "state": update.state,
        "percent": update.percent,
    }


def _preview_context(update: LivePreviewEvent) -> dict[str, object]:
    """Return profiler context for one preview image update."""

    return {
        "workflow_id": update.identity.workflow_id,
        "generation_run_id": update.identity.generation_run_id,
        "prompt_id": update.identity.prompt_id,
        "node_id": update.node_identity.resolved_node_id,
        "source_key": update.identity.source_key,
        "source_label": update.identity.source_label,
    }


def _output_image_context(update: LiveFinalOutputEvent) -> dict[str, object]:
    """Return profiler context for one final output image update."""

    return {
        "workflow_id": update.identity.workflow_id,
        "generation_run_id": update.identity.generation_run_id,
        "prompt_id": update.identity.prompt_id,
        "node_id": update.node_id,
        "source_key": update.identity.source_key,
        "source_label": update.identity.source_label,
        "list_index": update.position.list_index,
        "batch_index": update.position.batch_index,
        "file_path": str(update.file_path),
    }


def _timing_context(update: GenerationExecutionTiming) -> dict[str, object]:
    """Return profiler context for one generation timing update."""

    return {
        "workflow_id": update.workflow_id,
        "prompt_id": update.prompt_id,
        "job_duration_ms": update.job_duration_ms,
        "cube_timing_count": len(update.cube_timings),
    }


__all__ = [
    "GenerationFeedbackDispatcher",
    "GenerationFeedbackSink",
]
