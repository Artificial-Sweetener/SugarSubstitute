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

"""Qt dispatcher tests for generation feedback UI delivery."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import cast

from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtWidgets import QApplication

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
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    LivePreviewEvent,
)
from substitute.presentation.shell.generation_feedback_dispatcher import (
    GenerationFeedbackDispatcher,
)


class _Sink:
    """Record dispatcher sink calls for assertions."""

    def __init__(self) -> None:
        """Initialize empty call records."""

        self.progress: list[ProgressUpdate] = []
        self.progress_states: list[ProgressViewState] = []
        self.model_load: list[ModelLoadProgressUpdate] = []
        self.previews: list[LivePreviewEvent] = []
        self.outputs: list[LiveFinalOutputEvent] = []
        self.timing: list[GenerationExecutionTiming] = []
        self.failures: list[GenerationFailure] = []
        self.completed: list[ListenerCompleted] = []
        self.events: list[str] = []
        self.thread_ids: list[int] = []

    def apply_generation_progress(self, update: ProgressUpdate) -> None:
        """Record one progress update."""

        self.progress.append(update)
        self.events.append("progress")
        self.thread_ids.append(threading.get_ident())

    def apply_generation_progress_state(self, state: ProgressViewState) -> None:
        """Record one projected progress state."""

        self.progress_states.append(state)
        self.events.append("progress_state")
        self.thread_ids.append(threading.get_ident())

    def apply_generation_model_load_progress(
        self,
        update: ModelLoadProgressUpdate,
    ) -> None:
        """Record one model-load update."""

        self.model_load.append(update)
        self.events.append("model_load")
        self.thread_ids.append(threading.get_ident())

    def apply_generation_preview(self, update: LivePreviewEvent) -> None:
        """Record one preview update."""

        self.previews.append(update)
        self.events.append("preview")
        self.thread_ids.append(threading.get_ident())

    def apply_generation_output_image(self, update: LiveFinalOutputEvent) -> None:
        """Record one output image update."""

        self.outputs.append(update)
        self.events.append("output")
        self.thread_ids.append(threading.get_ident())

    def apply_generation_timing(self, update: GenerationExecutionTiming) -> None:
        """Record one generation timing update."""

        self.timing.append(update)
        self.events.append("timing")
        self.thread_ids.append(threading.get_ident())

    def apply_generation_failure(self, failure: GenerationFailure) -> None:
        """Record one failure update."""

        self.failures.append(failure)
        self.events.append("failure")
        self.thread_ids.append(threading.get_ident())

    def apply_generation_completed(self, event: ListenerCompleted) -> None:
        """Record one completion update."""

        self.completed.append(event)
        self.events.append("completed")
        self.thread_ids.append(threading.get_ident())


def test_queued_progress_callback_reaches_sink_on_gui_thread() -> None:
    """Queued dispatcher ingress should deliver progress on the GUI thread."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink)
    gui_thread_id = threading.get_ident()

    dispatcher.on_run_started(_run_started())
    dispatcher.on_progress(
        _progress_update(workflow_percent=25.0, sampler_percent=None)
    )
    _process_events_until(lambda: bool(sink.progress))

    assert sink.progress == [
        _progress_update(workflow_percent=25.0, sampler_percent=None)
    ]
    assert sink.thread_ids == [gui_thread_id]
    app = QCoreApplication.instance()
    assert app is not None
    assert dispatcher.thread() == app.thread()


def test_dispatcher_marks_output_activity_after_batch_applies() -> None:
    """Applied generation feedback should notify the prompt projection load tracker."""

    _qt_app()
    sink = _Sink()
    marked_reasons: list[str] = []
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        output_activity_marker=marked_reasons.append,
    )

    dispatcher.on_run_started(_run_started())
    dispatcher.on_progress(
        _progress_update(workflow_percent=25.0, sampler_percent=None)
    )
    _process_events_until(lambda: bool(marked_reasons))

    assert marked_reasons == ["generation_feedback_adaptive_flush"]


def test_rapid_progress_events_deliver_latest_scheduled_value() -> None:
    """Rapid progress updates should coalesce to the latest scheduled value."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=10)

    dispatcher.on_run_started(_run_started())
    dispatcher.on_progress(_progress_update(workflow_percent=0.0, sampler_percent=0.0))
    _process_events_until(lambda: len(sink.progress) == 1)
    dispatcher.on_progress(_progress_update(workflow_percent=10.0, sampler_percent=1.0))
    _process_events_until(lambda: len(sink.progress) == 2)
    dispatcher.on_progress(_progress_update(workflow_percent=20.0, sampler_percent=2.0))
    dispatcher.on_progress(_progress_update(workflow_percent=30.0, sampler_percent=3.0))
    _process_events_until(lambda: len(sink.progress) == 3)

    assert sink.progress[-1] == _progress_update(
        workflow_percent=30.0,
        sampler_percent=3.0,
    )


def test_completion_progress_flushes_immediately() -> None:
    """Progress at 100 percent should bypass the scheduled timer delay."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=1000)

    dispatcher.on_run_started(_run_started())
    dispatcher.on_progress(
        _progress_update(workflow_percent=100.0, sampler_percent=None)
    )
    _process_events_until(lambda: bool(sink.progress))

    assert sink.progress == [
        _progress_update(workflow_percent=100.0, sampler_percent=None)
    ]


def test_active_prompt_defers_boundary_progress_to_prompt_interval() -> None:
    """Prompt editing should make repaint-only boundary progress frame-budgeted."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        flush_interval_ms=1000,
        active_prompt_flush_interval_ms=10,
        prompt_interaction_active=lambda: True,
        prompt_interaction_elapsed_ms=lambda: 5.0,
    )

    dispatcher.on_run_started(_run_started())
    dispatcher.on_progress(_progress_update(workflow_percent=0.0, sampler_percent=0.0))
    app = _qt_app()
    app.processEvents()

    assert sink.progress == []

    _process_events_until(lambda: bool(sink.progress))

    assert sink.progress == [
        _progress_update(workflow_percent=0.0, sampler_percent=0.0)
    ]


def test_active_prompt_completion_progress_still_flushes_immediately() -> None:
    """Completed progress should not wait behind prompt-interaction deferral."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        flush_interval_ms=1000,
        active_prompt_flush_interval_ms=1000,
        prompt_interaction_active=lambda: True,
    )

    dispatcher.on_run_started(_run_started())
    dispatcher.on_progress(
        _progress_update(workflow_percent=100.0, sampler_percent=None)
    )
    _process_events_until(lambda: bool(sink.progress))

    assert sink.progress == [
        _progress_update(workflow_percent=100.0, sampler_percent=None)
    ]


def test_retire_progress_reaches_sink_on_gui_thread() -> None:
    """Explicit progress retirement should publish hidden state on the GUI thread."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=1000)
    gui_thread_id = threading.get_ident()

    dispatcher.on_run_started(_run_started())
    _qt_app().processEvents()
    dispatcher.retire_progress(reason="stopped")
    _process_events_until(lambda: bool(sink.progress_states))

    assert sink.progress == []
    assert sink.progress_states[-1] == ProgressViewState.hidden(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )
    assert sink.thread_ids[-1] == gui_thread_id


def test_retire_progress_clears_scheduled_progress() -> None:
    """Retirement should prevent a scheduled stale progress update from reopening."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=1000)

    dispatcher.on_run_started(_run_started())
    _qt_app().processEvents()
    dispatcher.on_progress(_progress_update(workflow_percent=10.0, sampler_percent=0.0))
    _process_events_until(lambda: len(sink.progress) == 1)
    dispatcher.on_progress(_progress_update(workflow_percent=43.0, sampler_percent=9.0))
    dispatcher.retire_progress(reason="stopped")
    _process_events_until(lambda: bool(sink.progress_states))

    assert sink.progress == [
        _progress_update(workflow_percent=10.0, sampler_percent=0.0)
    ]
    assert sink.progress_states[-1].show_overlay is False


def test_retire_progress_is_not_deferred_by_prompt_interaction() -> None:
    """Progress retirement should bypass prompt-interaction visual deferral."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        flush_interval_ms=1000,
        active_prompt_flush_interval_ms=1000,
        prompt_interaction_active=lambda: True,
    )

    dispatcher.on_run_started(_run_started())
    _qt_app().processEvents()
    dispatcher.retire_progress(reason="stopped")

    assert sink.progress_states == [
        ProgressViewState.hidden(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
        )
    ]


def test_late_queued_progress_after_retire_is_ignored() -> None:
    """A stale queued progress signal should not reopen retired progress."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=10)

    dispatcher.on_run_started(_run_started())
    _qt_app().processEvents()
    dispatcher.retire_progress(reason="stopped")
    _process_events_until(lambda: bool(sink.progress_states))
    dispatcher.on_progress(_progress_update(workflow_percent=43.0, sampler_percent=9.0))
    app = _qt_app()
    app.processEvents()
    QThread.msleep(20)
    app.processEvents()

    assert sink.progress == []


def test_rapid_previews_deliver_latest_preview() -> None:
    """Preview delivery should be latest-frame-wins for one preview slot."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=10)
    dispatcher.on_run_started(_run_started())
    first = _preview_update(image="first")
    second = _preview_update(image="second")

    dispatcher.on_preview(first)
    dispatcher.on_preview(second)
    _process_events_until(lambda: bool(sink.previews))

    assert sink.previews == [_live_preview(second)]


def test_active_prompt_previews_deliver_latest_preview_on_prompt_interval() -> None:
    """Prompt editing should still deliver the latest preview without stale frames."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        flush_interval_ms=1000,
        active_prompt_flush_interval_ms=10,
        prompt_interaction_active=lambda: True,
    )
    dispatcher.on_run_started(_run_started())
    first = _preview_update(image="first")
    second = _preview_update(image="second")

    dispatcher.on_preview(first)
    dispatcher.on_preview(second)
    app = _qt_app()
    app.processEvents()

    assert sink.previews == []

    _process_events_until(lambda: bool(sink.previews))

    assert sink.previews == [_live_preview(second)]


def test_model_load_progress_delivers_latest_scheduled_value() -> None:
    """Intermediate model-load updates should coalesce to the latest scheduled value."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=10)
    first = _model_load_update(percent=10.0, state="running")
    second = _model_load_update(percent=20.0, state="running")

    dispatcher.on_model_load_progress(first)
    assert sink.model_load == []

    dispatcher.on_model_load_progress(second)
    _process_events_until(lambda: bool(sink.model_load))

    assert sink.model_load == [second]


def test_active_prompt_terminal_model_load_flushes_immediately() -> None:
    """Terminal model-load updates should not wait behind prompt interaction."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        flush_interval_ms=1000,
        active_prompt_flush_interval_ms=1000,
        prompt_interaction_active=lambda: True,
    )
    terminal_update = _model_load_update(percent=100.0, state="finished")

    dispatcher.on_model_load_progress(terminal_update)
    _process_events_until(lambda: bool(sink.model_load))

    assert sink.model_load == [terminal_update]


def test_output_images_all_reach_sink(tmp_path: Path) -> None:
    """Final output image delivery should not be coalesced."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink)
    dispatcher.on_run_started(_run_started())
    first = _output_update(tmp_path / "first.png")
    second = _output_update(tmp_path / "second.png")

    dispatcher.on_output_image(first)
    dispatcher.on_output_image(second)
    _process_events_until(lambda: len(sink.outputs) == 2)

    assert sink.outputs == [_live_output(first), _live_output(second)]


def test_output_images_bypass_active_prompt_deferral(tmp_path: Path) -> None:
    """Final output delivery should stay durable while prompt interaction is active."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        flush_interval_ms=1000,
        active_prompt_flush_interval_ms=1000,
        prompt_interaction_active=lambda: True,
    )
    dispatcher.on_run_started(_run_started())
    output_update = _output_update(tmp_path / "output.png")

    dispatcher.on_output_image(output_update)
    _process_events_until(lambda: bool(sink.outputs))

    assert sink.outputs == [_live_output(output_update)]


def test_timing_reaches_sink_before_later_completion() -> None:
    """Timing updates should flush as durable metadata before completion."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=1000)
    dispatcher.on_run_started(_run_started())
    timing_update = GenerationExecutionTiming(
        workflow_id="wf",
        prompt_id="pid",
        job_duration_ms=3080.0,
    )

    dispatcher.on_timing(timing_update)
    dispatcher.on_completed(_completed())
    _process_events_until(lambda: bool(sink.completed))

    assert sink.timing == [timing_update]
    assert sink.completed == [_completed()]
    assert sink.events.index("timing") < sink.events.index("completed")


def test_failures_reach_sink_immediately() -> None:
    """Failures should force immediate cleanup delivery."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=1000)
    dispatcher.on_run_started(_run_started())
    failure = GenerationFailure(
        stage="listen",
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        message="failed",
    )

    dispatcher.on_failure(failure)
    _process_events_until(lambda: bool(sink.failures))

    assert sink.failures == [failure]


def test_completion_reaches_sink_immediately() -> None:
    """Completions should force immediate cleanup delivery."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=1000)

    dispatcher.on_run_started(_run_started())
    dispatcher.on_completed(_completed())
    _process_events_until(lambda: bool(sink.completed))

    assert sink.completed == [_completed()]


def _qt_app() -> QApplication:
    """Return a running Qt application for dispatcher tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _process_events_until(condition: object, *, max_turns: int = 200) -> None:
    """Process Qt events until a condition is true or the test should fail."""

    assert callable(condition)
    app = _qt_app()
    for _ in range(max_turns):
        if bool(condition()):
            return
        app.processEvents()
        QThread.msleep(5)
    raise AssertionError("condition was not reached while processing Qt events")


def _output_update(path: Path) -> OutputImageUpdate:
    """Build one final output image update."""

    return OutputImageUpdate(
        workflow_id="wf",
        workflow_payload={"N1": {"class_type": "SaveImage"}},
        file_path=path,
        node_id="N1",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        source_key="wf:N1",
        source_label="Cube",
        list_index=0,
        artifact_width=640,
        artifact_height=480,
    )


def _preview_update(*, image: object) -> PreviewImageUpdate:
    """Build one scoped preview update."""

    return PreviewImageUpdate(
        workflow_id="wf",
        image=image,
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        node_id="N1",
        source_key="wf:N1",
        source_label="Cube",
    )


def _live_preview(update: PreviewImageUpdate) -> LivePreviewEvent:
    """Build a strict preview event for dispatcher assertions."""

    event = LivePreviewEvent.from_update(update)
    assert event is not None
    return event


def _live_output(update: OutputImageUpdate) -> LiveFinalOutputEvent:
    """Build a strict final event for dispatcher assertions."""

    event = LiveFinalOutputEvent.from_update(update)
    assert event is not None
    return event


def _run_started() -> GenerationRunStarted:
    """Build one active-run registration event."""

    return GenerationRunStarted(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
    )


def _completed() -> ListenerCompleted:
    """Build one active-run completion event."""

    return ListenerCompleted(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )


def _progress_update(
    *,
    workflow_id: str = "wf",
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
    workflow_percent: float | None,
    sampler_percent: float | None,
) -> ProgressUpdate:
    """Build one identity-bearing progress update."""

    return ProgressUpdate(
        workflow_id=workflow_id,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
        workflow_percent=workflow_percent,
        sampler_percent=sampler_percent,
    )


def _model_load_update(
    *,
    percent: float,
    state: str,
) -> ModelLoadProgressUpdate:
    """Build one source-enriched model-load progress update."""

    return ModelLoadProgressUpdate(
        workflow_id="wf",
        prompt_id="pid",
        node_id="4",
        display_node_id="4",
        phase="dynamic_vram_staging",
        state=state,
        percent=percent,
        value=None,
        maximum=None,
        unit=None,
        model_class="SDXL",
        model_name="model.safetensors",
        source_node_id="2",
        source_input_key="ckpt_name",
        source_cube_alias="Cube",
        source_workflow_node_name="checkpoint",
        detail=None,
    )
