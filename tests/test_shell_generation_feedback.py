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

"""Tests for shell generation feedback and availability projection."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.errors import ErrorReport, ErrorReportKind
from substitute.application.generation import (
    GenerationFailure,
    GenerationRunStarted,
    WorkflowProgressService,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputVisualIdentity,
    SourceOnlyOutputIdentity,
)
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)
from substitute.presentation.shell.generation_feedback_presenter import (
    GenerationFeedbackPresenter,
)


class _VisibleWidget:
    """Record visibility updates."""

    def __init__(self) -> None:
        """Initialize an unset visibility state."""

        self.visible: bool | None = None

    def show(self) -> None:
        """Record a show call."""

        self.visible = True

    def hide(self) -> None:
        """Record a hide call."""

        self.visible = False


class _ValueWidget:
    """Record integer value updates."""

    def __init__(self) -> None:
        """Initialize an unset value."""

        self.value: int | None = None

    def setValue(self, value: int) -> None:  # noqa: N802
        """Record a value update."""

        self.value = value

    def setUseAni(self, _isUSe: bool) -> None:  # noqa: N802
        """Accept qfluent animation policy updates."""

    def isUseAni(self) -> bool:  # noqa: N802
        """Return that animation is enabled by default."""

        return True


class _TaskbarPresenter:
    """Record taskbar progress presenter calls."""

    def __init__(self) -> None:
        """Initialize an empty taskbar call list."""

        self.calls: list[tuple[str, int | None]] = []

    def set_progress(self, percent: int) -> None:
        """Record taskbar progress updates."""

        self.calls.append(("set", percent))

    def clear_progress(self) -> None:
        """Record taskbar progress clearing."""

        self.calls.append(("clear", None))


class _GenerationActionCluster:
    """Titlebar generation action cluster stub."""

    def __init__(self) -> None:
        """Initialize captured presentation updates."""

        self.presentation_updates: list[GenerationActionPresentation] = []

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Record one complete generation action presentation snapshot."""

        self.presentation_updates.append(presentation)


def test_generation_output_image_submits_to_output_pipeline(tmp_path: Path) -> None:
    """Generation output callback should forward strict live events unchanged."""

    submitted: list[object] = []
    shell = SimpleNamespace(
        output_image_pipeline=SimpleNamespace(submit_live_output_event=submitted.append)
    )
    output_update = _live_output(tmp_path)

    GenerationFeedbackPresenter(shell).apply_generation_output_image(output_update)

    assert submitted == [output_update]


def test_generation_failure_appends_shell_output_line() -> None:
    """Generation failures should also surface one shell-visible output line."""

    appended_lines: list[str] = []
    taskbar = _TaskbarPresenter()
    presented_reports: list[object] = []
    shell = _progress_surface_fake(
        _comfy_output_stream=SimpleNamespace(
            append_line=lambda line: appended_lines.append(line)
        ),
        _taskbar_progress_presenter=taskbar,
        _error_presenter=SimpleNamespace(
            show_error_report=lambda report: presented_reports.append(report)
        ),
    )
    failure = GenerationFailure(
        stage="queue",
        workflow_id="wf-1",
        message="queue_prompt did not return prompt_id",
        prompt_id="prompt-123",
    )

    GenerationFeedbackPresenter(shell).apply_generation_failure(failure)

    assert appended_lines == [
        "Generation failed during queue: "
        "queue_prompt did not return prompt_id prompt_id=prompt-123"
    ]
    assert taskbar.calls == [("clear", None)]
    assert shell.progressOverlay.visible is False
    assert presented_reports == []


def test_generation_failure_presents_structured_error_report() -> None:
    """Generation failures with structured reports should open the error modal path."""

    appended_lines: list[str] = []
    presented_reports: list[object] = []
    shell = _progress_surface_fake(
        _comfy_output_stream=SimpleNamespace(
            append_line=lambda line: appended_lines.append(line)
        ),
        _taskbar_progress_presenter=_TaskbarPresenter(),
        _error_presenter=SimpleNamespace(
            show_error_report=lambda report: presented_reports.append(report)
        ),
    )
    report = ErrorReport(
        kind=ErrorReportKind.EXECUTION,
        title="KSampler failed",
        message="CUDA out of memory",
        stage="listen",
    )
    failure = GenerationFailure(
        stage="listen",
        workflow_id="wf-1",
        message="CUDA out of memory",
        prompt_id="prompt-123",
        error_report=report,
    )

    GenerationFeedbackPresenter(shell).apply_generation_failure(failure)

    assert appended_lines == [
        "Generation failed during listen: CUDA out of memory prompt_id=prompt-123"
    ]
    assert presented_reports == [report]


def test_detached_shell_ignores_stale_generation_availability_callbacks() -> None:
    """Old shells should not touch deleted titlebar controls after GUI reload."""

    calls: list[str] = []
    shell = SimpleNamespace(
        _detached_for_gui_reload=True,
        generationActionCluster=SimpleNamespace(
            apply_generation_presentation=lambda _presentation: calls.append(
                "availability"
            )
        ),
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert calls == []


def test_generation_action_availability_fans_out_through_registry() -> None:
    """Registry should receive shell generation presentation when attached."""

    registry_presentations: list[GenerationActionPresentation] = []
    cluster = _GenerationActionCluster()
    shell = SimpleNamespace(
        _detached_for_gui_reload=False,
        generationActionCluster=cluster,
        generation_titlebar_control_registry=SimpleNamespace(
            apply_generation_presentation=registry_presentations.append
        ),
        _backend_state="ready",
        _current_generate_mode="generate",
        _active_workspace_route="wf-a",
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": SimpleNamespace(cubes={"Cube": object()})},
        ),
        workspace_generation_controller=SimpleNamespace(is_continuous_active=False),
        generation_job_queue_service=SimpleNamespace(
            has_active_job=lambda: False,
            has_cancellable_jobs=lambda: False,
            jobs=lambda: (),
        ),
        shell_layout_controller=SimpleNamespace(
            current_generation_queue_panel_visible=lambda: False
        ),
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert len(registry_presentations) == 1
    assert registry_presentations[0].play_enabled is True
    assert cluster.presentation_updates == []


def _live_output(tmp_path: Path) -> LiveFinalOutputEvent:
    """Build a strict live output event for presenter tests."""

    return LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf1",
            generation_run_id="run-output",
            prompt_id="prompt-output",
            client_id="client-output",
            source_key="wf1:N1",
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


def _progress_surface_fake(**kwargs: object) -> SimpleNamespace:
    """Return fake shell progress widgets and taskbar presenter."""

    workflow_progress_service = WorkflowProgressService()
    workflow_progress_service.register_run(
        GenerationRunStarted(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
        )
    )
    values: dict[str, object] = {
        "active_editor_panel": None,
        "editor_panels": {},
        "generation_progress_strip_registry": None,
        "workflow_session_service": SimpleNamespace(active_workflow_id="wf-1"),
        "workflow_progress_service": workflow_progress_service,
        "workspace_controller": None,
        "progressOverlay": _VisibleWidget(),
        "workflowOverlayBar": _ValueWidget(),
        "samplerOverlayBar": _ValueWidget(),
        "_taskbar_progress_presenter": _TaskbarPresenter(),
        "_comfy_output_stream": SimpleNamespace(append_line=lambda _line: None),
        "_error_presenter": None,
    }
    values.update(kwargs)
    shell = SimpleNamespace(**values)
    shell.progress_overlay_controller = SimpleNamespace(
        position_progress_overlay=lambda: None
    )
    shell.generation_action_controller = GenerationActionController(shell)
    return shell
