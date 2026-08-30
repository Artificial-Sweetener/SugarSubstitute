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

"""Build deterministic generation feedback events for coalescer tests."""

from __future__ import annotations

from pathlib import Path


from substitute.application.generation import GenerationRunStarted
from substitute.application.ports import (
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    LivePreviewEvent,
)


def _model_load_update(
    *,
    percent: float = 10.0,
    phase: str = "dynamic_vram_staging",
    state: str = "running",
) -> ModelLoadProgressUpdate:
    """Build one source-enriched model-load progress update."""

    return ModelLoadProgressUpdate(
        workflow_id="wf",
        prompt_id="pid",
        node_id="4",
        display_node_id="4",
        phase=phase,
        state=state,
        percent=percent,
        value=None,
        maximum=None,
        unit=None,
        model_class=None,
        model_name=None,
        source_node_id="2",
        source_input_key="ckpt_name",
        source_cube_alias="Cube",
        source_workflow_node_name="checkpoint",
        detail=None,
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


def _preview_update(
    *,
    image: object,
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
    node_id: str = "N1",
    source_key: str = "wf:N1",
    scene_run_id: str | None = None,
    scene_key: str | None = None,
) -> PreviewImageUpdate:
    """Build one scoped preview update for coalescer lifecycle tests."""

    scene_title = None
    scene_order = None
    scene_count = None
    if scene_run_id is not None or scene_key is not None:
        scene_title = scene_key or "scene"
        scene_order = 0
        scene_count = 2
    return PreviewImageUpdate(
        workflow_id="wf",
        image=image,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
        node_id=node_id,
        source_key=source_key,
        source_label="Cube",
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
    )


def _output_update(
    path: Path,
    *,
    list_index: int | None = 0,
    scene_run_id: str | None = None,
    scene_key: str | None = None,
) -> OutputImageUpdate:
    """Build one scoped final output image update."""

    scene_title = None
    scene_order = None
    scene_count = None
    if scene_run_id is not None or scene_key is not None:
        scene_title = scene_key or "scene"
        scene_order = 0
        scene_count = 2
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
        list_index=list_index,
        artifact_width=640,
        artifact_height=480,
        scene_run_id=scene_run_id,
        scene_key=scene_key,
        scene_title=scene_title,
        scene_order=scene_order,
        scene_count=scene_count,
    )


def _live_preview(update: PreviewImageUpdate) -> LivePreviewEvent:
    """Build a strict preview event for coalescer assertions."""

    event = LivePreviewEvent.from_update(update)
    assert event is not None
    return event


def _live_output(update: OutputImageUpdate) -> LiveFinalOutputEvent:
    """Build a strict final event for coalescer assertions."""

    event = LiveFinalOutputEvent.from_update(update)
    assert event is not None
    return event


def _run_started(
    *,
    workflow_id: str = "wf",
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
) -> GenerationRunStarted:
    """Build one active-run registration event."""

    return GenerationRunStarted(
        workflow_id=workflow_id,
        generation_run_id=generation_run_id,
        output_session_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
    )
