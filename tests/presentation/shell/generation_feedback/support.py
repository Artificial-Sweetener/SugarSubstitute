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

"""Provide observable feedback records and deterministic event builders."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QSignalSpy
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


class RecordingFeedbackSink(QObject):
    """Record dispatcher calls and signal each observable delivery."""

    updated = Signal()

    def __init__(self) -> None:
        """Initialize empty call records."""

        super().__init__()
        self.run_started: list[GenerationRunStarted] = []
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

    def apply_generation_run_started(self, event: GenerationRunStarted) -> None:
        """Record one accepted generation run."""

        self.run_started.append(event)
        self._record_delivery("run_started")

    def apply_generation_progress(self, update: ProgressUpdate) -> None:
        """Record one progress update."""

        self.progress.append(update)
        self._record_delivery("progress")

    def apply_generation_progress_state(self, state: ProgressViewState) -> None:
        """Record one projected progress state."""

        self.progress_states.append(state)
        self._record_delivery("progress_state")

    def apply_generation_model_load_progress(
        self,
        update: ModelLoadProgressUpdate,
    ) -> None:
        """Record one model-load update."""

        self.model_load.append(update)
        self._record_delivery("model_load")

    def apply_generation_preview(self, update: LivePreviewEvent) -> None:
        """Record one preview update."""

        self.previews.append(update)
        self._record_delivery("preview")

    def apply_generation_output_image(self, update: LiveFinalOutputEvent) -> None:
        """Record one output image update."""

        self.outputs.append(update)
        self._record_delivery("output")

    def apply_generation_timing(self, update: GenerationExecutionTiming) -> None:
        """Record one generation timing update."""

        self.timing.append(update)
        self._record_delivery("timing")

    def apply_generation_failure(self, failure: GenerationFailure) -> None:
        """Record one failure update."""

        self.failures.append(failure)
        self._record_delivery("failure")

    def apply_generation_completed(self, event: ListenerCompleted) -> None:
        """Record one completion update."""

        self.completed.append(event)
        self._record_delivery("completed")

    def _record_delivery(self, event: str) -> None:
        """Record delivery context and publish observable completion."""

        self.events.append(event)
        self.thread_ids.append(threading.get_ident())
        self.updated.emit()


def qt_app() -> QApplication:
    """Return the process Qt application for dispatcher tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def wait_for_sink(
    sink: RecordingFeedbackSink,
    condition: Callable[[], bool],
) -> None:
    """Wait for observable sink delivery with a bounded failure timeout."""

    spy = QSignalSpy(sink.updated)
    while not condition():
        assert spy.wait(1_000), "generation feedback did not reach the sink"


def output_update(path: Path) -> OutputImageUpdate:
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


def preview_update(*, image: object) -> PreviewImageUpdate:
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


def live_preview(update: PreviewImageUpdate) -> LivePreviewEvent:
    """Build a strict preview event for dispatcher assertions."""

    event = LivePreviewEvent.from_update(update)
    assert event is not None
    return event


def live_output(update: OutputImageUpdate) -> LiveFinalOutputEvent:
    """Build a strict final event for dispatcher assertions."""

    event = LiveFinalOutputEvent.from_update(update)
    assert event is not None
    return event


def run_started() -> GenerationRunStarted:
    """Build one active-run registration event."""

    return GenerationRunStarted(
        workflow_id="wf",
        generation_run_id="run-1",
        output_session_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
    )


def completed() -> ListenerCompleted:
    """Build one active-run completion event."""

    return ListenerCompleted(
        workflow_id="wf",
        generation_run_id="run-1",
        prompt_id="pid-1",
    )


def progress_update(
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


def model_load_update(*, percent: float, state: str) -> ModelLoadProgressUpdate:
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
