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

"""Test managed-ready shell build, restore, reveal, and post-show contracts."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.startup_managed_ready_launch import (
    create_startup_managed_ready_launch_runtime,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellBuildTask,
    ReadyShellInitialWorkspacePrehydrationTask,
    ReadyShellMinimumReadyTask,
    ReadyShellPostShowController,
    ReadyShellShowGateTask,
)
from substitute.app.bootstrap.ready_shell_reveal import ReadyShellRevealTask
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_warmup_controller import (
    NonessentialStartupWarmupRuntime,
)


from .launch_support import (
    _Clock,
    _context,
    _ports,
)


def test_managed_ready_launch_runtime_binds_shell_build_ready_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind ready state into shell build."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    launch_runtime.state.ready_state.comfy_http_ready = True

    task = launch_runtime.create_shell_build_task(
        startup_cancelled=lambda: False,
        splash=lambda: None,
        context=object(),
        comfy_output_stream=object(),
        shutdown_request=lambda _state: None,
        startup_timer=StartupTimer(clock=_Clock()),
        runtime_services=object(),
        build_main_window=lambda **_kwargs: object(),
        attach_gui_reload_command=lambda _shell_frame: None,
        set_current_shell=lambda _shell_frame: None,
        main_window_for_shell=lambda _shell_frame: object(),
        restore_asset_preload=lambda: None,
        set_shell_frame=lambda _shell_frame: None,
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellBuildTask)
    assert getattr(task, "_comfy_http_ready")() is True
    assert (
        getattr(task, "_set_backend_state")
        == launch_runtime.state.backend_state_updater.update
    )


def test_managed_ready_launch_runtime_binds_initial_prehydration_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind ready state into prehydration."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    task = launch_runtime.create_initial_workspace_prehydration_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: None,
        main_window_for_shell=lambda _shell_frame: object(),
        workspace=lambda: None,
        startup_timer=StartupTimer(clock=_Clock()),
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellInitialWorkspacePrehydrationTask)
    assert getattr(task, "_state") is launch_runtime.state.ready_state


def test_managed_ready_launch_runtime_binds_minimum_ready_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind ready state into minimum-ready."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    task = launch_runtime.create_minimum_ready_task(
        startup_cancelled=lambda: False,
        try_show_main_window=lambda: None,
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellMinimumReadyTask)
    assert getattr(task, "_state") is launch_runtime.state.ready_state


def test_managed_ready_launch_runtime_binds_reveal_warmup_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind warmup state into reveal."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    launch_runtime.state.ready_state.comfy_http_ready = True

    task = launch_runtime.create_reveal_task(
        splash=lambda: None,
        shell_frame=lambda: object(),
        initial_shell_placement=lambda: None,
        startup_timer=StartupTimer(clock=_Clock()),
        show_built_main_window=lambda **_kwargs: None,
        set_current_shell=lambda _shell_frame: None,
        schedule_warmups=lambda _reason: None,
        request_startup_diagnostics_update=lambda _main_window: None,
        schedule_post_show_hydration=lambda: None,
        set_shell_frame=lambda _shell_frame: None,
        set_splash=lambda _splash: None,
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellRevealTask)
    assert (
        getattr(task, "_startup_warmup_state")
        is launch_runtime.state.startup_warmup_state
    )
    assert getattr(task, "_comfy_http_ready")() is True
    assert (
        getattr(task, "_update_backend_state")
        == launch_runtime.state.backend_state_updater.update
    )


def test_managed_ready_launch_runtime_binds_show_gate_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind ready and pre-show state."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    launch_runtime.state.ready_state.minimum_shell_ready = True
    launch_runtime.state.ready_state.comfy_http_ready = True
    launch_runtime.state.ready_state.prehydration_succeeded = True
    launch_runtime.state.pre_show_restore_projection_state.pending = True

    task = launch_runtime.create_show_gate_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: object(),
        comfy_state=lambda: object(),
        handle_fatal_incident=lambda _incident: None,
        main_window_for_shell=lambda _shell_frame: object(),
        workspace=lambda: None,
        startup_timer=StartupTimer(clock=_Clock()),
        provisional_restore_projection=lambda: None,
        startup_cancelled_callback=lambda: False,
        reveal_main_window=lambda _main_window: object(),
        scheduler=lambda _delay, _callback: None,
        set_hidden_restore_runtime_prepared=lambda _prepared: None,
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellShowGateTask)
    assert getattr(task, "_state") is launch_runtime.state.ready_state
    assert (
        getattr(task, "_pre_show_projection_state")
        is launch_runtime.state.pre_show_restore_projection_state
    )
    assert getattr(task, "_pre_show_projection_pending")() is True
    assert getattr(task, "_minimum_shell_ready")() is True
    assert getattr(task, "_comfy_http_ready")() is True
    assert getattr(task, "_prehydration_succeeded")() is True


def test_managed_ready_launch_runtime_binds_post_show_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind ready state into post-show."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    launch_runtime.state.ready_state.prehydration_succeeded = True
    queued_tasks: list[tuple[str, object]] = []

    controller = launch_runtime.create_post_show_controller(
        startup_cancelled=lambda: False,
        shell_frame=lambda: object(),
        main_window_for_shell=lambda _shell_frame: object(),
        queue_named_task=lambda name, task: queued_tasks.append((name, task)),
        start_queue=lambda: None,
        workspace=lambda: None,
        hidden_restore_runtime_prepared=lambda: False,
        startup_timer=StartupTimer(clock=_Clock()),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {},
    )

    assert isinstance(controller, ReadyShellPostShowController)
    assert getattr(controller, "_state") is launch_runtime.state.ready_state
    assert getattr(controller, "_prehydration_succeeded")() is True
    assert (
        getattr(launch_runtime.state.backend_state_updater, "_update_backend_state")
        == controller.update_backend_state
    )


def test_managed_ready_launch_runtime_binds_nonessential_warmup_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind state into warmups."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    launch_runtime.state.ready_state.comfy_http_ready = True
    registry = StartupResourceRegistry()

    runtime = launch_runtime.create_nonessential_startup_warmup_runtime(
        startup_cancelled=lambda: False,
        metadata_update_bridge=lambda: None,
        shell_frame=lambda: object(),
        main_window_for_shell=lambda _shell_frame: object(),
        registry=registry,
        model_metadata_refreshes=lambda: [],
        model_metadata_service_factory=lambda: object(),
        model_metadata_refresh_handle_factory=lambda **_kwargs: object(),
        comfy_output_stream=object(),
        scheduler=lambda _delay, _callback: None,
        trace_fields=lambda: {},
    )

    assert isinstance(runtime, NonessentialStartupWarmupRuntime)
    assert runtime.launcher._state is launch_runtime.state.startup_warmup_state
    assert runtime.launcher._comfy_http_ready() is True
    assert (
        runtime.launcher._readiness_state
        is launch_runtime.state.readiness_controller_state
    )
    assert (
        runtime.launcher._model_metadata_refresh_state
        is launch_runtime.state.model_metadata_refresh_state
    )
