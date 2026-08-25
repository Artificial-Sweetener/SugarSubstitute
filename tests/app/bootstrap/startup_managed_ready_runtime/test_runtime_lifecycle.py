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

"""Test managed-ready runtime lifecycle contracts."""

from __future__ import annotations

from pathlib import Path
from typing import cast
import pytest
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionState,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellBackendStateUpdater,
    ReadyShellBuildTask,
    ReadyShellFailureQueue,
    ReadyShellInitialWorkspacePrehydrationTask,
    ReadyShellLocalEditorWarmupAdapter,
    ReadyShellManagedStartupPrelude,
    ReadyShellMetadataBridgeTask,
    ReadyShellMinimumReadyTask,
    ReadyShellPostShowController,
    ReadyShellPromptEditorWarmupTask,
    ReadyShellShowGateTask,
    ReadyShellTargetActivationTask,
    ReadyShellStartupDiagnosticsUpdateAdapter,
)
from substitute.app.bootstrap.ready_shell_reveal import ReadyShellRevealTask
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_warmup_controller import StartupWarmupState
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from .runtime_support import (
    _MetadataMainWindow,
    _MetadataSurfaceRefreshController,
    _OutputStream,
    _ReadyState,
    _Splash,
    _StartupTaskQueue,
    create_runtime_harness,
)
from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryController,
    ManagedCompatibilityRecoveryControllerState,
    ManagedRecoveryComfyReadyStateProtocol,
    ManagedRecoveryReadinessStateProtocol,
)
from substitute.app.bootstrap.ready_shell_trace_fields import (
    ReadyShellTraceFieldsProvider,
)
from substitute.app.bootstrap.startup_readiness_controller import (
    StartupReadinessController,
    StartupReadinessControllerState,
    StartupReadinessStarter,
)
from substitute.app.bootstrap.startup_probe_tasks import RuntimeCompatibilityProbeResult
from .runtime_support import (
    _ControllerReadinessProbe,
    _ControllerRuntimeCompatibilityProbe,
    _ControllerTimer,
    _ProjectionState,
    _ReadinessState,
    _relaunch_phase,
)


def test_runtime_resources_bind_startup_lifecycle_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bind shell task factories, metadata delivery, warmup, and scheduling."""

    harness = create_runtime_harness(tmp_path, monkeypatch)
    resources = harness.resources
    assert callable(resources.create_failure_queue)
    assert callable(resources.create_shell_build_task)
    assert callable(resources.create_target_activation_task)
    assert callable(resources.create_local_editor_warmup_adapter)
    assert callable(resources.create_managed_startup_prelude)
    assert callable(resources.create_post_show_controller)
    assert callable(resources.create_prompt_editor_warmup_task)
    assert callable(resources.create_initial_workspace_prehydration_task)
    assert callable(resources.create_minimum_ready_task)
    assert callable(resources.create_reveal_task)
    assert callable(resources.create_show_gate_task)
    assert callable(resources.schedule_startup_tasks)
    diagnostics_update_adapter = resources.create_startup_diagnostics_update_adapter(
        startup_cancelled=lambda: False,
        shell_frame_available=lambda: True,
        trace_fields=lambda: {},
    )
    shell_frame = object()
    registered_bridges: list[object] = []
    recorded_metadata_bridges: list[ModelMetadataUpdateSignalBridgeProtocol | None] = []
    metadata_surface_refresh_controller = _MetadataSurfaceRefreshController()
    metadata_bridge_task = resources.create_metadata_bridge_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        register_bridge=registered_bridges.append,
        main_window_for_shell=lambda _shell_frame: _MetadataMainWindow(
            metadata_surface_refresh_controller
        ),
        set_metadata_update_bridge=recorded_metadata_bridges.append,
        trace_fields=lambda: {},
    )
    prompt_editor_window = object()
    prompt_editor_warmup_task = resources.create_prompt_editor_warmup_task(
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        main_window_for_shell=lambda _shell_frame: prompt_editor_window,
        trace_fields=lambda: {},
    )
    initial_workspace_prehydration_task = (
        resources.create_initial_workspace_prehydration_task(
            startup_cancelled=lambda: False,
            shell_frame=lambda: shell_frame,
            main_window_for_shell=lambda _shell_frame: object(),
            workspace=lambda: None,
            startup_timer=StartupTimer(clock=lambda: 0.1),
            state=_ReadyState(),
            trace_fields=lambda: {},
        )
    )
    splash = _Splash()
    output_stream = _OutputStream()
    failure_queue_events: list[str] = []
    failure_queue = resources.create_failure_queue(
        is_startup_cancelled=lambda: False,
        mark_startup_cancelled=lambda: failure_queue_events.append("cancelled"),
        managed_comfy_state=lambda: None,
        splash=lambda: None,
        cleanup=lambda: failure_queue_events.append("cleanup"),
        quit_app=lambda: failure_queue_events.append("quit"),
        trace_fields=lambda: {},
        scheduler=lambda _delay_ms, _callback: None,
    )
    target_activation_task = resources.create_target_activation_task(
        startup_cancelled=lambda: False,
        splash=lambda: splash,
        comfy_output_stream=output_stream,
        state=_ReadyState(),
        set_comfy_state=lambda _state: None,
        trace_fields=lambda: {},
    )
    shell_build_task = resources.create_shell_build_task(
        startup_cancelled=lambda: False,
        splash=lambda: splash,
        context=harness.context,
        comfy_output_stream=output_stream,
        shutdown_request=lambda _state: None,
        startup_timer=StartupTimer(clock=lambda: 0.1),
        runtime_services=object(),
        build_main_window=lambda **_kwargs: object(),
        attach_gui_reload_command=lambda _shell_frame: None,
        set_current_shell=lambda _shell_frame: None,
        main_window_for_shell=lambda _shell_frame: object(),
        restore_asset_preload=lambda: None,
        comfy_http_ready=lambda: True,
        set_backend_state=lambda _state: None,
        set_shell_frame=lambda _shell_frame: None,
        trace_fields=lambda: {},
    )
    local_editor_warmup_adapter = resources.create_local_editor_warmup_adapter(
        state=StartupWarmupState(),
        startup_cancelled=lambda: False,
        main_window_for_shell=lambda _shell_frame: object(),
        registry=StartupResourceRegistry(),
        trace_fields=lambda: {},
    )
    managed_startup_prelude = resources.create_managed_startup_prelude(
        connect_cancel_request=lambda _callback: None,
        request_startup_cancel=lambda: None,
        initial_splash_cancel_connector=None,
        emit_splash_cancel=lambda: None,
        splash=lambda: None,
        set_splash=lambda _splash: None,
        startup_timer=StartupTimer(clock=lambda: 0.1),
        resolved_appearance=object(),
        start_or_adopt_launch_splash=lambda **_kwargs: object(),
    )
    cutecanvas_warmup_callback = resources.create_cutecanvas_sam_warmup_callback(
        state=StartupWarmupState(),
        startup_cancelled=lambda: False,
        registry=StartupResourceRegistry(),
        trace_fields=lambda: {},
    )
    post_show_controller = resources.create_post_show_controller(
        backend_state_updater=ReadyShellBackendStateUpdater(),
        startup_cancelled=lambda: False,
        shell_frame=lambda: shell_frame,
        main_window_for_shell=lambda _shell_frame: object(),
        state=_ReadyState(),
        queue_named_task=lambda _name, _callback: None,
        start_queue=lambda: None,
        workspace=lambda: None,
        hidden_restore_runtime_prepared=lambda: False,
        prehydration_succeeded=lambda: False,
        startup_timer=StartupTimer(clock=lambda: 0.1),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {},
    )
    minimum_ready_task = resources.create_minimum_ready_task(
        startup_cancelled=lambda: False,
        state=_ReadyState(),
        try_show_main_window=lambda: None,
        trace_fields=lambda: {},
    )
    reveal_task = resources.create_reveal_task(
        splash=lambda: splash,
        shell_frame=lambda: shell_frame,
        initial_shell_placement=lambda: None,
        comfy_http_ready=lambda: True,
        startup_timer=StartupTimer(clock=lambda: 0.1),
        show_built_main_window=lambda **_kwargs: object(),
        set_current_shell=lambda _shell_frame: None,
        update_backend_state=lambda _state: None,
        startup_warmup_state=StartupWarmupState(),
        schedule_warmups=lambda _reason: None,
        request_startup_diagnostics_update=lambda _main_window: None,
        schedule_post_show_hydration=lambda: None,
        set_shell_frame=lambda _shell_frame: None,
        set_splash=lambda _splash: None,
        trace_fields=lambda: {},
    )
    show_gate_task = resources.create_show_gate_task(
        startup_cancelled=lambda: False,
        state=_ReadyState(),
        pre_show_projection_pending=lambda: False,
        minimum_shell_ready=lambda: False,
        comfy_http_ready=lambda: False,
        shell_frame=lambda: shell_frame,
        comfy_state=lambda: None,
        handle_fatal_incident=lambda _incident: None,
        main_window_for_shell=lambda _shell_frame: object(),
        workspace=lambda: None,
        prehydration_succeeded=lambda: False,
        startup_timer=StartupTimer(clock=lambda: 0.1),
        pre_show_projection_state=PreShowRestoreProjectionState(),
        provisional_restore_projection=lambda: None,
        startup_cancelled_callback=lambda: False,
        reveal_main_window=lambda _main_window: None,
        scheduler=lambda _delay_ms, _callback: None,
        set_hidden_restore_runtime_prepared=lambda _prepared: None,
        trace_fields=lambda: {},
    )
    startup_task_queue = _StartupTaskQueue()
    resources.schedule_startup_tasks(
        queue=startup_task_queue,
        prepare_main_window=lambda: object(),
        target_activation_task=target_activation_task,
        start_readiness_timer=lambda: None,
        shell_build_task=shell_build_task,
        metadata_bridge_task=metadata_bridge_task,
        prompt_editor_warmup_task=prompt_editor_warmup_task,
        initial_workspace_prehydration_task=initial_workspace_prehydration_task,
        minimum_shell_ready_task=minimum_ready_task,
    )

    assert isinstance(failure_queue, ReadyShellFailureQueue)
    assert isinstance(
        diagnostics_update_adapter, ReadyShellStartupDiagnosticsUpdateAdapter
    )
    assert not hasattr(resources, "managed_startup_fatal_incident")
    assert harness.compatibility_checker.targets == []
    assert isinstance(shell_build_task, ReadyShellBuildTask)
    assert isinstance(target_activation_task, ReadyShellTargetActivationTask)
    assert isinstance(local_editor_warmup_adapter, ReadyShellLocalEditorWarmupAdapter)
    assert isinstance(managed_startup_prelude, ReadyShellManagedStartupPrelude)
    assert callable(cutecanvas_warmup_callback)
    assert isinstance(post_show_controller, ReadyShellPostShowController)
    assert isinstance(minimum_ready_task, ReadyShellMinimumReadyTask)
    assert isinstance(reveal_task, ReadyShellRevealTask)
    assert isinstance(show_gate_task, ReadyShellShowGateTask)
    assert isinstance(metadata_bridge_task, ReadyShellMetadataBridgeTask)
    assert isinstance(prompt_editor_warmup_task, ReadyShellPromptEditorWarmupTask)
    assert isinstance(
        initial_workspace_prehydration_task,
        ReadyShellInitialWorkspacePrehydrationTask,
    )
    assert startup_task_queue.names == [
        "prepare_main_window",
        "activate_target",
        "start_readiness_timer",
        "build_main_window",
        "wire_metadata_bridge",
        "warm_prompt_editor_gui",
        "prehydrate_initial_workspace",
        "mark_minimum_shell_ready",
    ]
    assert startup_task_queue.started is True
    assert metadata_bridge_task.wire() is cast(
        ModelMetadataUpdateSignalBridgeProtocol,
        harness.metadata_bridge,
    )
    assert prompt_editor_warmup_task.warm() is True
    assert harness.warmed_windows == [prompt_editor_window]
    assert registered_bridges == [harness.metadata_bridge]
    assert len(recorded_metadata_bridges) == 1
    assert recorded_metadata_bridges[0] is cast(
        ModelMetadataUpdateSignalBridgeProtocol,
        harness.metadata_bridge,
    )
    assert harness.metadata_bridge.model_updated.callbacks == [
        metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert failure_queue_events == []


def test_runtime_resources_bind_recovery_readiness_and_failure_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bind recovery and readiness controllers to the managed runtime ports."""

    harness = create_runtime_harness(tmp_path, monkeypatch)
    resources = harness.resources
    splash = _Splash()
    output_stream = _OutputStream()
    managed_startup_failures: list[object] = []
    failure_queue_events: list[str] = []
    failure_queue = resources.create_failure_queue(
        is_startup_cancelled=lambda: False,
        mark_startup_cancelled=lambda: failure_queue_events.append("cancelled"),
        managed_comfy_state=lambda: None,
        splash=lambda: None,
        cleanup=lambda: failure_queue_events.append("cleanup"),
        quit_app=lambda: failure_queue_events.append("quit"),
        trace_fields=lambda: {},
        scheduler=lambda _delay_ms, _callback: None,
    )
    ready_state = _ReadyState()
    readiness_state = _ReadinessState()
    startup_readiness_state = StartupReadinessControllerState()
    readiness_starter = StartupReadinessStarter()
    recovery_state = ManagedCompatibilityRecoveryControllerState()
    projection_state = _ProjectionState()
    trace_provider = resources.create_ready_shell_trace_fields_provider(
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: True,
        ready_state=ready_state,
        readiness_state=readiness_state,
        recovery_state=recovery_state,
        pre_show_restore_projection_state=projection_state,
        provisional_restore_projection_present=lambda: True,
    )
    recovery_controller = resources.create_managed_compatibility_recovery_controller(
        state=recovery_state,
        comfy_ready_state=cast(ManagedRecoveryComfyReadyStateProtocol, ready_state),
        readiness_state=cast(ManagedRecoveryReadinessStateProtocol, readiness_state),
        splash=lambda: splash,
        comfy_output_stream=output_stream,
        handle_managed_startup_failure=managed_startup_failures.append,
        current_comfy_state=lambda: None,
        set_comfy_state=lambda _state: None,
        set_backend_state=lambda _state: None,
        is_startup_cancelled=lambda: False,
        restart_readiness_timer=lambda: None,
        trace_fields=lambda: {},
        relaunch_phase=_relaunch_phase,
    )
    readiness_controller = resources.bind_startup_readiness_controller(
        starter=readiness_starter,
        state=startup_readiness_state,
        comfy_http_ready_state=ready_state,
        is_startup_cancelled=lambda: False,
        readiness_probe=lambda _host, _port: True,
        current_comfy_state=lambda: None,
        handle_managed_startup_failure=managed_startup_failures.append,
        recovery_attempted=lambda: recovery_state.recovery_attempted,
        recovery_running=lambda: recovery_state.recovery_running,
        start_managed_compatibility_recovery=recovery_controller.start,
        set_backend_state=lambda _state: None,
        backend_ready_phase=_relaunch_phase,
        release_nonessential_startup_warmups=lambda: None,
        try_show_main_window=lambda: None,
        trace_fields=lambda: {},
    )
    readiness_controller.handle_runtime_compatibility_probe_result(
        timer=_ControllerTimer(),
        readiness_probe=_ControllerReadinessProbe(),
        compatibility_probe=_ControllerRuntimeCompatibilityProbe(),
        result=RuntimeCompatibilityProbeResult(
            request_id=1,
            compatibility=harness.compatibility,
        ),
    )
    harness.collector.append_output("runtime line")
    failure_queue.handle_managed_startup_failure(harness.failure_incident)

    assert harness.recovery_bridge.finished.emissions == []
    assert isinstance(failure_queue, ReadyShellFailureQueue)
    assert isinstance(trace_provider, ReadyShellTraceFieldsProvider)
    assert trace_provider()["shell_frame_present"] is True
    assert trace_provider()["provisional_restore_projection_present"] is True
    assert isinstance(recovery_controller, ManagedCompatibilityRecoveryController)
    assert isinstance(readiness_controller, StartupReadinessController)
    assert getattr(readiness_starter, "_controller") is readiness_controller
    assert len(harness.recovery_bridge.finished.callbacks) == 1
    assert callable(resources.create_nonessential_startup_warmup_runtime)
    assert not hasattr(resources, "restored_active_workflow_id")
    assert managed_startup_failures == [harness.failure_incident]
    assert failure_queue_events == ["cancelled", "cleanup", "quit"]
    assert len(harness.presented_reports) == 1
    assert harness.report_kwargs == [
        {
            "installation_context": harness.context,
            "incident": harness.failure_incident,
            "transcript": ("runtime line",),
        }
    ]
