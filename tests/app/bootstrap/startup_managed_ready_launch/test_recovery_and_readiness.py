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

"""Test managed-ready recovery, readiness, and timing contracts."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import cast

from substitute.app.bootstrap.startup_managed_ready_launch import (
    StartupManagedReadyLaunchRuntime,
    create_startup_managed_ready_launch_runtime,
)
from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryController,
)
from substitute.app.bootstrap.managed_recovery_adapters import (
    ManagedRecoveryOutputStreamProtocol,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellBuildTask,
    ReadyShellInitialWorkspacePrehydrationTask,
    ReadyShellMetadataBridgeTask,
    ReadyShellMinimumReadyTask,
    ReadyShellPromptEditorWarmupTask,
    ReadyShellTargetActivationTask,
)
from substitute.app.bootstrap.ready_shell_startup_tasks import (
    ReadyShellStartupTaskQueueProtocol,
)
from substitute.app.bootstrap.startup_managed_ready_runtime import (
    StartupManagedReadyRuntimeResources,
)
from substitute.app.bootstrap.startup_managed_ready_state import (
    create_startup_managed_ready_state_bundle,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_readiness_controller import (
    StartupReadinessController,
)
from substitute.app.bootstrap.startup_timing import StartupTimer


from .launch_support import (
    _Clock,
    _StartupTaskScheduleRuntime,
    _context,
    _ports,
)


def test_managed_ready_launch_runtime_binds_recovery_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind recovery state."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    controller = launch_runtime.create_managed_compatibility_recovery_controller(
        splash=lambda: None,
        comfy_output_stream=cast(ManagedRecoveryOutputStreamProtocol, object()),
        handle_managed_startup_failure=lambda _incident: None,
        current_comfy_state=lambda: None,
        set_comfy_state=lambda _state: None,
        is_startup_cancelled=lambda: False,
        trace_fields=lambda: {},
        relaunch_phase=lambda: nullcontext(),
    )

    assert isinstance(controller, ManagedCompatibilityRecoveryController)
    assert (
        getattr(controller, "_state")
        is launch_runtime.state.managed_compatibility_recovery_state
    )
    assert getattr(controller, "_comfy_ready_state") is launch_runtime.state.ready_state
    assert (
        getattr(controller, "_readiness_state")
        is launch_runtime.state.readiness_controller_state
    )
    assert (
        getattr(controller, "_restart_readiness_timer")
        == launch_runtime.state.readiness_starter.start
    )
    assert (
        getattr(controller, "_set_backend_state")
        == launch_runtime.state.backend_state_updater.update
    )


def test_managed_ready_launch_runtime_binds_readiness_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind readiness state."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    launch_runtime.state.managed_compatibility_recovery_state.recovery_attempted = True
    launch_runtime.state.managed_compatibility_recovery_state.recovery_running = True
    recoveries: list[object] = []

    controller = launch_runtime.bind_startup_readiness_controller(
        is_startup_cancelled=lambda: False,
        readiness_probe=lambda _host, _port: True,
        current_comfy_state=lambda: None,
        handle_managed_startup_failure=lambda _incident: None,
        start_managed_compatibility_recovery=recoveries.append,
        backend_ready_phase=lambda: nullcontext(),
        release_nonessential_startup_warmups=lambda: None,
        try_show_main_window=lambda: None,
        trace_fields=lambda: {},
    )

    assert isinstance(controller, StartupReadinessController)
    assert (
        getattr(controller, "_state") is launch_runtime.state.readiness_controller_state
    )
    assert (
        getattr(controller, "_comfy_http_ready_state")
        is launch_runtime.state.ready_state
    )
    assert getattr(controller, "_recovery_attempted")() is True
    assert getattr(controller, "_recovery_running")() is True
    assert getattr(launch_runtime.state.readiness_starter, "_controller") is controller
    assert (
        getattr(controller, "_set_backend_state")
        == launch_runtime.state.backend_state_updater.update
    )


def test_managed_ready_launch_runtime_binds_startup_task_readiness_timer() -> None:
    """Managed-ready launch assembly should own readiness timer scheduling."""

    state = create_startup_managed_ready_state_bundle()
    runtime = _StartupTaskScheduleRuntime()
    launch_runtime = StartupManagedReadyLaunchRuntime(
        state=state,
        runtime=cast(StartupManagedReadyRuntimeResources, runtime),
    )

    launch_runtime.schedule_startup_tasks(
        queue=cast(ReadyShellStartupTaskQueueProtocol, object()),
        target_activation_task=cast(ReadyShellTargetActivationTask, object()),
        shell_build_task=cast(ReadyShellBuildTask, object()),
        metadata_bridge_task=cast(ReadyShellMetadataBridgeTask, object()),
        prompt_editor_warmup_task=cast(ReadyShellPromptEditorWarmupTask, object()),
        initial_workspace_prehydration_task=cast(
            ReadyShellInitialWorkspacePrehydrationTask,
            object(),
        ),
        minimum_shell_ready_task=cast(ReadyShellMinimumReadyTask, object()),
    )

    assert runtime.start_readiness_timer == state.readiness_starter.start
