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

"""Tests for shell progress feedback projection."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from substitute.application.generation import (
    GenerationRunStarted,
    WorkflowProgressService,
)
from substitute.application.generation.progress_service import ProgressViewState
from substitute.application.ports import ProgressUpdate
from substitute.presentation.shell.canvas_route_controller import CanvasRouteController
from substitute.presentation.shell.comfy_runtime_actions import ComfyRuntimeActions
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.progress_projection import ProgressProjectionMode
from substitute.presentation.shell.shell_layout_controller import ShellLayoutController
from substitute.presentation.shell.workflow_surface_reconciler import (
    ActiveWorkflowSurfaceRefresher,
)


class _VisibleWidget:
    """Record visibility updates."""

    def __init__(self) -> None:
        """Initialize an unset visibility state."""

        self.visible: bool | None = None
        self.calls: list[str] = []

    def show(self) -> None:
        """Record a show call."""

        self.visible = True
        self.calls.append("show")

    def hide(self) -> None:
        """Record a hide call."""

        self.visible = False
        self.calls.append("hide")


class _ValueWidget:
    """Record integer value updates."""

    def __init__(self) -> None:
        """Initialize unset value and animation state."""

        self.value: int | None = None
        self.calls: list[int] = []
        self.animation_enabled = True
        self.animation_calls: list[bool] = []

    def setValue(self, value: int) -> None:  # noqa: N802
        """Record a value update."""

        self.value = value
        self.calls.append(value)

    def setUseAni(self, isUSe: bool) -> None:  # noqa: N802
        """Record qfluent animation policy updates."""

        self.animation_enabled = isUSe
        self.animation_calls.append(isUSe)

    def isUseAni(self) -> bool:  # noqa: N802
        """Return the current fake qfluent animation policy."""

        return self.animation_enabled


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


def _progress_view(
    *,
    show_overlay: bool,
    workflow_value: int,
    sampler_value: int,
    active: bool | None = None,
) -> SimpleNamespace:
    """Return a progress-view stub with lifecycle fields."""

    return SimpleNamespace(
        show_overlay=show_overlay,
        workflow_value=workflow_value,
        sampler_value=sampler_value,
        active=show_overlay if active is None else active,
        workflow_id=None,
        generation_run_id=None,
        prompt_id=None,
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
    fake = SimpleNamespace(**values)
    fake.progress_overlay_controller = SimpleNamespace(
        position_progress_overlay=lambda: None
    )
    fake.generation_action_controller = GenerationActionController(fake)
    return fake


def _attach_shell_layout_controller(fake: SimpleNamespace) -> SimpleNamespace:
    """Attach the composed shell layout controller expected by layout methods."""

    fake.shell_layout_controller = ShellLayoutController(fake)
    if not hasattr(fake, "generation_action_controller"):
        fake.generation_action_controller = GenerationActionController(fake)
    if not hasattr(fake, "active_workflow_surface_refresher"):
        fake.active_workflow_surface_refresher = ActiveWorkflowSurfaceRefresher(fake)
    if not hasattr(fake, "comfy_runtime_actions"):
        fake.comfy_runtime_actions = ComfyRuntimeActions(fake)
    if not hasattr(fake, "canvas_route_controller"):
        fake.canvas_route_controller = CanvasRouteController(fake)
    return fake


def test_update_progress_labels_updates_overlay_bars_and_taskbar() -> None:
    """Progress view state should drive overlay bars and taskbar together."""

    taskbar = _TaskbarPresenter()
    fake = SimpleNamespace(
        progress_service=SimpleNamespace(
            build_view_state=lambda **_kwargs: _progress_view(
                show_overlay=True,
                workflow_value=33,
                sampler_value=44,
            )
        ),
        progressOverlay=_VisibleWidget(),
        workflowOverlayBar=_ValueWidget(),
        samplerOverlayBar=_ValueWidget(),
        _taskbar_progress_presenter=taskbar,
    )
    position_calls: list[str] = []
    fake.progress_overlay_controller = SimpleNamespace(
        position_progress_overlay=lambda: position_calls.append("position")
    )
    fake = _attach_shell_layout_controller(fake)

    GenerationActionController(fake).update_progress_labels(33.0, 44.0)

    assert position_calls == ["position"]
    assert fake.progressOverlay.visible is True
    assert fake.workflowOverlayBar.value == 33
    assert fake.samplerOverlayBar.value == 44
    assert taskbar.calls == [("set", 33)]


def test_update_progress_labels_fans_out_to_progress_registry() -> None:
    """Floating progress strips should receive the same projected progress view."""

    taskbar = _TaskbarPresenter()
    progress_view = _progress_view(
        show_overlay=True,
        workflow_value=33,
        sampler_value=44,
    )
    registry_views: list[object] = []
    registry_modes: list[ProgressProjectionMode] = []

    def apply_progress_view(
        view: object,
        *,
        mode: ProgressProjectionMode,
    ) -> None:
        """Record progress registry projection calls."""

        registry_views.append(view)
        registry_modes.append(mode)

    fake = SimpleNamespace(
        progress_service=SimpleNamespace(
            build_view_state=lambda **_kwargs: progress_view
        ),
        generation_progress_strip_registry=SimpleNamespace(
            apply_progress_view=apply_progress_view
        ),
        progressOverlay=_VisibleWidget(),
        workflowOverlayBar=_ValueWidget(),
        samplerOverlayBar=_ValueWidget(),
        _taskbar_progress_presenter=taskbar,
    )
    fake.progress_overlay_controller = SimpleNamespace(
        position_progress_overlay=lambda: None
    )
    fake = _attach_shell_layout_controller(fake)

    GenerationActionController(fake).update_progress_labels(33.0, 44.0)

    assert registry_views == [progress_view]
    assert registry_modes == [ProgressProjectionMode.LIVE_UPDATE]
    assert fake.workflowOverlayBar.value == 33
    assert taskbar.calls == [("set", 33)]


def test_update_progress_labels_skips_duplicate_visible_state() -> None:
    """Duplicate progress states should not rewrite unchanged progress widgets."""

    taskbar = _TaskbarPresenter()
    fake = SimpleNamespace(
        progress_service=SimpleNamespace(
            build_view_state=lambda **_kwargs: _progress_view(
                show_overlay=True,
                workflow_value=33,
                sampler_value=44,
            )
        ),
        progressOverlay=_VisibleWidget(),
        workflowOverlayBar=_ValueWidget(),
        samplerOverlayBar=_ValueWidget(),
        _taskbar_progress_presenter=taskbar,
    )
    position_calls: list[str] = []
    fake.progress_overlay_controller = SimpleNamespace(
        position_progress_overlay=lambda: position_calls.append("position")
    )
    fake = _attach_shell_layout_controller(fake)

    controller = GenerationActionController(fake)
    controller.update_progress_labels(33.0, 44.0)
    controller.update_progress_labels(33.0, 44.0)

    assert position_calls == ["position"]
    assert fake.progressOverlay.calls == ["show"]
    assert fake.workflowOverlayBar.calls == [33]
    assert fake.samplerOverlayBar.calls == [44]
    assert taskbar.calls == [("set", 33)]


def test_update_progress_labels_replays_duplicate_state_to_progress_registry() -> None:
    """Duplicate progress states should still keep late floating strips current."""

    taskbar = _TaskbarPresenter()
    progress_view = _progress_view(
        show_overlay=True,
        workflow_value=33,
        sampler_value=44,
    )
    registry_views: list[object] = []
    registry_modes: list[ProgressProjectionMode] = []

    def apply_progress_view(
        view: object,
        *,
        mode: ProgressProjectionMode,
    ) -> None:
        """Record progress registry projection calls."""

        registry_views.append(view)
        registry_modes.append(mode)

    fake = SimpleNamespace(
        progress_service=SimpleNamespace(
            build_view_state=lambda **_kwargs: progress_view
        ),
        generation_progress_strip_registry=SimpleNamespace(
            apply_progress_view=apply_progress_view
        ),
        progressOverlay=_VisibleWidget(),
        workflowOverlayBar=_ValueWidget(),
        samplerOverlayBar=_ValueWidget(),
        _taskbar_progress_presenter=taskbar,
    )
    fake.progress_overlay_controller = SimpleNamespace(
        position_progress_overlay=lambda: None
    )
    fake = _attach_shell_layout_controller(fake)

    controller = GenerationActionController(fake)
    controller.update_progress_labels(33.0, 44.0)
    controller.update_progress_labels(33.0, 44.0)

    assert registry_views == [progress_view, progress_view]
    assert registry_modes == [
        ProgressProjectionMode.LIVE_UPDATE,
        ProgressProjectionMode.LIVE_UPDATE,
    ]
    assert fake.workflowOverlayBar.calls == [33]
    assert taskbar.calls == [("set", 33)]


def test_inactive_workflow_progress_is_stored_without_showing_overlay() -> None:
    """Progress for an inactive workflow should wait for workflow selection."""

    fake = _progress_surface_fake()
    fake.workflow_progress_service.register_run(
        GenerationRunStarted(
            workflow_id="wf-2",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )

    GenerationActionController(fake).apply_generation_progress(
        _progress_update(
            workflow_id="wf-2",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
            workflow_percent=45.0,
            sampler_percent=4.0,
        ),
    )

    assert fake.workflowOverlayBar.calls == []
    assert fake.samplerOverlayBar.calls == []
    assert fake.progressOverlay.calls == []
    assert fake.workflow_progress_service.view_for_workflow("wf-2").workflow_value == 45


def test_project_active_workflow_progress_replays_selected_workflow_state() -> None:
    """Selecting a workflow should project its stored progress state."""

    fake = _progress_surface_fake()
    fake.workflow_progress_service.register_run(
        GenerationRunStarted(
            workflow_id="wf-2",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )
    fake.workflow_progress_service.apply_update(
        _progress_update(
            workflow_id="wf-2",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
            workflow_percent=45.0,
            sampler_percent=4.0,
        )
    )

    fake.workflow_session_service.active_workflow_id = "wf-2"
    GenerationActionController(fake).project_active_workflow_progress()

    assert fake.progressOverlay.visible is True
    assert fake.workflowOverlayBar.calls == [45]
    assert fake.samplerOverlayBar.calls == [4]
    assert fake.workflowOverlayBar.animation_calls == [False, True]
    assert fake.samplerOverlayBar.animation_calls == [False, True]


def test_live_progress_updates_keep_progress_bar_animation_enabled() -> None:
    """Live progress should not suppress qfluent value animation."""

    fake = _progress_surface_fake()

    GenerationActionController(fake).apply_generation_progress(
        _progress_update(workflow_percent=45.0, sampler_percent=4.0),
    )

    assert fake.workflowOverlayBar.calls == [45]
    assert fake.samplerOverlayBar.calls == [4]
    assert fake.workflowOverlayBar.animation_calls == []
    assert fake.samplerOverlayBar.animation_calls == []


def test_project_active_workflow_progress_hides_missing_workflow_state() -> None:
    """Selecting a workflow with no progress should hide progress surfaces."""

    fake = _progress_surface_fake()
    fake.workflow_progress_service.apply_update(
        _progress_update(workflow_percent=45.0, sampler_percent=4.0)
    )
    controller = GenerationActionController(fake)
    controller.project_active_workflow_progress()

    fake.workflow_session_service.active_workflow_id = "wf-missing"
    controller.project_active_workflow_progress()

    assert fake.progressOverlay.visible is False
    assert fake.workflowOverlayBar.value == 0
    assert fake.samplerOverlayBar.value == 0


def test_inactive_workflow_retirement_does_not_clear_active_progress() -> None:
    """A hidden state for another workflow should reproject selected progress."""

    fake = _progress_surface_fake()
    fake.workflow_progress_service.apply_update(
        _progress_update(workflow_percent=45.0, sampler_percent=4.0)
    )
    GenerationActionController(fake).project_active_workflow_progress()

    GenerationActionController(fake).apply_generation_progress_state(
        ProgressViewState.hidden(
            workflow_id="wf-2",
            generation_run_id="run-2",
            prompt_id="pid-2",
        ),
    )

    assert fake.progressOverlay.visible is True
    assert fake.workflowOverlayBar.value == 45
    assert fake.samplerOverlayBar.value == 4


def test_active_workflow_retirement_hides_active_progress() -> None:
    """A hidden state for the selected workflow should clear progress surfaces."""

    fake = _progress_surface_fake()
    fake.workflow_progress_service.apply_update(
        _progress_update(workflow_percent=45.0, sampler_percent=4.0)
    )
    GenerationActionController(fake).project_active_workflow_progress()

    GenerationActionController(fake).apply_generation_progress_state(
        ProgressViewState.hidden(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
        ),
    )

    assert fake.progressOverlay.visible is False
    assert fake.workflowOverlayBar.value == 0
    assert fake.samplerOverlayBar.value == 0


def test_update_progress_labels_clears_taskbar_when_progress_is_not_visible() -> None:
    """Complete or absent progress should clear taskbar progress."""

    taskbar = _TaskbarPresenter()
    fake = SimpleNamespace(
        progress_service=SimpleNamespace(
            build_view_state=lambda **_kwargs: _progress_view(
                show_overlay=False,
                workflow_value=100,
                sampler_value=0,
                active=False,
            )
        ),
        progressOverlay=_VisibleWidget(),
        workflowOverlayBar=_ValueWidget(),
        samplerOverlayBar=_ValueWidget(),
        _taskbar_progress_presenter=taskbar,
    )
    fake = _attach_shell_layout_controller(fake)

    GenerationActionController(fake).update_progress_labels(100.0, None)

    assert fake.progressOverlay.visible is False
    assert taskbar.calls == [("clear", None)]


def test_clear_generation_progress_hides_progress_surfaces() -> None:
    """Generation progress clearing should apply hidden presentation state."""

    taskbar = _TaskbarPresenter()
    registry_views: list[Any] = []
    registry_modes: list[ProgressProjectionMode] = []

    def apply_progress_view(
        view: Any,
        *,
        mode: ProgressProjectionMode,
    ) -> None:
        """Record progress registry projection calls."""

        registry_views.append(view)
        registry_modes.append(mode)

    fake = SimpleNamespace(
        generation_progress_strip_registry=SimpleNamespace(
            apply_progress_view=apply_progress_view
        ),
        progressOverlay=_VisibleWidget(),
        workflowOverlayBar=_ValueWidget(),
        samplerOverlayBar=_ValueWidget(),
        _taskbar_progress_presenter=taskbar,
        _last_progress_view_state=(
            True,
            True,
            43,
            12,
            "wf",
            "run-1",
            "pid-1",
        ),
    )
    fake.generation_action_controller = GenerationActionController(fake)

    GenerationActionController(fake).clear_generation_progress()

    assert fake.progressOverlay.visible is False
    assert fake.workflowOverlayBar.value == 0
    assert fake.samplerOverlayBar.value == 0
    assert taskbar.calls == [("clear", None)]
    assert registry_views[-1].show_overlay is False
    assert registry_modes[-1] is ProgressProjectionMode.CLEAR
    assert fake.workflowOverlayBar.animation_calls == [False, True]
    assert fake.samplerOverlayBar.animation_calls == [False, True]
