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

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.errors import ErrorReport, ErrorReportKind
from substitute.application.generation import GenerationFailure
from substitute.application.generation import GenerationRunStarted
from substitute.application.ports import (
    CubeExecutionTiming,
    GenerationExecutionTiming,
    ListenerCompleted,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    GenerationFeedbackPresenter,
)
import substitute.presentation.shell.window_attention as window_attention
from tests.presentation.shell.generation_feedback.presenter_support import (
    _feedback_shell,
    _live_output,
    _model_load_update,
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


def test_generation_completion_requests_attention_when_shell_is_unfocused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed generation should use native attention without changing focus."""

    _ = QApplication.instance() or QApplication([])
    attention_requests: list[tuple[QWidget, int]] = []

    class _ShellWindow(QWidget):
        """Expose a visible window whose focus belongs to another application."""

        def isActiveWindow(self) -> bool:
            """Report that the shell is not the active application window."""

            return False

    class _AttentionApplication:
        """Record the Qt native-attention request."""

        @staticmethod
        def alert(window: QWidget, milliseconds: int) -> None:
            """Capture the target and requested alert lifetime."""

            attention_requests.append((window, milliseconds))

    shell_window = _ShellWindow()
    shell = _feedback_shell(window=lambda: shell_window)
    monkeypatch.setattr(window_attention, "QApplication", _AttentionApplication)

    GenerationFeedbackPresenter(shell).apply_generation_completed(
        ListenerCompleted(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        )
    )

    assert attention_requests == [(shell_window, 0)]
    shell_window.close()


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
        output_canvas_timing_service=SimpleNamespace(
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


def test_generation_run_start_begins_output_navigation_session() -> None:
    """Route accepted run identity into the Output navigation session owner."""

    calls: list[tuple[object, str, str]] = []
    workflows = {"wf-1": object()}
    shell = _feedback_shell(
        workflow_session_service=SimpleNamespace(
            workflows=workflows,
            active_workflow_id="wf-1",
        ),
        output_navigation_session_service=SimpleNamespace(
            begin_session=lambda owned, workflow_id, session_id: calls.append(
                (owned, workflow_id, session_id)
            )
        ),
    )

    GenerationFeedbackPresenter(shell).apply_generation_run_started(
        GenerationRunStarted(
            workflow_id="wf-1",
            generation_run_id="generation-2",
            output_session_id="scene-run-2",
            prompt_id="prompt-2",
            client_id="client-2",
        )
    )

    assert calls == [(workflows, "wf-1", "scene-run-2")]


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
