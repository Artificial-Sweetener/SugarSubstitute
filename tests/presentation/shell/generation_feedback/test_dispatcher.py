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

from PySide6.QtCore import QCoreApplication

from substitute.application.generation import GenerationFailure
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import (
    GenerationExecutionTiming,
)
from substitute.presentation.shell.generation_feedback_dispatcher import (
    GenerationFeedbackDispatcher,
)
from tests.presentation.shell.generation_feedback.support import (
    RecordingFeedbackSink as _Sink,
    completed as _completed,
    live_output as _live_output,
    live_preview as _live_preview,
    model_load_update as _model_load_update,
    output_update as _output_update,
    preview_update as _preview_update,
    progress_update as _progress_update,
    qt_app as _qt_app,
    run_started as _run_started,
    wait_for_sink,
)
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


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
    wait_for_sink(sink, lambda: bool(sink.progress))

    assert sink.progress == [
        _progress_update(workflow_percent=25.0, sampler_percent=None)
    ]
    assert sink.events == ["run_started", "progress"]
    assert sink.thread_ids == [gui_thread_id, gui_thread_id]
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
    wait_for_sink(sink, lambda: bool(sink.progress))

    assert marked_reasons == ["generation_feedback_adaptive_flush"]


def test_rapid_progress_events_deliver_latest_scheduled_value() -> None:
    """Rapid progress updates should coalesce to the latest scheduled value."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=10)

    dispatcher.on_run_started(_run_started())
    dispatcher.on_progress(_progress_update(workflow_percent=0.0, sampler_percent=0.0))
    wait_for_sink(sink, lambda: len(sink.progress) == 1)
    dispatcher.on_progress(_progress_update(workflow_percent=10.0, sampler_percent=1.0))
    wait_for_sink(sink, lambda: len(sink.progress) == 2)
    dispatcher.on_progress(_progress_update(workflow_percent=20.0, sampler_percent=2.0))
    dispatcher.on_progress(_progress_update(workflow_percent=30.0, sampler_percent=3.0))
    wait_for_sink(sink, lambda: len(sink.progress) == 3)

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
    wait_for_sink(sink, lambda: bool(sink.progress))

    assert sink.progress == [
        _progress_update(workflow_percent=100.0, sampler_percent=None)
    ]


def test_active_prompt_defers_boundary_progress_until_next_flush() -> None:
    """Defer repaint-only boundary progress while prompt interaction is active."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        flush_interval_ms=1000,
        active_prompt_flush_interval_ms=1000,
        prompt_interaction_active=lambda: True,
        prompt_interaction_elapsed_ms=lambda: 5.0,
    )

    dispatcher.on_run_started(_run_started())
    dispatcher.on_progress(_progress_update(workflow_percent=0.0, sampler_percent=0.0))
    wait_for_queued_qt_turn()

    assert sink.progress == []

    dispatcher.flush_now()

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
    wait_for_sink(sink, lambda: bool(sink.progress))

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
    wait_for_sink(sink, lambda: bool(sink.run_started))
    dispatcher.retire_progress(reason="stopped")
    wait_for_sink(sink, lambda: bool(sink.progress_states))

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
    wait_for_sink(sink, lambda: bool(sink.run_started))
    dispatcher.on_progress(_progress_update(workflow_percent=10.0, sampler_percent=0.0))
    wait_for_sink(sink, lambda: len(sink.progress) == 1)
    dispatcher.on_progress(_progress_update(workflow_percent=43.0, sampler_percent=9.0))
    dispatcher.retire_progress(reason="stopped")
    wait_for_sink(sink, lambda: bool(sink.progress_states))

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
    wait_for_sink(sink, lambda: bool(sink.run_started))
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
    wait_for_sink(sink, lambda: bool(sink.run_started))
    dispatcher.retire_progress(reason="stopped")
    wait_for_sink(sink, lambda: bool(sink.progress_states))
    dispatcher.on_progress(_progress_update(workflow_percent=43.0, sampler_percent=9.0))
    dispatcher.on_completed(_completed())
    wait_for_sink(sink, lambda: bool(sink.completed))

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
    wait_for_sink(sink, lambda: bool(sink.previews))

    assert sink.previews == [_live_preview(second)]


def test_active_prompt_previews_deliver_latest_preview_on_next_flush() -> None:
    """Flush only the latest prompt-time preview after its scheduled deferral."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(
        sink=sink,
        flush_interval_ms=1000,
        active_prompt_flush_interval_ms=1000,
        prompt_interaction_active=lambda: True,
    )
    dispatcher.on_run_started(_run_started())
    first = _preview_update(image="first")
    second = _preview_update(image="second")

    dispatcher.on_preview(first)
    dispatcher.on_preview(second)
    wait_for_queued_qt_turn()

    assert sink.previews == []

    dispatcher.flush_now()

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
    wait_for_sink(sink, lambda: bool(sink.model_load))

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
    wait_for_sink(sink, lambda: bool(sink.model_load))

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
    wait_for_sink(sink, lambda: len(sink.outputs) == 2)

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
    wait_for_sink(sink, lambda: bool(sink.outputs))

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
    wait_for_sink(sink, lambda: bool(sink.completed))

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
    wait_for_sink(sink, lambda: bool(sink.failures))

    assert sink.failures == [failure]


def test_completion_reaches_sink_immediately() -> None:
    """Completions should force immediate cleanup delivery."""

    _qt_app()
    sink = _Sink()
    dispatcher = GenerationFeedbackDispatcher(sink=sink, flush_interval_ms=1000)

    dispatcher.on_run_started(_run_started())
    dispatcher.on_completed(_completed())
    wait_for_sink(sink, lambda: bool(sink.completed))

    assert sink.completed == [_completed()]
