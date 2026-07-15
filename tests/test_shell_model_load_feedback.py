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

"""Tests for shell model-load feedback projection."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from _pytest.logging import LogCaptureFixture

from substitute.application.generation import (
    GenerationFailure,
    GenerationRunStarted,
    WorkflowProgressService,
)
from substitute.application.generation.progress_service import ProgressService
from substitute.application.ports import (
    ListenerCompleted,
    ModelLoadProgressUpdate,
    ProgressUpdate,
)
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
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
        """Initialize unset value and animation state."""

        self.value: int | None = None
        self.calls: list[int] = []

    def setValue(self, value: int) -> None:  # noqa: N802
        """Record a value update."""

        self.value = value
        self.calls.append(value)

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


def test_model_load_progress_routes_to_source_model_picker(
    caplog: LogCaptureFixture,
) -> None:
    """Source-enriched model-load progress should update the owning editor panel."""

    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.shell.generation_feedback_presenter",
    )
    calls: list[dict[str, object]] = []
    panel = SimpleNamespace(
        set_model_field_load_progress=lambda **kwargs: calls.append(kwargs)
    )
    shell = _feedback_shell(
        editor_panels={"wf-1": panel},
        progress_service=SimpleNamespace(
            build_model_load_view_state=lambda **_kwargs: SimpleNamespace(
                show_overlay=True,
                value=42,
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
    assert "Routing model-load telemetry to editor field" in caplog.text
    assert "workflow_id=wf-1" in caplog.text
    assert "source_node_id=2" in caplog.text
    assert "field_key=ckpt_name" in caplog.text


def test_model_load_progress_ignores_unenriched_or_inactive_workflow_events(
    caplog: LogCaptureFixture,
) -> None:
    """Model-load progress should not route without explicit editor source metadata."""

    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.shell.generation_feedback_presenter",
    )
    calls: list[dict[str, object]] = []
    shell = _feedback_shell(
        editor_panels={
            "wf-1": SimpleNamespace(
                set_model_field_load_progress=lambda **kwargs: calls.append(kwargs)
            )
        },
        progress_service=SimpleNamespace(
            build_model_load_view_state=lambda **_kwargs: SimpleNamespace(
                show_overlay=True,
                value=42,
                display_percent=42.0,
            )
        ),
    )

    GenerationFeedbackPresenter(shell).apply_generation_model_load_progress(
        _model_load_update(
            source_node_id=None,
            source_input_key=None,
            source_cube_alias=None,
            source_workflow_node_name=None,
        )
    )
    GenerationFeedbackPresenter(shell).apply_generation_model_load_progress(
        _model_load_update(workflow_id="wf-missing")
    )

    assert calls == []
    assert "Ignoring model-load telemetry without editor source metadata" in caplog.text
    assert "Ignoring model-load telemetry for missing editor panel" in caplog.text


def test_dynamic_model_load_progress_holds_until_sampler_progress(
    caplog: LogCaptureFixture,
) -> None:
    """Dynamic staging completion should stay visible until sampler work starts."""

    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.shell.generation_feedback_presenter",
    )
    field_calls: list[dict[str, object]] = []
    clear_calls: list[str] = []
    panel = SimpleNamespace(
        set_model_field_load_progress=lambda **kwargs: field_calls.append(kwargs),
        clear_model_field_load_progress=lambda: clear_calls.append("cleared"),
    )
    shell = _progress_surface_fake(
        editor_panels={"wf-1": panel},
        progress_service=ProgressService(),
    )

    GenerationFeedbackPresenter(shell).apply_generation_model_load_progress(
        _model_load_update(percent=100.0, state="running")
    )
    GenerationFeedbackPresenter(shell).apply_generation_model_load_progress(
        _model_load_update(percent=100.0, state="finished")
    )
    GenerationActionController(shell).apply_generation_progress(
        _progress_update(workflow_percent=80.0, sampler_percent=3.5),
    )

    assert field_calls == [
        {
            "cube_alias": "Cube",
            "node_name": "checkpoint",
            "field_key": "ckpt_name",
            "percent": 99.0,
            "active": True,
        }
    ]
    assert clear_calls == ["cleared"]
    assert shell.workflowOverlayBar.calls == [80]
    assert shell.samplerOverlayBar.calls == [3]
    assert "Deferring dynamic model-load progress clear" in caplog.text


def test_sampler_progress_clears_model_load_fields_once() -> None:
    """Sampler progress should preserve accuracy while avoiding repeated field clears."""

    clear_calls: list[str] = []
    panel = SimpleNamespace(
        clear_model_field_load_progress=lambda: clear_calls.append("cleared"),
    )
    shell = _progress_surface_fake(
        editor_panels={"wf-1": panel},
        progress_service=ProgressService(),
    )

    controller = GenerationActionController(shell)
    controller.apply_generation_progress(
        _progress_update(workflow_percent=10.0, sampler_percent=1.0),
    )
    controller.apply_generation_progress(
        _progress_update(workflow_percent=20.0, sampler_percent=2.0),
    )

    assert clear_calls == ["cleared"]
    assert shell.workflowOverlayBar.calls == [10, 20]
    assert shell.samplerOverlayBar.calls == [1, 2]


def test_generation_failure_and_start_clear_model_field_progress() -> None:
    """Generation lifecycle cleanup should clear stale model picker progress."""

    clear_calls: list[str] = []
    taskbar = _TaskbarPresenter()
    shell = _progress_surface_fake(
        editor_panels={
            "wf-1": SimpleNamespace(
                clear_model_field_load_progress=lambda: clear_calls.append("wf-1")
            )
        },
        output_canvas_projection_coordinator=SimpleNamespace(
            clear_output_for_workflow=lambda _workflows, workflow_id: (
                clear_calls.append(f"output:{workflow_id}")
            )
        ),
        workflow_session_service=SimpleNamespace(workflows={}),
        _taskbar_progress_presenter=taskbar,
        _comfy_output_stream=SimpleNamespace(append_line=lambda _line: None),
    )

    presenter = GenerationFeedbackPresenter(shell)
    presenter.clear_output_for_workflow("wf-1")
    presenter.apply_generation_failure(
        GenerationFailure(stage="listen", workflow_id="wf-1", message="failed"),
    )

    assert clear_calls == ["wf-1", "output:wf-1", "wf-1"]
    assert shell.progressOverlay.visible is False
    assert taskbar.calls == [("clear", None)]


def test_generation_completion_keeps_preview_until_final_projection() -> None:
    """Completion must not uncover stale outputs while final output is pending."""

    clear_calls: list[str] = []
    model_clear_calls: list[str] = []
    taskbar_clear_calls: list[bool] = []
    shell = _feedback_shell(
        editor_panels={
            "wf-1": SimpleNamespace(
                clear_model_field_load_progress=lambda: model_clear_calls.append("wf-1")
            )
        },
        workspace_controller=SimpleNamespace(
            clear_output_previews=lambda workflow_id: clear_calls.append(workflow_id)
        ),
        _taskbar_progress_presenter=SimpleNamespace(
            clear_progress=lambda: taskbar_clear_calls.append(True)
        ),
    )

    GenerationFeedbackPresenter(shell).apply_generation_completed(
        ListenerCompleted(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )

    assert model_clear_calls == ["wf-1"]
    assert clear_calls == []
    assert taskbar_clear_calls == [True]


def _model_load_update(
    *,
    workflow_id: str = "wf-1",
    source_node_id: str | None = "2",
    source_input_key: str | None = "ckpt_name",
    source_cube_alias: str | None = "Cube",
    source_workflow_node_name: str | None = "checkpoint",
    percent: float | None = 42.5,
    state: str = "running",
) -> ModelLoadProgressUpdate:
    """Build model-load progress for presenter tests."""

    return ModelLoadProgressUpdate(
        workflow_id=workflow_id,
        prompt_id="pid-1",
        node_id="4",
        display_node_id="4",
        phase="dynamic_vram_staging",
        state=state,
        percent=percent,
        value=2048.0,
        maximum=4897.0,
        unit="bytes",
        model_class="SDXL",
        model_name="example.safetensors",
        source_node_id=source_node_id,
        source_input_key=source_input_key,
        source_cube_alias=source_cube_alias,
        source_workflow_node_name=source_workflow_node_name,
        detail=None,
    )


def _progress_update(
    *,
    workflow_id: str = "wf-1",
    generation_run_id: str = "run-1",
    prompt_id: str = "pid-1",
    client_id: str = "client-1",
    workflow_percent: float | None,
    sampler_percent: float | None,
) -> ProgressUpdate:
    """Return one identity-bearing progress update for shell tests."""

    return ProgressUpdate(
        workflow_id=workflow_id,
        generation_run_id=generation_run_id,
        prompt_id=prompt_id,
        client_id=client_id,
        workflow_percent=workflow_percent,
        sampler_percent=sampler_percent,
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
        "generation_progress_strip_registry": None,
        "workflow_session_service": SimpleNamespace(active_workflow_id="wf-1"),
        "workflow_progress_service": workflow_progress_service,
        "progressOverlay": _VisibleWidget(),
        "workflowOverlayBar": _ValueWidget(),
        "samplerOverlayBar": _ValueWidget(),
        "_taskbar_progress_presenter": _TaskbarPresenter(),
    }
    values.update(kwargs)
    shell = SimpleNamespace(**values)
    shell.progress_overlay_controller = SimpleNamespace(
        position_progress_overlay=lambda: None
    )
    shell.generation_action_controller = GenerationActionController(shell)
    return shell


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
        "progress_service": SimpleNamespace(
            build_model_load_view_state=lambda **_kwargs: SimpleNamespace(
                show_overlay=False,
                display_percent=None,
            )
        ),
        "clear_output_signal": SimpleNamespace(emit=lambda _workflow_id: None),
    }
    values.update(overrides)
    return SimpleNamespace(**values)
