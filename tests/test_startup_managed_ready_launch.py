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

"""Tests for managed-ready startup launch assembly."""

from __future__ import annotations

import ast
from collections.abc import Callable
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
    ReadyShellFailureQueue,
    ReadyShellInitialWorkspacePrehydrationTask,
    ReadyShellLocalEditorWarmupAdapter,
    ReadyShellManagedStartupPrelude,
    ReadyShellMetadataBridgeTask,
    ReadyShellMinimumReadyTask,
    ReadyShellPostShowController,
    ReadyShellPromptEditorWarmupTask,
    ReadyShellRevealTask,
    ReadyShellShowGateTask,
    ReadyShellStartupDiagnosticsUpdateAdapter,
    ReadyShellTargetActivationTask,
)
from substitute.app.bootstrap.ready_shell_startup_tasks import (
    ReadyShellStartupTaskQueueProtocol,
)
from substitute.app.bootstrap.startup_managed_ready_runtime import (
    StartupManagedCompatibilityRecoveryBridgeProtocol,
    StartupManagedReadyRuntimeResources,
)
from substitute.app.bootstrap.startup_managed_ready_state import (
    StartupManagedReadyStateBundle,
    create_startup_managed_ready_state_bundle,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupRuntimeCompatibilityCheckerProtocol,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_readiness_controller import (
    StartupReadinessController,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_warmup_controller import (
    NonessentialStartupWarmupRuntime,
)
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_launch.py"
)
STARTUP_MANAGED_READY_SHELL_LAUNCHER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_MANAGED_READY_LAUNCH_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)
ALLOWED_MANAGED_READY_SHELL_LAUNCHER_IMPORTS = frozenset(
    {"substitute.presentation.qt.execution"}
)


def test_managed_ready_launch_runtime_creates_state_and_resources(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should pair state with runtime resources."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    assert isinstance(launch_runtime, StartupManagedReadyLaunchRuntime)
    assert isinstance(launch_runtime.state, StartupManagedReadyStateBundle)
    assert isinstance(launch_runtime.runtime, StartupManagedReadyRuntimeResources)


def test_managed_ready_launch_runtime_binds_trace_fields(tmp_path: Path) -> None:
    """Managed-ready launch assembly should bind state into trace fields."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    provider = launch_runtime.create_ready_trace_fields(
        startup_cancelled=lambda: True,
        shell_frame_present=lambda: False,
        provisional_restore_projection_present=lambda: True,
    )
    launch_runtime.state.ready_state.minimum_shell_ready = True
    launch_runtime.state.readiness_controller_state.readiness_attempts = 2
    launch_runtime.state.managed_compatibility_recovery_state.recovery_attempted = True
    launch_runtime.state.pre_show_restore_projection_state.pending = True

    fields = provider()

    assert fields["startup_cancelled"] is True
    assert fields["shell_frame_present"] is False
    assert fields["minimum_shell_ready"] is True
    assert fields["readiness_attempts"] == 2
    assert fields["managed_compatibility_recovery_attempted"] is True
    assert fields["pre_show_restore_projection_pending"] is True
    assert fields["provisional_restore_projection_present"] is True


def test_managed_ready_launch_runtime_creates_failure_queue(tmp_path: Path) -> None:
    """Managed-ready launch assembly should expose failure queue construction."""

    comfy_state = object()
    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: comfy_state,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    failure_queue = launch_runtime.create_failure_queue(
        is_startup_cancelled=lambda: False,
        mark_startup_cancelled=lambda: None,
        managed_comfy_state=lambda: comfy_state,
        splash=lambda: None,
        cleanup=lambda: None,
        quit_app=lambda: None,
        trace_fields=lambda: {},
        scheduler=lambda _delay, _callback: None,
    )

    assert isinstance(failure_queue, ReadyShellFailureQueue)


def test_managed_ready_launch_runtime_binds_target_activation_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind ready state into activation."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    comfy_states: list[object | None] = []
    task = launch_runtime.create_target_activation_task(
        startup_cancelled=lambda: False,
        splash=lambda: object(),
        comfy_output_stream=object(),
        set_comfy_state=comfy_states.append,
        trace_fields=lambda: {},
    )

    result = task.activate()

    assert isinstance(task, ReadyShellTargetActivationTask)
    assert result.started is True
    assert launch_runtime.state.ready_state.comfy_activation_started is True
    assert comfy_states == [result.comfy_state]


def test_managed_ready_launch_runtime_creates_metadata_bridge_task(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should create metadata bridge tasks."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    shell_frame = object()
    registered_bridges: list[object] = []
    recorded_metadata_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []

    task = launch_runtime.create_metadata_bridge_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        register_bridge=registered_bridges.append,
        main_window_for_shell=lambda _shell_frame: object(),
        set_metadata_update_bridge=recorded_metadata_bridges.append,
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellMetadataBridgeTask)
    assert getattr(task, "_shell_frame")() is shell_frame
    assert getattr(task, "_register_bridge") == registered_bridges.append
    assert (
        getattr(task, "_set_metadata_update_bridge") == recorded_metadata_bridges.append
    )


def test_managed_ready_launch_runtime_creates_prompt_editor_warmup_task(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should create prompt editor warmup tasks."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    shell_frame = object()
    main_window = object()

    task = launch_runtime.create_prompt_editor_warmup_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        main_window_for_shell=lambda _shell_frame: main_window,
        trace_fields=lambda: {},
    )

    assert isinstance(task, ReadyShellPromptEditorWarmupTask)
    assert getattr(task, "_shell_frame")() is shell_frame
    assert getattr(task, "_main_window_for_shell")(shell_frame) is main_window


def test_managed_ready_launch_runtime_binds_local_editor_warmup_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind warmup state into local editor."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    registry = StartupResourceRegistry()

    adapter = launch_runtime.create_local_editor_warmup_adapter(
        startup_cancelled=lambda: False,
        main_window_for_shell=lambda _shell_frame: object(),
        registry=registry,
        trace_fields=lambda: {},
    )

    assert isinstance(adapter, ReadyShellLocalEditorWarmupAdapter)
    assert getattr(adapter, "_state") is launch_runtime.state.startup_warmup_state
    assert getattr(adapter, "_registry") is registry


def test_managed_ready_launch_runtime_creates_managed_startup_prelude(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should create the startup prelude."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    prelude = launch_runtime.create_managed_startup_prelude(
        connect_cancel_request=lambda _callback: object(),
        request_startup_cancel=lambda: None,
        initial_splash_cancel_connector=None,
        emit_splash_cancel=lambda: None,
        splash=lambda: None,
        set_splash=lambda _splash: None,
        startup_timer=StartupTimer(clock=_Clock()),
        resolved_appearance=object(),
        start_or_adopt_launch_splash=lambda **_kwargs: object(),
    )

    assert isinstance(prelude, ReadyShellManagedStartupPrelude)


def test_managed_ready_launch_runtime_binds_qpane_warmup_state(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should bind QPane warmup state separately."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )
    registry = StartupResourceRegistry()

    callback = launch_runtime.create_qpane_sam_warmup_callback(
        startup_cancelled=lambda: False,
        registry=registry,
        trace_fields=lambda: {},
    )

    assert callable(callback)


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


def test_managed_ready_launch_runtime_creates_startup_diagnostics_update_adapter(
    tmp_path: Path,
) -> None:
    """Managed-ready launch assembly should create diagnostics update adapters."""

    launch_runtime = create_startup_managed_ready_launch_runtime(
        context=_context(tmp_path),
        comfy_state=lambda: None,
        managed_ready_ports=_ports(),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

    adapter = launch_runtime.create_startup_diagnostics_update_adapter(
        startup_cancelled=lambda: True,
        shell_frame_available=lambda: False,
        trace_fields=lambda: {},
    )

    assert isinstance(adapter, ReadyShellStartupDiagnosticsUpdateAdapter)
    assert adapter._startup_cancelled() is True
    assert adapter._shell_frame_available() is False


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


def test_managed_ready_launch_imports_no_forbidden_boundaries() -> None:
    """Managed-ready launch assembly should stay outside UI and infrastructure."""

    imported_modules = _imported_module_names(STARTUP_MANAGED_READY_LAUNCH_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if imported_module not in ALLOWED_MANAGED_READY_SHELL_LAUNCHER_IMPORTS
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_MANAGED_READY_LAUNCH_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_managed_ready_shell_launcher_imports_no_forbidden_boundaries() -> None:
    """Managed-ready shell launcher should stay outside UI and infrastructure."""

    imported_modules = _imported_module_names(
        STARTUP_MANAGED_READY_SHELL_LAUNCHER_SOURCE
    )
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if imported_module not in ALLOWED_MANAGED_READY_SHELL_LAUNCHER_IMPORTS
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_MANAGED_READY_LAUNCH_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_managed_ready_launch_runtime() -> None:
    """Startup should request one managed-ready launch assembly object."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    ready_launch_source = STARTUP_READY_SHELL_LAUNCH_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    launcher_source = STARTUP_MANAGED_READY_SHELL_LAUNCHER_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_shell_launcher(" not in source
    assert "create_startup_managed_ready_shell_launcher(" in ready_launch_source
    assert "def launch_managed_ready_shell" not in source
    assert "create_startup_managed_ready_launch_runtime(" not in source
    assert "create_startup_managed_ready_state_bundle()" not in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "managed_ready_launch.state" not in source
    assert "managed_ready_launch.runtime" not in source
    assert "create_startup_managed_ready_launch_runtime(" in launch_source
    assert "create_startup_managed_ready_shell_launcher(" not in launch_source
    assert "StartupManagedReadyShellLauncher" not in launch_source
    assert "managed_ready_launch.create_ready_trace_fields(" in launcher_source
    assert (
        "managed_ready_runtime.create_ready_shell_trace_fields_provider("
        not in launcher_source
    )
    assert "managed_ready_launch.create_failure_queue(" in launcher_source
    assert "managed_ready_runtime.create_failure_queue(" not in launcher_source
    assert "managed_ready_launch.create_target_activation_task(" in launcher_source
    assert "managed_ready_runtime.create_target_activation_task(" not in launcher_source
    assert "managed_ready_launch.create_metadata_bridge_task(" in launcher_source
    assert "managed_ready_runtime.create_metadata_bridge_task(" not in launcher_source
    assert "managed_ready_launch.create_prompt_editor_warmup_task(" in launcher_source
    assert (
        "managed_ready_runtime.create_prompt_editor_warmup_task(" not in launcher_source
    )
    assert "managed_ready_launch.create_local_editor_warmup_adapter(" in launcher_source
    assert (
        "managed_ready_runtime.create_local_editor_warmup_adapter("
        not in launcher_source
    )
    assert "managed_ready_launch.create_managed_startup_prelude(" in launcher_source
    assert (
        "managed_ready_runtime.create_managed_startup_prelude(" not in launcher_source
    )
    assert "managed_ready_launch.create_shell_build_task(" in launcher_source
    assert "managed_ready_runtime.create_shell_build_task(" not in launcher_source
    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launcher_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task("
        not in launcher_source
    )
    assert "managed_ready_launch.create_minimum_ready_task(" in launcher_source
    assert "managed_ready_runtime.create_minimum_ready_task(" not in launcher_source
    assert "managed_ready_launch.create_reveal_task(" in launcher_source
    assert "managed_ready_runtime.create_reveal_task(" not in launcher_source
    assert (
        "comfy_http_ready=lambda: ready_state.comfy_http_ready" not in launcher_source
    )
    assert "managed_ready_launch.create_show_gate_task(" in launcher_source
    assert "managed_ready_runtime.create_show_gate_task(" not in launcher_source
    assert "managed_ready_launch.create_post_show_controller(" in launcher_source
    assert "managed_ready_runtime.create_post_show_controller(" not in launcher_source
    assert (
        "managed_ready_launch.create_nonessential_startup_warmup_runtime("
        in launcher_source
    )
    assert (
        "managed_ready_runtime.create_nonessential_startup_warmup_runtime("
        not in launcher_source
    )
    assert (
        "managed_ready_launch.create_startup_diagnostics_update_adapter("
        in launcher_source
    )
    assert (
        "managed_ready_runtime.create_startup_diagnostics_update_adapter("
        not in launcher_source
    )
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launcher_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller("
        not in launcher_source
    )
    assert "managed_ready_launch.bind_startup_readiness_controller(" in launcher_source
    assert (
        "managed_ready_runtime.bind_startup_readiness_controller("
        not in launcher_source
    )
    assert "managed_ready_launch.schedule_startup_tasks(" in launcher_source
    assert "managed_ready_runtime.schedule_startup_tasks(" not in launcher_source
    assert "start_readiness_timer=readiness_starter.start" not in launcher_source
    assert (
        "backend_state_updater = managed_ready_state.backend_state_updater"
        not in launcher_source
    )
    assert "set_backend_state=backend_state_updater.update" not in launcher_source
    assert "update_backend_state=backend_state_updater.update" not in launcher_source
    assert "backend_state_updater=backend_state_updater" not in launcher_source


def _ports() -> StartupManagedReadyFactoryPorts:
    """Create inert managed-ready ports for launch assembly tests."""

    failure_incident = cast(ComfyStartupIncident, object())
    compatibility_checker = cast(
        StartupRuntimeCompatibilityCheckerProtocol,
        _CompatibilityChecker(),
    )

    return StartupManagedReadyFactoryPorts(
        create_startup_diagnostics_collector=ComfyStartupDiagnosticsCollector,
        create_startup_diagnostics_ignore_repository=lambda _context: cast(
            StartupDiagnosticsIgnoreRepository,
            object(),
        ),
        create_runtime_compatibility_checker=lambda: compatibility_checker,
        create_managed_compatibility_recovery_bridge=lambda: cast(
            StartupManagedCompatibilityRecoveryBridgeProtocol,
            _RecoveryBridge(),
        ),
        create_model_metadata_update_bridge=lambda _parent: cast(
            ModelMetadataUpdateSignalBridgeProtocol,
            object(),
        ),
        request_startup_diagnostics_titlebar_update=lambda **_kwargs: True,
        activate_target=lambda **_kwargs: object(),
        managed_startup_fatal_incident=lambda _state: failure_incident,
        present_startup_failure_report=lambda _report: None,
        build_startup_failure_report=lambda **_kwargs: object(),
        build_startup_readiness_timeout_incident=lambda **_kwargs: failure_incident,
        build_startup_runtime_compatibility_incident=lambda **_kwargs: failure_incident,
    )


def _context(tmp_path: Path) -> InstallationContext:
    """Build one managed-ready installation context."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            workspace_path=tmp_path / "ComfyUI",
            install_owned=True,
            launch_owned=True,
        ),
    )


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _CompatibilityChecker:
    """Accept compatibility checks requested by runtime resources."""

    def assess_target(self, _target: object) -> object:
        """Return an inert compatibility result."""

        return object()


class _Signal:
    """Expose the Qt-compatible signal methods used by startup bridges."""

    def connect(self, _callback: object) -> object:
        """Return one inert connection token."""

        return object()

    def emit(self, *_args: object) -> None:
        """Accept emitted bridge payloads."""


class _RecoveryBridge:
    """Expose a recovery completion signal."""

    def __init__(self) -> None:
        """Create the finished signal."""

        self.finished = _Signal()


class _StartupTaskScheduleRuntime:
    """Record the readiness timer callback passed to the lower-level scheduler."""

    def __init__(self) -> None:
        """Initialize the recorded callback slot."""

        self.start_readiness_timer: Callable[[], None] | None = None

    def schedule_startup_tasks(
        self,
        *,
        queue: ReadyShellStartupTaskQueueProtocol,
        target_activation_task: ReadyShellTargetActivationTask,
        start_readiness_timer: Callable[[], None],
        shell_build_task: ReadyShellBuildTask,
        metadata_bridge_task: ReadyShellMetadataBridgeTask,
        prompt_editor_warmup_task: ReadyShellPromptEditorWarmupTask,
        initial_workspace_prehydration_task: ReadyShellInitialWorkspacePrehydrationTask,
        minimum_shell_ready_task: ReadyShellMinimumReadyTask,
    ) -> None:
        """Store the callback delegated by the launch runtime."""

        self.start_readiness_timer = start_readiness_timer


class _Clock:
    """Return monotonically increasing timestamps for deterministic timing."""

    def __init__(self) -> None:
        """Initialize the fake clock."""

        self._now = 0.0

    def __call__(self) -> float:
        """Return the next fake timestamp."""

        self._now += 0.1
        return self._now
