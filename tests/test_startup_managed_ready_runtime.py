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

"""Tests for managed-ready startup runtime resource composition."""

from __future__ import annotations

import ast
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from substitute.app.bootstrap import startup_managed_ready_runtime
from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryController,
    ManagedCompatibilityRecoveryControllerState,
    ManagedRecoveryComfyReadyStateProtocol,
    ManagedRecoveryReadinessStateProtocol,
)
from substitute.app.bootstrap.ready_shell_trace_fields import (
    ReadyShellTraceFieldsProvider,
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
    ReadyShellRevealTask,
    ReadyShellShowGateTask,
    ReadyShellStartupDiagnosticsUpdateAdapter,
    ReadyShellTargetActivationTask,
)
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionState,
)
from substitute.app.bootstrap.startup_readiness_controller import (
    StartupReadinessController,
    StartupReadinessControllerState,
    StartupReadinessStarter,
    TimerSignalProtocol,
)
from substitute.app.bootstrap.startup_probe_tasks import (
    RuntimeCompatibilityProbeResult,
)
from substitute.app.bootstrap.startup_managed_ready_runtime import (
    StartupManagedCompatibilityRecoveryBridgeProtocol,
    create_startup_managed_ready_runtime_resources,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_warmup_controller import StartupWarmupState
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)
from substitute.application.comfy_startup_diagnostics import (
    ComfyStartupDiagnosticsCollector,
)
from substitute.application.ports.startup_diagnostics_ignore_repository import (
    StartupDiagnosticsIgnoreRepository,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationContext,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGED_READY_RUNTIME_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_runtime.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_MANAGED_READY_RUNTIME_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_managed_ready_runtime_resources_create_startup_collaborators(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Managed-ready runtime composition should bind resources from factory ports."""

    target = _target(tmp_path)
    context = cast(InstallationContext, _Context(target))
    collector = ComfyStartupDiagnosticsCollector()
    ignore_repository = cast(StartupDiagnosticsIgnoreRepository, object())
    compatibility = BackendCompatibilityResult(
        status=RuntimeCompatibilityStatus.BACKEND_TOO_NEW,
        summary="Runtime is newer than supported.",
    )
    compatibility_checker = _Checker(compatibility)
    fake_recovery_bridge = _RecoveryBridge()
    recovery_bridge = cast(
        StartupManagedCompatibilityRecoveryBridgeProtocol,
        fake_recovery_bridge,
    )
    metadata_bridge = _MetadataBridge()
    activation_result = object()
    failure_incident = cast(ComfyStartupIncident, object())
    fatal_incident = cast(ComfyStartupIncident, object())
    presented_reports: list[object] = []
    report_kwargs: list[dict[str, object]] = []
    warmed_windows: list[object] = []

    monkeypatch.setattr(
        startup_managed_ready_runtime,
        "warm_prompt_editor_gui_from_window",
        warmed_windows.append,
    )

    def build_failure_report(**kwargs: object) -> object:
        """Record managed failure report inputs."""

        report_kwargs.append(kwargs)
        return object()

    resources = create_startup_managed_ready_runtime_resources(
        context=context,
        comfy_state=lambda: object(),
        managed_ready_ports=StartupManagedReadyFactoryPorts(
            create_startup_diagnostics_collector=lambda: collector,
            create_startup_diagnostics_ignore_repository=lambda _context: (
                ignore_repository
            ),
            create_runtime_compatibility_checker=lambda: compatibility_checker,
            create_managed_compatibility_recovery_bridge=lambda: recovery_bridge,
            create_model_metadata_update_bridge=lambda _parent: cast(
                ModelMetadataUpdateSignalBridgeProtocol,
                metadata_bridge,
            ),
            request_startup_diagnostics_titlebar_update=lambda **_kwargs: True,
            activate_target=lambda **_kwargs: activation_result,
            managed_startup_fatal_incident=lambda _state: fatal_incident,
            present_startup_failure_report=presented_reports.append,
            build_startup_failure_report=build_failure_report,
            build_startup_readiness_timeout_incident=lambda **_kwargs: failure_incident,
            build_startup_runtime_compatibility_incident=lambda **_kwargs: (
                failure_incident
            ),
        ),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        execution_runtime=object(),
        execution_dispatcher_factory=lambda: object(),
    )

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
    assert isinstance(
        diagnostics_update_adapter,
        ReadyShellStartupDiagnosticsUpdateAdapter,
    )
    assert not hasattr(resources, "managed_startup_fatal_incident")
    assert compatibility_checker.targets == []
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
            startup_timer=StartupTimer(clock=_Clock()),
            state=_ReadyState(),
            trace_fields=lambda: {},
        )
    )
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
        context=context,
        comfy_output_stream=output_stream,
        shutdown_request=lambda _state: None,
        startup_timer=StartupTimer(clock=_Clock()),
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
        startup_timer=StartupTimer(clock=_Clock()),
        resolved_appearance=object(),
        start_or_adopt_launch_splash=lambda **_kwargs: object(),
    )
    qpane_warmup_callback = resources.create_qpane_sam_warmup_callback(
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
        startup_timer=StartupTimer(clock=_Clock()),
        schedule_warmups=lambda _reason: None,
        schedule_visible_summary=lambda _callback: None,
        trace_fields=lambda: {},
    )
    restored_workspace = SimpleNamespace(active_workflow_id="wf-a", workflows=(1, 2))
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
        startup_timer=StartupTimer(clock=_Clock()),
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
        workspace=lambda: restored_workspace,
        prehydration_succeeded=lambda: False,
        startup_timer=StartupTimer(clock=_Clock()),
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
        target_activation_task=target_activation_task,
        start_readiness_timer=lambda: None,
        shell_build_task=shell_build_task,
        metadata_bridge_task=metadata_bridge_task,
        prompt_editor_warmup_task=prompt_editor_warmup_task,
        initial_workspace_prehydration_task=initial_workspace_prehydration_task,
        minimum_shell_ready_task=minimum_ready_task,
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
        comfy_ready_state=cast(
            ManagedRecoveryComfyReadyStateProtocol,
            ready_state,
        ),
        readiness_state=cast(
            ManagedRecoveryReadinessStateProtocol,
            readiness_state,
        ),
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
            compatibility=compatibility,
        ),
    )
    collector.append_output("runtime line")
    failure_queue.handle_managed_startup_failure(failure_incident)

    assert fake_recovery_bridge.finished.emissions == []
    assert isinstance(failure_queue, ReadyShellFailureQueue)
    assert isinstance(shell_build_task, ReadyShellBuildTask)
    assert isinstance(target_activation_task, ReadyShellTargetActivationTask)
    assert isinstance(
        local_editor_warmup_adapter,
        ReadyShellLocalEditorWarmupAdapter,
    )
    assert isinstance(managed_startup_prelude, ReadyShellManagedStartupPrelude)
    assert callable(qpane_warmup_callback)
    assert isinstance(post_show_controller, ReadyShellPostShowController)
    assert isinstance(minimum_ready_task, ReadyShellMinimumReadyTask)
    assert isinstance(reveal_task, ReadyShellRevealTask)
    assert isinstance(show_gate_task, ReadyShellShowGateTask)
    assert isinstance(trace_provider, ReadyShellTraceFieldsProvider)
    assert isinstance(metadata_bridge_task, ReadyShellMetadataBridgeTask)
    assert isinstance(prompt_editor_warmup_task, ReadyShellPromptEditorWarmupTask)
    assert isinstance(
        initial_workspace_prehydration_task,
        ReadyShellInitialWorkspacePrehydrationTask,
    )
    assert startup_task_queue.names == [
        "activate_target",
        "start_readiness_timer",
        "build_main_window",
        "wire_metadata_bridge",
        "warm_prompt_editor_gui",
        "prehydrate_initial_workspace",
        "mark_minimum_shell_ready",
    ]
    assert startup_task_queue.started is True
    assert cast(object, metadata_bridge_task.wire()) is metadata_bridge
    assert prompt_editor_warmup_task.warm() is True
    assert warmed_windows == [prompt_editor_window]
    assert registered_bridges == [metadata_bridge]
    assert len(recorded_metadata_bridges) == 1
    assert cast(object, recorded_metadata_bridges[0]) is metadata_bridge
    assert metadata_bridge.model_updated.callbacks == [
        metadata_surface_refresh_controller.handle_model_metadata_updated
    ]
    assert trace_provider()["shell_frame_present"] is True
    assert trace_provider()["provisional_restore_projection_present"] is True
    assert isinstance(recovery_controller, ManagedCompatibilityRecoveryController)
    assert isinstance(readiness_controller, StartupReadinessController)
    assert getattr(readiness_starter, "_controller") is readiness_controller
    assert len(fake_recovery_bridge.finished.callbacks) == 1
    assert callable(resources.create_nonessential_startup_warmup_runtime)
    assert not hasattr(resources, "restored_active_workflow_id")
    assert managed_startup_failures == [failure_incident]
    assert failure_queue_events == ["cancelled", "cleanup", "quit"]
    assert len(presented_reports) == 1
    assert report_kwargs == [
        {
            "installation_context": context,
            "incident": failure_incident,
            "transcript": ("runtime line",),
        }
    ]


def test_managed_ready_runtime_imports_no_forbidden_boundaries() -> None:
    """Managed-ready runtime composition should stay outside UI and infrastructure."""

    imported_modules = _imported_module_names(MANAGED_READY_RUNTIME_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_MANAGED_READY_RUNTIME_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_managed_ready_runtime_resources() -> None:
    """Startup should delegate managed-ready runtime resource setup."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "managed_ready_runtime.startup_diagnostics" not in source
    assert "managed_ready_runtime.startup_ignore_repository" not in source
    assert "managed_ready_runtime.readiness_runtime_adapters" not in source
    assert "managed_ready_runtime.managed_failure_report_adapter" not in source
    assert "managed_ready_runtime.present_startup_failure_report" not in source
    assert "managed_ready_launch.create_failure_queue" in launch_source
    assert "managed_ready_runtime.create_failure_queue" not in source
    assert "managed_ready_launch.create_shell_build_task(" in launch_source
    assert "managed_ready_runtime.create_shell_build_task" not in source
    assert "managed_ready_runtime.managed_startup_compatibility_assessor" not in source
    assert "managed_ready_runtime.activate_target" not in source
    assert "managed_ready_launch.create_target_activation_task(" in launch_source
    assert "managed_ready_runtime.create_target_activation_task" not in source
    assert "managed_ready_runtime.managed_startup_fatal_incident" not in source
    assert "managed_ready_runtime.create_model_metadata_update_bridge" not in source
    assert "managed_ready_launch.create_metadata_bridge_task" in launch_source
    assert "managed_ready_runtime.create_metadata_bridge_task" not in source
    assert "managed_ready_launch.create_ready_trace_fields(" in launch_source
    assert (
        "managed_ready_runtime.create_ready_shell_trace_fields_provider" not in source
    )
    assert "managed_ready_runtime.start_local_editor_startup_warmup" not in source
    assert "managed_ready_launch.create_local_editor_warmup_adapter(" in launch_source
    assert "managed_ready_runtime.create_local_editor_warmup_adapter" not in source
    assert "managed_ready_runtime.start_qpane_sam_startup_warmup" not in source
    assert "managed_ready_launch.create_qpane_sam_warmup_callback(" not in launch_source
    assert "qpane_sam_warmup()" not in launch_source
    assert "managed_ready_launch.create_managed_startup_prelude(" in launch_source
    assert "managed_ready_runtime.create_managed_startup_prelude" not in source
    assert "managed_ready_launch.create_post_show_controller(" in launch_source
    assert "managed_ready_runtime.create_post_show_controller" not in source
    assert (
        "managed_ready_launch.create_nonessential_startup_warmup_runtime"
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_nonessential_startup_warmup_runtime" not in source
    )
    assert "managed_ready_runtime.restored_active_workflow_id" not in source
    assert "managed_ready_runtime.restored_workspace_workflow_count" not in source
    assert "managed_ready_runtime.warm_prompt_editor_gui_from_window" not in source
    assert "managed_ready_launch.create_prompt_editor_warmup_task" in launch_source
    assert "managed_ready_runtime.create_prompt_editor_warmup_task" not in source
    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task" not in source
    )
    assert "managed_ready_launch.create_minimum_ready_task(" in launch_source
    assert "managed_ready_runtime.create_minimum_ready_task" not in source
    assert "managed_ready_launch.create_reveal_task(" in launch_source
    assert "managed_ready_runtime.create_reveal_task" not in source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task" not in source
    assert "managed_ready_launch.schedule_startup_tasks" in launch_source
    assert "managed_ready_runtime.schedule_startup_tasks" not in source
    assert (
        "managed_ready_launch.create_startup_diagnostics_update_adapter"
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_startup_diagnostics_update_adapter" not in source
    )
    assert "managed_ready_runtime.create_readiness_failure_adapter" not in source
    assert "managed_ready_launch.bind_startup_readiness_controller(" in launch_source
    assert "managed_ready_runtime.bind_startup_readiness_controller" not in source
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller"
        not in source
    )
    assert (
        "managed_ready_runtime.create_managed_recovery_startup_adapters" not in source
    )
    assert "startup_adapters=" not in source
    assert "managed_ready_runtime.managed_recovery_controller_adapters" not in source
    assert (
        "managed_ready_runtime.publish_managed_compatibility_recovery_outcome"
        not in source
    )
    assert (
        "managed_ready_runtime.connect_managed_compatibility_recovery_finished"
        not in source
    )
    assert "start_local_editor_warmup=start_local_editor_startup_warmup" not in source
    assert "start_qpane_sam_warmup=start_qpane_sam_startup_warmup" not in source
    assert "fallback_workflow_id=lambda: restored_active_workflow_id" not in source
    assert "workspace_workflow_count=restored_workspace_workflow_count" not in source
    assert (
        "from substitute.app.bootstrap.startup_restore_workspace import" not in source
    )
    assert "managed_ready_runtime.managed_compatibility_checker" not in source
    assert "managed_ready_runtime.managed_compatibility_recovery_bridge" not in source
    assert "managed_ready_ports.create_startup_diagnostics_collector()" not in source
    assert "managed_ready_ports.activate_target" not in source
    assert "create_ready_shell_target_activation_task(" not in source
    assert "create_ready_shell_build_task(" not in source
    assert "managed_ready_ports.managed_startup_fatal_incident" not in source
    assert "managed_ready_ports.present_startup_failure_report" not in source
    assert "create_ready_shell_failure_queue(" not in source
    assert "create_ready_shell_managed_startup_prelude(" not in source
    assert "create_bound_ready_shell_post_show_controller(" not in source
    assert "create_ready_shell_post_show_controller(" not in source
    assert "managed_ready_ports.create_model_metadata_update_bridge" not in source
    assert "create_ready_shell_metadata_bridge_task(" not in source
    assert "create_ready_shell_local_editor_warmup_adapter(" not in source
    assert "create_ready_shell_prompt_editor_warmup_task(" not in source
    assert "create_ready_shell_initial_workspace_prehydration_task(" not in source
    assert "create_ready_shell_minimum_ready_task(" not in source
    assert "create_ready_shell_reveal_task(" not in source
    assert "create_ready_shell_show_gate_task(" not in source
    assert "schedule_ready_shell_controller_startup_tasks(" not in source
    assert "create_startup_managed_failure_report_adapter(" not in source
    assert "create_ready_shell_startup_diagnostics_update_adapter(" not in source
    assert "create_startup_readiness_failure_adapter(" not in source
    assert "create_bound_startup_readiness_controller(" not in source
    assert "from substitute.app.bootstrap.ready_shell_trace_fields import" not in source
    assert "from substitute.app.bootstrap.prompt_editor_gui_warmup import" not in source
    assert (
        "from substitute.app.bootstrap.startup_warmup_controller import" not in source
    )
    assert (
        "from substitute.app.bootstrap.managed_recovery_adapters import" not in source
    )
    assert "connect_managed_compatibility_recovery_bridge(" not in source
    assert (
        "managed_ready_ports.create_startup_diagnostics_ignore_repository(context)"
        not in source
    )
    assert "StartupReadinessRuntimeAdapters(" not in source
    assert "managed_ready_ports.create_runtime_compatibility_checker()" not in source
    assert (
        "managed_ready_ports.create_managed_compatibility_recovery_bridge()"
        not in source
    )
    assert "create_connected_managed_compatibility_recovery_controller(" not in source
    assert (
        "from substitute.app.bootstrap.managed_compatibility_recovery import"
        not in source
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


class _Context:
    """Expose the installation-context target needed by runtime composition."""

    def __init__(self, target: ComfyTargetConfiguration) -> None:
        """Store the managed Comfy target."""

        self.comfy_target = target


def _target(tmp_path: Path) -> ComfyTargetConfiguration:
    """Build one managed target for runtime compatibility tests."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path / "ComfyUI",
        install_owned=True,
        launch_owned=True,
    )


def _relaunch_phase() -> AbstractContextManager[object]:
    """Return a no-op relaunch timing context."""

    return nullcontext()


class _Checker:
    """Record runtime compatibility target assessments."""

    def __init__(self, result: BackendCompatibilityResult) -> None:
        """Store the compatibility result to return."""

        self._result = result
        self.targets: list[ComfyTargetConfiguration] = []

    def assess_target(
        self,
        target: ComfyTargetConfiguration,
    ) -> BackendCompatibilityResult:
        """Record one target assessment."""

        self.targets.append(target)
        return self._result


class _Clock:
    """Return deterministic timestamps for startup timing."""

    def __init__(self) -> None:
        """Initialize the deterministic clock."""

        self._now = 0.0

    def __call__(self) -> float:
        """Return the next timestamp."""

        self._now += 0.1
        return self._now


class _ControllerTimer:
    """Record timer operations needed by controller compatibility handling."""

    def __init__(self) -> None:
        """Initialize recorded timer operations."""

        self.timeout: TimerSignalProtocol = _UnusedTimerSignal()
        self.started = 0
        self.stopped = 0

    def setInterval(self, _interval_ms: int) -> None:
        """Accept interval configuration."""

    def start(self) -> None:
        """Record a timer start."""

        self.started += 1

    def stop(self) -> None:
        """Record a timer stop."""

        self.stopped += 1


class _ControllerReadinessProbe:
    """Record readiness-probe cancellation from controller failure paths."""

    def __init__(self) -> None:
        """Initialize cancellation records."""

        self.cancel_calls = 0

    def connect_finished(self, _callback: Callable[..., object]) -> None:
        """Accept a readiness completion callback."""

    def request_probe(self, *, host: str, port: int) -> int | None:
        """Return a fake readiness request identifier."""

        return 1 if host and port else None

    def accept_result(self, _result: object) -> bool:
        """Accept fake readiness results."""

        return True

    def cancel_current(self) -> None:
        """Record cancellation of the fake readiness probe."""

        self.cancel_calls += 1


class _UnusedTimerSignal:
    """Accept timer signal connections that are unused by this test."""

    def connect(self, _callback: Callable[[], None]) -> None:
        """Accept one timeout callback."""


class _ControllerRuntimeCompatibilityProbe:
    """Accept a current compatibility result for controller routing tests."""

    def connect_finished(self, _callback: Callable[..., object]) -> None:
        """Accept a runtime compatibility completion callback."""

    def request_assessment(self) -> int | None:
        """Return a fake compatibility request identifier."""

        return 1

    def accept_result(self, result: RuntimeCompatibilityProbeResult) -> bool:
        """Accept the one fake compatibility result used by this test."""

        return result.request_id == 1

    def cancel_current(self) -> None:
        """Accept cancellation of the fake compatibility request."""


class _Signal:
    """Record a Qt-compatible signal surface."""

    def __init__(self) -> None:
        """Initialize callback and emission records."""

        self.callbacks: list[Callable[..., object]] = []
        self.emissions: list[tuple[object, ...]] = []

    def connect(self, callback: Callable[..., object]) -> object:
        """Return one connection token."""

        self.callbacks.append(callback)
        return object()

    def emit(self, *_args: object) -> None:
        """Record the emission and notify connected callbacks."""

        self.emissions.append(_args)
        for callback in self.callbacks:
            callback(*_args)


class _MetadataBridge:
    """Expose a connectable metadata-updated signal."""

    def __init__(self) -> None:
        """Initialize the fake metadata signal."""

        self.model_updated = _Signal()

    def emit_model_updated(self, _event: object) -> None:
        """Accept metadata update forwarding."""


class _MetadataSurfaceRefreshController:
    """Record metadata refresh callbacks connected during bridge wiring."""

    def __init__(self) -> None:
        """Initialize received metadata events."""

        self.events: list[object] = []

    def handle_model_metadata_updated(self, event: object) -> None:
        """Record one metadata update event."""

        self.events.append(event)


class _MetadataMainWindow:
    """Expose the metadata surface controller expected by bridge wiring."""

    def __init__(self, controller: _MetadataSurfaceRefreshController) -> None:
        """Store the fake metadata controller."""

        self.model_metadata_surface_refresh_controller = controller


class _StartupTaskQueue:
    """Record scheduled ready-shell startup task names."""

    def __init__(self) -> None:
        """Initialize queued task records."""

        self.names: list[str] = []
        self.started = False

    def add(self, name: str, _callback: Callable[[], None]) -> None:
        """Record one queued task name."""

        self.names.append(name)

    def start(self) -> None:
        """Record queue startup."""

        self.started = True


class _RecoveryBridge:
    """Expose the recovery completion signal used by startup."""

    def __init__(self) -> None:
        """Create the fake finished signal."""

        self.finished = _Signal()


class _ReadyState:
    """Expose ready-shell gate fields used by recovery and tracing."""

    def __init__(self) -> None:
        """Initialize ready-shell gate fields."""

        self.minimum_shell_ready = False
        self.comfy_http_ready = False
        self.comfy_activation_started = False
        self.main_window_shown = False
        self.prehydration_attempted = False
        self.prehydration_succeeded = False
        self.hydration_started = False


class _ReadinessState:
    """Expose readiness fields required by recovery controllers and tracing."""

    def __init__(self) -> None:
        """Initialize readiness fields."""

        self.readiness_attempts = 0
        self.nonessential_startup_warmups_pending_backend = False


class _ProjectionState:
    """Expose pre-show projection fields used by tracing."""

    def __init__(self) -> None:
        """Initialize projection state fields."""

        self.pending = False


class _Splash:
    """Record launch-splash lines emitted through recovery adapters."""

    def __init__(self) -> None:
        """Initialize the recorded line list."""

        self.lines: list[str] = []

    def append_log(self, line: str) -> None:
        """Record one launch-splash line."""

        self.lines.append(line)

    def close(self) -> None:
        """Close the fake splash."""


class _OutputStream:
    """Record Comfy output lines emitted through recovery adapters."""

    def __init__(self) -> None:
        """Initialize the recorded line list."""

        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Record one output line."""

        self.lines.append(line)
