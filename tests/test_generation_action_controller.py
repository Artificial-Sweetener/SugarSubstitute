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

"""Cover generation progress projection outside MainWindow."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.generation import GenerationRunStarted
from substitute.application.generation.progress_service import (
    ProgressService,
    ProgressViewState,
)
from substitute.application.generation.workflow_progress_service import (
    WorkflowProgressService,
)
from substitute.application.ports import ProgressUpdate
from substitute.presentation.shell.generation_action_controller import (
    GenerationActionController,
)
from substitute.presentation.shell.generation_action_state import (
    GenerationActionPresentation,
)
from substitute.presentation.shell.progress_projection import ProgressProjectionMode


class _VisibleWidget:
    """Record visibility updates."""

    def __init__(self) -> None:
        """Initialize visibility state."""

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
        """Initialize value and animation state."""

        self.value: int | None = None
        self.calls: list[int] = []
        self.animation_enabled = True
        self.animation_calls: list[bool] = []

    def setValue(self, value: int) -> None:
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
        """Initialize recorded calls."""

        self.calls: list[tuple[str, int | None]] = []

    def set_progress(self, percent: int) -> None:
        """Record taskbar progress updates."""

        self.calls.append(("set", percent))

    def clear_progress(self) -> None:
        """Record taskbar progress clearing."""

        self.calls.append(("clear", None))


class _Signal:
    """Record shell signal emissions."""

    def __init__(self) -> None:
        """Initialize emitted values."""

        self.emitted: list[object] = []

    def emit(self, value: object) -> None:
        """Record one emitted value."""

        self.emitted.append(value)


class _GenerationActionCluster:
    """Titlebar generation action cluster stub."""

    def __init__(self) -> None:
        """Initialize recorded presentation updates."""

        self.availability_updates: list[dict[str, bool]] = []
        self.queue_badge_count_updates: list[int] = []
        self.queue_segment_visible_updates: list[bool] = []
        self.presentation_updates: list[GenerationActionPresentation] = []

    def apply_generation_presentation(
        self,
        presentation: GenerationActionPresentation,
    ) -> None:
        """Record one complete generation action presentation snapshot."""

        self.presentation_updates.append(presentation)
        self.availability_updates.append(
            {
                "can_generate": presentation.play_enabled,
                "can_skip": presentation.skip_enabled,
                "can_stop": presentation.stop_enabled,
                "can_show_queue": presentation.queue_primary_enabled,
            }
        )
        self.queue_badge_count_updates.append(presentation.queue_badge_count)
        self.queue_segment_visible_updates.append(presentation.queue_segment_visible)


def test_update_progress_labels_updates_overlay_bars_and_taskbar() -> None:
    """Progress view state should drive overlay bars and taskbar together."""

    shell = _progress_surface_fake()
    position_calls: list[str] = []
    shell.progress_overlay_controller = SimpleNamespace(
        position_progress_overlay=lambda: position_calls.append("position")
    )
    shell.progress_service = ProgressService()

    GenerationActionController(shell).update_progress_labels(33.0, 44.0)

    assert position_calls == ["position"]
    assert shell.progressOverlay.visible is True
    assert shell.workflowOverlayBar.value == 33
    assert shell.samplerOverlayBar.value == 44
    assert shell._taskbar_progress_presenter.calls == [("set", 33)]


def test_duplicate_progress_state_still_replays_to_progress_registry() -> None:
    """Duplicate progress states should still keep late floating strips current."""

    progress_view = ProgressViewState(
        show_overlay=True,
        workflow_value=33,
        sampler_value=44,
    )
    registry_views: list[ProgressViewState] = []
    registry_modes: list[ProgressProjectionMode] = []

    def apply_progress_view(
        view: ProgressViewState,
        *,
        mode: ProgressProjectionMode,
    ) -> None:
        """Record registry progress projection."""

        registry_views.append(view)
        registry_modes.append(mode)

    shell = _progress_surface_fake(
        generation_progress_strip_registry=SimpleNamespace(
            apply_progress_view=apply_progress_view
        )
    )
    controller = GenerationActionController(shell)

    controller.apply_generation_progress_state(progress_view)
    controller.apply_generation_progress_state(progress_view)

    assert registry_views == [progress_view, progress_view]
    assert registry_modes == [
        ProgressProjectionMode.LIVE_UPDATE,
        ProgressProjectionMode.LIVE_UPDATE,
    ]
    assert shell.workflowOverlayBar.calls == [33]
    assert shell._taskbar_progress_presenter.calls == [("set", 33)]


def test_project_active_workflow_progress_replays_selected_workflow_state() -> None:
    """Selecting a workflow should project its stored progress state."""

    shell = _progress_surface_fake()
    shell.workflow_progress_service.apply_update(
        _progress_update(
            workflow_id="wf-1",
            workflow_percent=45.0,
            sampler_percent=4.0,
        )
    )

    GenerationActionController(shell).project_active_workflow_progress()

    assert shell.progressOverlay.visible is True
    assert shell.workflowOverlayBar.calls == [45]
    assert shell.samplerOverlayBar.calls == [4]
    assert shell.workflowOverlayBar.animation_calls == [False, True]
    assert shell.samplerOverlayBar.animation_calls == [False, True]


def test_clear_generation_progress_hides_progress_surfaces() -> None:
    """Generation progress clearing should apply hidden presentation state."""

    registry_views: list[ProgressViewState] = []
    registry_modes: list[ProgressProjectionMode] = []

    def apply_progress_view(
        view: ProgressViewState,
        *,
        mode: ProgressProjectionMode,
    ) -> None:
        """Record registry progress projection."""

        registry_views.append(view)
        registry_modes.append(mode)

    shell = _progress_surface_fake(
        generation_progress_strip_registry=SimpleNamespace(
            apply_progress_view=apply_progress_view
        )
    )

    GenerationActionController(shell).clear_generation_progress()

    assert shell.progressOverlay.visible is False
    assert shell.workflowOverlayBar.value == 0
    assert shell.samplerOverlayBar.value == 0
    assert shell._taskbar_progress_presenter.calls == [("clear", None)]
    assert registry_views[-1].show_overlay is False
    assert registry_modes[-1] is ProgressProjectionMode.CLEAR


def test_sampler_progress_clears_model_load_fields_once() -> None:
    """Sampler progress should preserve accuracy while avoiding repeated field clears."""

    clear_calls: list[str] = []
    cleared = False

    def clear_once() -> None:
        """Record the first sampler cleanup request only."""

        nonlocal cleared
        if cleared:
            return
        cleared = True
        clear_calls.append("cleared")

    shell = _progress_surface_fake(
        editor_panels={
            "wf-1": SimpleNamespace(clear_model_field_load_progress=clear_once)
        },
    )
    controller = GenerationActionController(shell)

    controller.apply_generation_progress(
        _progress_update(workflow_percent=10.0, sampler_percent=1.0)
    )
    controller.apply_generation_progress(
        _progress_update(workflow_percent=20.0, sampler_percent=2.0)
    )

    assert clear_calls == ["cleared"]
    assert shell.workflowOverlayBar.calls == [10, 20]
    assert shell.samplerOverlayBar.calls == [1, 2]


def test_set_generation_selected_mode_projects_expected_button_state() -> None:
    """Generate mode selection should project titlebar state snapshots."""

    cluster = _GenerationActionCluster()
    shell = _generation_action_shell(cluster=cluster)
    controller = GenerationActionController(shell)

    controller.set_generation_selected_mode("generate")
    assert getattr(shell, "_current_generate_mode") == "generate"
    assert str(cluster.presentation_updates[-1].play_mode) == "generate"

    controller.set_generation_selected_mode("continuous")
    assert getattr(shell, "_current_generate_mode") == "continuous"
    assert str(cluster.presentation_updates[-1].play_mode) == "continuous"

    assert cluster.availability_updates == [
        {
            "can_generate": True,
            "can_skip": False,
            "can_stop": False,
            "can_show_queue": False,
        },
        {
            "can_generate": True,
            "can_skip": False,
            "can_stop": False,
            "can_show_queue": False,
        },
    ]


def test_set_backend_state_disables_generation_until_ready() -> None:
    """Backend-starting state should disable generation controls."""

    cluster = _GenerationActionCluster()
    availability: list[bool] = []
    shell = _generation_action_shell(
        cluster=cluster,
        set_backend_available=lambda available, **_kwargs: availability.append(
            available
        ),
    )
    controller = GenerationActionController(shell)

    controller.set_backend_state("starting")

    assert availability == [False]
    assert cluster.availability_updates[-1] == {
        "can_generate": False,
        "can_skip": False,
        "can_stop": False,
        "can_show_queue": False,
    }

    controller.set_backend_state("ready")

    assert availability == [False, True]
    assert cluster.availability_updates[-1] == {
        "can_generate": True,
        "can_skip": False,
        "can_stop": False,
        "can_show_queue": False,
    }


def test_set_backend_state_emits_changed_signal() -> None:
    """Backend state projection should notify controllers waiting for readiness."""

    state_signal = _Signal()
    shell = _generation_action_shell(cluster=None)
    shell.backend_state_changed = state_signal
    controller = GenerationActionController(shell)

    controller.set_backend_state("starting")
    controller.set_backend_state("starting")
    controller.set_backend_state("ready")

    assert state_signal.emitted == ["starting", "ready"]


def test_generation_action_availability_uses_queue_and_continuous_state() -> None:
    """Titlebar action availability should reflect backend, queue, and continuous state."""

    cluster = _GenerationActionCluster()
    shell = _generation_action_shell(
        cluster=cluster,
        has_active_job=True,
        has_cancellable_jobs=True,
        jobs=(
            SimpleNamespace(status="running"),
            SimpleNamespace(status="pending"),
            SimpleNamespace(status="completed"),
            SimpleNamespace(status="failed"),
            SimpleNamespace(status="cancelled"),
        ),
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert cluster.availability_updates[-1] == {
        "can_generate": True,
        "can_skip": True,
        "can_stop": True,
        "can_show_queue": True,
    }
    assert cluster.queue_badge_count_updates[-1] == 1
    assert cluster.queue_segment_visible_updates[-1] is True

    shell.workspace_generation_controller.is_continuous_active = True
    shell.generation_job_queue_service = _queue_service(
        has_active_job=False,
        has_cancellable_jobs=False,
        jobs=(),
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert cluster.availability_updates[-1] == {
        "can_generate": True,
        "can_skip": True,
        "can_stop": True,
        "can_show_queue": False,
    }
    assert cluster.queue_badge_count_updates[-1] == 0
    assert cluster.queue_segment_visible_updates[-1] is True


def test_generation_action_availability_disables_skip_without_pending_queue() -> None:
    """Normal generation skip should require additional queued work."""

    cluster = _GenerationActionCluster()
    shell = _generation_action_shell(
        cluster=cluster,
        has_active_job=True,
        has_cancellable_jobs=True,
        jobs=(SimpleNamespace(status="running"),),
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert cluster.availability_updates[-1] == {
        "can_generate": True,
        "can_skip": False,
        "can_stop": True,
        "can_show_queue": True,
    }
    assert cluster.queue_badge_count_updates[-1] == 0


def test_generation_action_availability_hides_queue_segment_for_visible_panel() -> None:
    """Full queue panel visibility should remove the redundant titlebar queue segment."""

    cluster = _GenerationActionCluster()
    shell = _generation_action_shell(
        cluster=cluster,
        jobs=(object(),),
        queue_panel_visible=True,
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert cluster.availability_updates[-1] == {
        "can_generate": True,
        "can_skip": False,
        "can_stop": False,
        "can_show_queue": True,
    }
    assert cluster.queue_segment_visible_updates[-1] is False


def test_generation_action_availability_noops_without_titlebar_cluster() -> None:
    """Availability updates should be safe before a titlebar cluster exists."""

    shell = _generation_action_shell(cluster=None)

    GenerationActionController(shell).apply_generation_action_availability()


def test_detached_shell_ignores_stale_generation_availability_callbacks() -> None:
    """Detached shells should not touch deleted titlebar controls after GUI reload."""

    calls: list[str] = []
    shell = _generation_action_shell(cluster=None)
    shell._detached_for_gui_reload = True
    shell.generationActionCluster = SimpleNamespace(
        apply_generation_presentation=lambda _presentation: calls.append("availability")
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert calls == []


def test_generation_action_availability_fans_out_through_registry() -> None:
    """Registry should receive shell generation presentation when attached."""

    registry_presentations: list[GenerationActionPresentation] = []
    cluster = _GenerationActionCluster()
    shell = _generation_action_shell(cluster=cluster)
    shell.generation_titlebar_control_registry = SimpleNamespace(
        apply_generation_presentation=registry_presentations.append
    )

    GenerationActionController(shell).apply_generation_action_availability()

    assert len(registry_presentations) == 1
    assert registry_presentations[0].play_enabled is True
    assert cluster.presentation_updates == []


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
    return shell


def _generation_action_shell(
    *,
    cluster: _GenerationActionCluster | None,
    set_backend_available: object | None = None,
    has_active_job: bool = False,
    has_cancellable_jobs: bool = False,
    jobs: tuple[object, ...] = (),
    queue_panel_visible: bool = False,
) -> SimpleNamespace:
    """Return a shell fake for generation action projection."""

    return SimpleNamespace(
        generationActionCluster=cluster,
        _backend_state="ready",
        _current_generate_mode="generate",
        _active_workspace_route="wf-a",
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": SimpleNamespace(cubes={"Cube": object()})},
        ),
        workspace_generation_controller=SimpleNamespace(
            is_continuous_active=False,
            set_backend_available=(
                set_backend_available
                if set_backend_available is not None
                else lambda _available, **_kwargs: None
            ),
        ),
        generation_job_queue_service=_queue_service(
            has_active_job=has_active_job,
            has_cancellable_jobs=has_cancellable_jobs,
            jobs=jobs,
        ),
        generation_queue_controller=SimpleNamespace(panel_visible=queue_panel_visible),
    )


def _queue_service(
    *,
    has_active_job: bool,
    has_cancellable_jobs: bool,
    jobs: tuple[object, ...],
) -> SimpleNamespace:
    """Return a queue service fake for action projection."""

    return SimpleNamespace(
        has_active_job=lambda: has_active_job,
        has_cancellable_jobs=lambda: has_cancellable_jobs,
        jobs=lambda: jobs,
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
