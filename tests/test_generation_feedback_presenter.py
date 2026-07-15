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

"""Cover generation feedback presentation outside MainWindow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.errors import ErrorReport, ErrorReportKind
from substitute.application.generation import GenerationFailure
from substitute.application.ports import (
    CubeExecutionTiming,
    GenerationExecutionTiming,
    ListenerCompleted,
    ModelLoadProgressUpdate,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputVisualIdentity,
    SourceOnlyOutputIdentity,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    GenerationFeedbackPresenter,
)


def test_output_image_submits_to_output_pipeline(tmp_path: Path) -> None:
    """Generation output callback should forward strict live events unchanged."""

    submitted: list[object] = []
    shell = SimpleNamespace(
        output_image_pipeline=SimpleNamespace(
            submit_live_output_event=lambda update: submitted.append(update)
        )
    )
    output_update = _live_output(tmp_path)

    GenerationFeedbackPresenter(shell).apply_generation_output_image(output_update)

    assert submitted == [output_update]


def test_generation_failure_appends_output_line_and_presents_report() -> None:
    """Generation failures should surface shell output and structured errors."""

    appended_lines: list[str] = []
    presented_reports: list[object] = []
    preview_clears: list[str] = []
    model_clears: list[str] = []
    progress_clears: list[str] = []
    report = ErrorReport(
        kind=ErrorReportKind.EXECUTION,
        title="KSampler failed",
        message="CUDA out of memory",
        stage="listen",
    )
    shell = _feedback_shell(
        editor_panels={
            "wf-1": SimpleNamespace(
                clear_model_field_load_progress=lambda: model_clears.append("wf-1")
            )
        },
        generation_action_controller=SimpleNamespace(
            clear_generation_progress=lambda: progress_clears.append("progress")
        ),
        workspace_canvas_actions=SimpleNamespace(
            clear_output_previews=lambda workflow_id: preview_clears.append(workflow_id)
        ),
        _comfy_output_stream=SimpleNamespace(
            append_line=lambda line: appended_lines.append(line)
        ),
        _error_presenter=SimpleNamespace(
            show_error_report=lambda error_report: presented_reports.append(
                error_report
            )
        ),
    )
    failure = GenerationFailure(
        stage="listen",
        workflow_id="wf-1",
        message="CUDA out of memory",
        prompt_id="prompt-123",
        error_report=report,
    )

    GenerationFeedbackPresenter(shell).apply_generation_failure(failure)

    assert progress_clears == ["progress"]
    assert model_clears == ["wf-1"]
    assert preview_clears == ["wf-1"]
    assert appended_lines == [
        "Generation failed during listen: CUDA out of memory prompt_id=prompt-123"
    ]
    assert presented_reports == [report]


def test_generation_completion_clears_nonvisual_progress_only() -> None:
    """Completion should clear model progress and taskbar without clearing previews."""

    model_clears: list[str] = []
    taskbar_clears: list[str] = []
    preview_clears: list[str] = []
    shell = _feedback_shell(
        editor_panels={
            "wf-1": SimpleNamespace(
                clear_model_field_load_progress=lambda: model_clears.append("wf-1")
            )
        },
        workspace_canvas_actions=SimpleNamespace(
            clear_output_previews=lambda workflow_id: preview_clears.append(workflow_id)
        ),
        _taskbar_progress_presenter=SimpleNamespace(
            clear_progress=lambda: taskbar_clears.append("taskbar")
        ),
    )

    GenerationFeedbackPresenter(shell).apply_generation_completed(
        ListenerCompleted(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        )
    )

    assert model_clears == ["wf-1"]
    assert taskbar_clears == ["taskbar"]
    assert preview_clears == []


def test_model_load_progress_routes_to_source_model_picker() -> None:
    """Source-enriched model-load progress should update the owning editor panel."""

    calls: list[dict[str, object]] = []
    panel = SimpleNamespace(
        set_model_field_load_progress=lambda **kwargs: calls.append(kwargs)
    )
    shell = _feedback_shell(
        editor_panels={"wf-1": panel},
        progress_service=SimpleNamespace(
            build_model_load_view_state=lambda **_kwargs: SimpleNamespace(
                show_overlay=True,
                display_percent=42.5,
            )
        ),
    )

    GenerationFeedbackPresenter(shell).apply_generation_model_load_progress(
        _model_load_update()
    )

    assert calls == [
        {
            "cube_alias": "Cube",
            "node_name": "checkpoint",
            "field_key": "ckpt_name",
            "percent": 42.5,
            "active": True,
        }
    ]


def test_clear_output_for_workflow_clears_model_field_and_output_projection() -> None:
    """Fresh generation should clear stale model progress and workflow output."""

    calls: list[str] = []
    shell = _feedback_shell(
        editor_panels={
            "wf-1": SimpleNamespace(
                clear_model_field_load_progress=lambda: calls.append("model:wf-1")
            )
        },
        workflow_session_service=SimpleNamespace(workflows={"wf-1": object()}),
        output_image_pipeline=SimpleNamespace(
            remove_workflow=lambda workflow_id: calls.append(
                f"pending-output:{workflow_id}"
            )
        ),
        output_canvas_projection_coordinator=SimpleNamespace(
            clear_output_for_workflow=lambda _workflows, workflow_id: calls.append(
                f"output:{workflow_id}"
            )
        ),
    )

    GenerationFeedbackPresenter(shell).clear_output_for_workflow("wf-1")

    assert calls == ["model:wf-1", "pending-output:wf-1", "output:wf-1"]
    assert shell._sampler_progress_model_fields_cleared is False


def test_generation_timing_updates_output_state_and_schedules_projection() -> None:
    """Timing feedback should update output metadata and schedule intended projection."""

    timing_kwargs: dict[str, object] = {}
    scheduled: list[object] = []
    projection_intent = SimpleNamespace(should_schedule=True)

    def apply_output_source_timing(*_args: object, **kwargs: object) -> object:
        timing_kwargs.update(kwargs)
        return SimpleNamespace(projection_intent=projection_intent)

    shell = _feedback_shell(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-1": object()},
            active_workflow_id="wf-1",
        ),
        output_canvas_state_service=SimpleNamespace(
            apply_output_source_timing=apply_output_source_timing
        ),
        output_image_pipeline=SimpleNamespace(
            schedule_output_projection=lambda intent: scheduled.append(intent)
        ),
    )

    GenerationFeedbackPresenter(shell).apply_generation_timing(
        GenerationExecutionTiming(
            workflow_id="wf-1",
            prompt_id="prompt-1",
            job_duration_ms=1000.0,
            cube_timings=(
                CubeExecutionTiming(
                    cube_alias="Sampler",
                    source_key="wf-1:N1",
                    duration_ms=25.0,
                ),
            ),
        )
    )

    assert timing_kwargs["source_durations_ms"] == {"wf-1:N1": 25.0}
    assert timing_kwargs["cube_durations_ms"] == {"Sampler": 25.0}
    assert scheduled == [projection_intent]


def test_sampler_progress_model_field_clear_is_idempotent() -> None:
    """Sampler progress should clear model-load widgets once per reset marker."""

    calls: list[str] = []
    shell = _feedback_shell(
        editor_panels={
            "wf-1": SimpleNamespace(
                clear_model_field_load_progress=lambda: calls.append("wf-1")
            ),
            "wf-2": SimpleNamespace(
                clear_model_field_load_progress=lambda: calls.append("wf-2")
            ),
        }
    )
    presenter = GenerationFeedbackPresenter(shell)

    presenter.clear_model_field_progress_for_sampler_once()
    presenter.clear_model_field_progress_for_sampler_once()
    presenter.mark_sampler_progress_model_field_clear_needed()
    presenter.clear_model_field_progress_for_sampler_once()

    assert calls == ["wf-1", "wf-2", "wf-1", "wf-2"]


def _live_output(tmp_path: Path) -> LiveFinalOutputEvent:
    """Build a strict live output event for presenter tests."""

    return LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf-1",
            generation_run_id="run-output",
            prompt_id="prompt-output",
            client_id="client-output",
            source_key="wf-1:N1",
            source_label="MyCube",
            scene=SourceOnlyOutputIdentity(),
        ),
        node_id="N1",
        workflow_payload={"N1": {"_meta": {"title": "MyCube.KSampler"}}},
        file_path=tmp_path / "007_cube_preview.png",
        list_index=0,
        artifact_width=640,
        artifact_height=480,
    )


def _model_load_update() -> ModelLoadProgressUpdate:
    """Build source-enriched model-load progress for presenter tests."""

    return ModelLoadProgressUpdate(
        workflow_id="wf-1",
        prompt_id="pid-1",
        node_id="4",
        display_node_id="4",
        phase="dynamic_vram_staging",
        state="running",
        percent=42.5,
        value=2048.0,
        maximum=4897.0,
        unit="bytes",
        model_class="SDXL",
        model_name="example.safetensors",
        source_node_id="2",
        source_input_key="ckpt_name",
        source_cube_alias="Cube",
        source_workflow_node_name="checkpoint",
        detail=None,
    )


def _feedback_shell(**overrides: object) -> SimpleNamespace:
    """Build a shell fake with default feedback collaborators."""

    values: dict[str, object] = {
        "active_editor_panel": None,
        "editor_panels": {},
        "generation_action_controller": SimpleNamespace(
            clear_generation_progress=lambda: None
        ),
        "workspace_controller": None,
        "_comfy_output_stream": SimpleNamespace(append_line=lambda _line: None),
        "_error_presenter": None,
        "_taskbar_progress_presenter": SimpleNamespace(clear_progress=lambda: None),
        "workflow_session_service": SimpleNamespace(
            workflows={},
            active_workflow_id="wf-1",
        ),
        "output_canvas_projection_coordinator": SimpleNamespace(
            clear_output_for_workflow=lambda _workflows, _workflow_id: None
        ),
        "output_image_pipeline": SimpleNamespace(
            submit_live_output_event=lambda _event: None,
            schedule_output_projection=lambda _intent: None,
        ),
        "output_canvas_state_service": SimpleNamespace(
            apply_output_source_timing=lambda *_args, **_kwargs: SimpleNamespace(
                projection_intent=SimpleNamespace(should_schedule=False)
            )
        ),
        "progress_service": SimpleNamespace(
            build_model_load_view_state=lambda **_kwargs: SimpleNamespace(
                show_overlay=False,
                display_percent=None,
            )
        ),
        "preview_image_signal": SimpleNamespace(emit=lambda _event: None),
        "clear_output_signal": SimpleNamespace(emit=lambda _workflow_id: None),
    }
    values.update(overrides)
    return SimpleNamespace(**values)
