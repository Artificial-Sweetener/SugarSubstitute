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

"""Own managed-ready startup runtime resource composition."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.startup_warmup_controller import (
    NonessentialStartupWarmupRuntime,
    StartupWarmupState,
    StartupWarmupRegistryProtocol,
    create_nonessential_startup_warmup_runtime,
    start_local_editor_startup_warmup,
    start_qpane_sam_startup_warmup,
)
from substitute.app.bootstrap.startup_restore_workspace import (
    restored_active_workflow_id,
    restored_workspace_workflow_count,
)
from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryController,
    ManagedCompatibilityRecoveryControllerState,
    ManagedRecoveryComfyReadyStateProtocol,
    ManagedRecoveryReadinessStateProtocol,
    create_connected_managed_compatibility_recovery_controller,
)
from substitute.app.bootstrap.managed_recovery_adapters import (
    ManagedRecoveryOutputStreamProtocol,
    ManagedRecoveryStartupAdapters,
    create_managed_recovery_controller_adapters,
    create_managed_recovery_startup_adapters,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
)
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.app.bootstrap.startup_readiness_runtime import (
    StartupReadinessRuntimeAdapters,
)
from substitute.app.bootstrap.startup_readiness_controller import (
    ComfyHttpReadyStateProtocol,
    StartupReadinessController,
    StartupReadinessControllerState,
    StartupReadinessFailureAdapter,
    StartupReadinessStarter,
    create_bound_startup_readiness_controller,
    create_startup_readiness_failure_adapter,
)
from substitute.app.bootstrap.ready_shell_trace_fields import (
    ManagedCompatibilityRecoveryTraceStateProtocol,
    PreShowRestoreProjectionTraceStateProtocol,
    ReadyShellGateStateProtocol,
    ReadyShellTraceFieldsProvider,
    StartupReadinessTraceStateProtocol,
    create_ready_shell_trace_fields_provider,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellActivationStateProtocol,
    ReadyShellBackendStateUpdater,
    ReadyShellBuildTask,
    ReadyShellFailureQueue,
    ReadyShellHydrationStateProtocol,
    ReadyShellInitialWorkspacePrehydrationTask,
    ReadyShellLocalEditorWarmupAdapter,
    ReadyShellManagedStartupPrelude,
    ReadyShellMetadataBridgeTask,
    ReadyShellMinimumReadyStateProtocol,
    ReadyShellMinimumReadyTask,
    ReadyShellPostShowController,
    ReadyShellPrehydrationStateProtocol,
    ReadyShellPromptEditorWarmupTask,
    ReadyShellRevealTask,
    ReadyShellRevealTimerProtocol,
    ReadyShellSplashProtocol,
    ReadyShellShowGateTask,
    ReadyShellShowStateProtocol,
    StartupSplashLogProtocol,
    StartupPhaseTimerProtocol,
    ReadyShellStartupDiagnosticsUpdateAdapter,
    ReadyShellTargetActivationTask,
    create_bound_ready_shell_post_show_controller,
    create_ready_shell_build_task,
    create_ready_shell_failure_queue,
    create_ready_shell_initial_workspace_prehydration_task,
    create_ready_shell_local_editor_warmup_adapter,
    create_ready_shell_managed_startup_prelude,
    create_ready_shell_metadata_bridge_task,
    create_ready_shell_minimum_ready_task,
    create_ready_shell_prompt_editor_warmup_task,
    create_ready_shell_reveal_task,
    create_ready_shell_show_gate_task,
    create_ready_shell_startup_diagnostics_update_adapter,
    create_ready_shell_target_activation_task,
    schedule_ready_shell_controller_startup_tasks,
)
from substitute.app.bootstrap.ready_shell_startup_tasks import (
    ReadyShellStartupTaskQueueProtocol,
)
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionState,
)
from substitute.app.bootstrap.startup_failure_controller import (
    SplashCloseProtocol,
    create_startup_managed_failure_report_adapter,
)
from substitute.app.bootstrap.startup_signal_bridges import (
    connect_managed_compatibility_recovery_bridge,
)
from substitute.app.bootstrap.runtime_compatibility import (
    create_managed_startup_compatibility_assessor,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.application.execution import ExecutionContext, TaskIdentity
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import InstallationContext
from substitute.app.bootstrap.process_pump_execution import (
    ProcessPumpTaskHandle,
    ProcessPumpWork,
    create_process_pump_task,
)


class StartupManagedRecoverySignalProtocol(Protocol):
    """Describe the Qt-compatible signal surface used by recovery startup."""

    def connect(self, callback: Callable[..., object]) -> object:
        """Connect a callback to the signal."""

    def emit(self, *args: object) -> None:
        """Emit the signal with arbitrary startup recovery payloads."""


class StartupManagedCompatibilityRecoveryBridgeProtocol(Protocol):
    """Describe the managed compatibility recovery GUI-thread bridge."""

    @property
    def finished(self) -> StartupManagedRecoverySignalProtocol:
        """Return the recovery completion signal."""


class ManagedCompatibilityRecoveryControllerFactory(Protocol):
    """Create the live managed compatibility recovery controller."""

    def __call__(
        self,
        *,
        state: ManagedCompatibilityRecoveryControllerState,
        comfy_ready_state: ManagedRecoveryComfyReadyStateProtocol,
        readiness_state: ManagedRecoveryReadinessStateProtocol,
        splash: Callable[[], LaunchSplashClient | None],
        comfy_output_stream: ManagedRecoveryOutputStreamProtocol,
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        current_comfy_state: Callable[[], object | None],
        set_comfy_state: Callable[[object | None], None],
        set_backend_state: Callable[[str], None],
        is_startup_cancelled: Callable[[], bool],
        restart_readiness_timer: Callable[[], None],
        trace_fields: Callable[[], dict[str, object]],
        relaunch_phase: Callable[[], AbstractContextManager[object]],
    ) -> ManagedCompatibilityRecoveryController:
        """Return the connected recovery controller for one managed launch."""


class StartupReadinessControllerBinder(Protocol):
    """Bind the live startup readiness controller for a managed-ready launch."""

    def __call__(
        self,
        *,
        starter: StartupReadinessStarter,
        state: StartupReadinessControllerState,
        comfy_http_ready_state: ComfyHttpReadyStateProtocol,
        is_startup_cancelled: Callable[[], bool],
        readiness_probe: Callable[[str, int], bool],
        current_comfy_state: Callable[[], object | None],
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        recovery_attempted: Callable[[], bool],
        recovery_running: Callable[[], bool],
        start_managed_compatibility_recovery: Callable[
            [BackendCompatibilityResult], None
        ],
        set_backend_state: Callable[[str], None],
        backend_ready_phase: Callable[[], AbstractContextManager[object]],
        release_nonessential_startup_warmups: Callable[[], None],
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> StartupReadinessController:
        """Return the bound readiness controller for one managed launch."""


class ReadyShellFailureQueueFactory(Protocol):
    """Create failure queues from live managed-ready startup ports."""

    def __call__(
        self,
        *,
        is_startup_cancelled: Callable[[], bool],
        mark_startup_cancelled: Callable[[], None],
        managed_comfy_state: Callable[[], object | None],
        splash: Callable[[], SplashCloseProtocol | None],
        cleanup: Callable[[], object],
        quit_app: Callable[[], None],
        trace_fields: Callable[[], dict[str, object]],
        scheduler: Callable[[int, Callable[[], None]], None],
    ) -> ReadyShellFailureQueue:
        """Return the failure queue for one managed-ready launch."""


class ReadyShellBuildTaskFactory(Protocol):
    """Create shell build tasks from live managed-ready startup ports."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        splash: Callable[[], StartupSplashLogProtocol | None],
        context: object,
        comfy_output_stream: object,
        shutdown_request: Callable[[object | None], None],
        startup_timer: StartupPhaseTimerProtocol,
        runtime_services: object,
        build_main_window: Callable[..., object],
        attach_gui_reload_command: Callable[[object], None],
        set_current_shell: Callable[[object], None],
        main_window_for_shell: Callable[[object], object],
        restore_asset_preload: Callable[[], object | None],
        comfy_http_ready: Callable[[], bool],
        set_backend_state: Callable[[str], object],
        set_shell_frame: Callable[[object], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellBuildTask:
        """Return the shell build task for one managed launch."""


class ReadyShellTargetActivationTaskFactory(Protocol):
    """Create target activation tasks from live managed-ready startup ports."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        splash: Callable[[], object | None],
        comfy_output_stream: object,
        state: ReadyShellActivationStateProtocol,
        set_comfy_state: Callable[[object | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellTargetActivationTask:
        """Return the target activation task for one managed launch."""


class ReadyShellMetadataBridgeTaskFactory(Protocol):
    """Create metadata bridge queue tasks from live ready-shell ports."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        register_bridge: Callable[[object], object],
        main_window_for_shell: Callable[[object], object],
        set_metadata_update_bridge: Callable[
            [ModelMetadataUpdateSignalBridgeProtocol | None], None
        ],
        trace_fields: Callable[[], dict[str, object]],
    ) -> ReadyShellMetadataBridgeTask:
        """Return the metadata bridge task for one managed launch."""


class ReadyShellPromptEditorWarmupTaskFactory(Protocol):
    """Create prompt-editor warmup queue tasks from live ready-shell ports."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object | None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellPromptEditorWarmupTask:
        """Return the prompt-editor warmup task for one managed launch."""


class ReadyShellInitialWorkspacePrehydrationTaskFactory(Protocol):
    """Create initial workspace prehydration tasks from live ready-shell ports."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object],
        workspace: Callable[[], object | None],
        startup_timer: StartupPhaseTimerProtocol,
        state: ReadyShellPrehydrationStateProtocol,
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellInitialWorkspacePrehydrationTask:
        """Return the initial workspace prehydration task for one managed launch."""


class ReadyShellLocalEditorWarmupAdapterFactory(Protocol):
    """Create local-editor warmup adapters from live ready-shell ports."""

    def __call__(
        self,
        *,
        state: StartupWarmupState,
        startup_cancelled: Callable[[], bool],
        main_window_for_shell: Callable[[object], object],
        registry: object,
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellLocalEditorWarmupAdapter:
        """Return the local-editor warmup adapter for one managed launch."""


class ReadyShellManagedStartupPreludeFactory(Protocol):
    """Create managed ready-shell preludes from live startup ports."""

    def __call__(
        self,
        *,
        connect_cancel_request: Callable[[Callable[[], None]], object],
        request_startup_cancel: Callable[[], None],
        initial_splash_cancel_connector: (Callable[[Callable[[], None]], None] | None),
        emit_splash_cancel: Callable[[], None],
        splash: Callable[[], object | None],
        set_splash: Callable[[object | None], None],
        startup_timer: object,
        resolved_appearance: object,
        start_or_adopt_launch_splash: Callable[..., object],
    ) -> ReadyShellManagedStartupPrelude:
        """Return the managed ready-shell startup prelude for one launch."""


class QPaneSamWarmupCallbackFactory(Protocol):
    """Create a delayed QPane SAM warmup callback from launch state."""

    def __call__(
        self,
        *,
        state: StartupWarmupState,
        startup_cancelled: Callable[[], bool],
        registry: StartupWarmupRegistryProtocol,
        trace_fields: Callable[[], dict[str, object]],
    ) -> Callable[[], None]:
        """Return a callback that starts QPane SAM warmup when invoked."""


class ReadyShellPostShowControllerFactory(Protocol):
    """Create post-show controllers from live managed-ready startup ports."""

    def __call__(
        self,
        *,
        backend_state_updater: ReadyShellBackendStateUpdater,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object],
        state: ReadyShellHydrationStateProtocol,
        queue_named_task: Callable[[str, Callable[[], None]], None],
        start_queue: Callable[[], None],
        workspace: Callable[[], object | None],
        hidden_restore_runtime_prepared: Callable[[], bool],
        prehydration_succeeded: Callable[[], bool],
        startup_timer: StartupTimer,
        schedule_warmups: Callable[[str], None],
        schedule_visible_summary: Callable[[Callable[[], None]], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellPostShowController:
        """Return the post-show controller for one managed launch."""


class ReadyShellMinimumReadyTaskFactory(Protocol):
    """Create minimum-ready tasks from live managed-ready startup ports."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        state: ReadyShellMinimumReadyStateProtocol,
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
        after_mark_ready: Callable[[], object] | None = None,
    ) -> ReadyShellMinimumReadyTask:
        """Return the minimum-ready task for one managed launch."""


class ReadyShellRevealTaskFactory(Protocol):
    """Create reveal tasks from live managed-ready startup ports."""

    def __call__(
        self,
        *,
        splash: Callable[[], ReadyShellSplashProtocol | None],
        shell_frame: Callable[[], object | None],
        initial_shell_placement: Callable[[], object | None],
        comfy_http_ready: Callable[[], bool],
        startup_timer: ReadyShellRevealTimerProtocol,
        show_built_main_window: Callable[..., object],
        set_current_shell: Callable[[object], None],
        update_backend_state: Callable[[str], object],
        startup_warmup_state: StartupWarmupState,
        schedule_warmups: Callable[[str], None],
        request_startup_diagnostics_update: Callable[[object], object],
        schedule_post_show_hydration: Callable[[], object],
        set_shell_frame: Callable[[object], None],
        set_splash: Callable[[ReadyShellSplashProtocol | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellRevealTask:
        """Return the reveal task for one managed launch."""


class ReadyShellStartupTaskScheduler(Protocol):
    """Schedule ready-shell startup tasks through the canonical queue owner."""

    def __call__(
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
        """Schedule all managed-ready startup tasks."""


class ReadyShellShowGateTaskFactory(Protocol):
    """Create show-gate tasks from live managed-ready startup ports."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        state: ReadyShellShowStateProtocol,
        pre_show_projection_pending: Callable[[], bool],
        minimum_shell_ready: Callable[[], bool],
        comfy_http_ready: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        comfy_state: Callable[[], object | None],
        handle_fatal_incident: Callable[[object], object],
        main_window_for_shell: Callable[[object], object],
        workspace: Callable[[], object | None],
        prehydration_succeeded: Callable[[], bool],
        startup_timer: StartupPhaseTimerProtocol,
        pre_show_projection_state: PreShowRestoreProjectionState,
        provisional_restore_projection: Callable[[], object | None],
        startup_cancelled_callback: Callable[[], bool],
        reveal_main_window: Callable[[object], object],
        scheduler: Callable[[int, Callable[[], None]], None],
        set_hidden_restore_runtime_prepared: Callable[[bool], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellShowGateTask:
        """Return the show-gate task for one managed launch."""


class ReadyShellStartupDiagnosticsUpdateAdapterFactory(Protocol):
    """Create diagnostics update adapters from live ready-shell ports."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame_available: Callable[[], bool],
        trace_fields: Callable[[], dict[str, object]],
    ) -> ReadyShellStartupDiagnosticsUpdateAdapter:
        """Return the diagnostics update adapter for one managed launch."""


class ReadyShellTraceFieldsProviderFactory(Protocol):
    """Create ready-shell trace field providers from live launch state."""

    def __call__(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame_present: Callable[[], bool],
        ready_state: ReadyShellGateStateProtocol,
        readiness_state: StartupReadinessTraceStateProtocol,
        recovery_state: ManagedCompatibilityRecoveryTraceStateProtocol,
        pre_show_restore_projection_state: PreShowRestoreProjectionTraceStateProtocol,
        provisional_restore_projection_present: Callable[[], bool],
    ) -> ReadyShellTraceFieldsProvider:
        """Return the prompt-safe ready-shell trace field provider."""


@dataclass(frozen=True, slots=True)
class StartupManagedReadyRuntimeResources:
    """Group runtime resources created for one managed-ready startup launch."""

    create_failure_queue: ReadyShellFailureQueueFactory
    create_shell_build_task: ReadyShellBuildTaskFactory
    create_target_activation_task: ReadyShellTargetActivationTaskFactory
    create_metadata_bridge_task: ReadyShellMetadataBridgeTaskFactory
    create_local_editor_warmup_adapter: ReadyShellLocalEditorWarmupAdapterFactory
    create_managed_startup_prelude: ReadyShellManagedStartupPreludeFactory
    create_qpane_sam_warmup_callback: QPaneSamWarmupCallbackFactory
    create_post_show_controller: ReadyShellPostShowControllerFactory
    create_ready_shell_trace_fields_provider: ReadyShellTraceFieldsProviderFactory
    create_nonessential_startup_warmup_runtime: Callable[
        ..., NonessentialStartupWarmupRuntime
    ]
    create_prompt_editor_warmup_task: ReadyShellPromptEditorWarmupTaskFactory
    create_initial_workspace_prehydration_task: (
        ReadyShellInitialWorkspacePrehydrationTaskFactory
    )
    create_minimum_ready_task: ReadyShellMinimumReadyTaskFactory
    create_reveal_task: ReadyShellRevealTaskFactory
    create_show_gate_task: ReadyShellShowGateTaskFactory
    schedule_startup_tasks: ReadyShellStartupTaskScheduler
    create_startup_diagnostics_update_adapter: (
        ReadyShellStartupDiagnosticsUpdateAdapterFactory
    )
    bind_startup_readiness_controller: StartupReadinessControllerBinder
    create_managed_compatibility_recovery_controller: (
        ManagedCompatibilityRecoveryControllerFactory
    )


def create_startup_managed_ready_runtime_resources(
    *,
    context: InstallationContext,
    comfy_state: Callable[[], object | None],
    managed_ready_ports: StartupManagedReadyFactoryPorts,
    startup_resources: StartupResourceRegistry,
    startup_timer: StartupTimer,
    execution_runtime: object,
    execution_dispatcher_factory: Callable[[], object],
) -> StartupManagedReadyRuntimeResources:
    """Create runtime resources consumed by managed-ready startup orchestration."""

    managed_compatibility_checker = (
        managed_ready_ports.create_runtime_compatibility_checker()
    )
    startup_diagnostics = managed_ready_ports.create_startup_diagnostics_collector()
    startup_ignore_repository = (
        managed_ready_ports.create_startup_diagnostics_ignore_repository(context)
    )
    managed_compatibility_recovery_bridge = cast(
        StartupManagedCompatibilityRecoveryBridgeProtocol,
        managed_ready_ports.create_managed_compatibility_recovery_bridge(),
    )
    readiness_runtime_adapters = StartupReadinessRuntimeAdapters(
        startup_resources=startup_resources,
        startup_timer=startup_timer,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=execution_dispatcher_factory,
    )
    managed_startup_compatibility_assessor = (
        create_managed_startup_compatibility_assessor(
            comfy_state=comfy_state,
            checker=managed_compatibility_checker,
            target=context.comfy_target,
        )
    )

    def managed_process_task_factory(
        identity: TaskIdentity,
        task_context: ExecutionContext,
        work: ProcessPumpWork,
        thread_name: str,
    ) -> ProcessPumpTaskHandle:
        """Create one managed process execution task for this startup runtime."""

        return create_process_pump_task(
            execution_runtime=execution_runtime,
            dispatcher_factory=execution_dispatcher_factory,
            identity=identity,
            context=task_context,
            work=work,
            thread_name=thread_name,
        )

    managed_failure_report_adapter = create_startup_managed_failure_report_adapter(
        installation_context=context,
        transcript=lambda: startup_diagnostics.transcript(),
        build_report=managed_ready_ports.build_startup_failure_report,
    )

    def build_failure_queue(
        *,
        is_startup_cancelled: Callable[[], bool],
        mark_startup_cancelled: Callable[[], None],
        managed_comfy_state: Callable[[], object | None],
        splash: Callable[[], SplashCloseProtocol | None],
        cleanup: Callable[[], object],
        quit_app: Callable[[], None],
        trace_fields: Callable[[], dict[str, object]],
        scheduler: Callable[[int, Callable[[], None]], None],
    ) -> ReadyShellFailureQueue:
        """Bind ready-shell failure queue construction to this runtime."""

        return create_ready_shell_failure_queue(
            is_startup_cancelled=is_startup_cancelled,
            mark_startup_cancelled=mark_startup_cancelled,
            readiness_timers=readiness_runtime_adapters.readiness_timers,
            runtime_compatibility_probes=lambda: tuple(
                startup_resources.runtime_compatibility_probes
            ),
            managed_comfy_state=managed_comfy_state,
            splash=splash,
            cleanup=cleanup,
            quit_app=quit_app,
            trace_fields=trace_fields,
            managed_failure_report_factory=managed_failure_report_adapter.build,
            present_startup_failure_report=(
                managed_ready_ports.present_startup_failure_report
            ),
            scheduler=scheduler,
            startup_timer=startup_timer,
        )

    def build_target_activation_task(
        *,
        startup_cancelled: Callable[[], bool],
        splash: Callable[[], object | None],
        comfy_output_stream: object,
        state: ReadyShellActivationStateProtocol,
        set_comfy_state: Callable[[object | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellTargetActivationTask:
        """Bind managed target activation task construction to this runtime."""

        return create_ready_shell_target_activation_task(
            startup_cancelled=startup_cancelled,
            splash=splash,
            installation_context=context,
            comfy_output_stream=comfy_output_stream,
            startup_diagnostics=startup_diagnostics,
            startup_timer=startup_timer,
            activate_target=lambda **kwargs: managed_ready_ports.activate_target(
                **kwargs,
                launch_task_factory=managed_process_task_factory,
                process_pump_task_factory=managed_process_task_factory,
            ),
            state=state,
            set_comfy_state=set_comfy_state,
            trace_fields=trace_fields,
        )

    def build_shell_build_task(
        *,
        startup_cancelled: Callable[[], bool],
        splash: Callable[[], StartupSplashLogProtocol | None],
        context: object,
        comfy_output_stream: object,
        shutdown_request: Callable[[object | None], None],
        startup_timer: StartupPhaseTimerProtocol,
        runtime_services: object,
        build_main_window: Callable[..., object],
        attach_gui_reload_command: Callable[[object], None],
        set_current_shell: Callable[[object], None],
        main_window_for_shell: Callable[[object], object],
        restore_asset_preload: Callable[[], object | None],
        comfy_http_ready: Callable[[], bool],
        set_backend_state: Callable[[str], object],
        set_shell_frame: Callable[[object], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellBuildTask:
        """Bind diagnostics ignore storage into the shell build task."""

        return create_ready_shell_build_task(
            startup_cancelled=startup_cancelled,
            splash=splash,
            context=context,
            comfy_output_stream=comfy_output_stream,
            shutdown_request=shutdown_request,
            startup_timer=startup_timer,
            runtime_services=runtime_services,
            startup_diagnostics_ignore_repository=startup_ignore_repository,
            build_main_window=build_main_window,
            attach_gui_reload_command=attach_gui_reload_command,
            set_current_shell=set_current_shell,
            main_window_for_shell=main_window_for_shell,
            restore_asset_preload=restore_asset_preload,
            comfy_http_ready=comfy_http_ready,
            set_backend_state=set_backend_state,
            set_shell_frame=set_shell_frame,
            trace_fields=trace_fields,
        )

    def build_managed_recovery_startup_adapters(
        *,
        splash: Callable[[], LaunchSplashClient | None],
        comfy_output_stream: ManagedRecoveryOutputStreamProtocol,
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
    ) -> ManagedRecoveryStartupAdapters:
        """Bind recovery startup adapters to this launch context and diagnostics."""

        return create_managed_recovery_startup_adapters(
            installation_context=context,
            splash=splash,
            comfy_output_stream=comfy_output_stream,
            startup_diagnostics=startup_diagnostics,
            handle_managed_startup_failure=handle_managed_startup_failure,
            launch_task_factory=managed_process_task_factory,
            process_pump_task_factory=managed_process_task_factory,
        )

    def build_ready_shell_trace_fields_provider(
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame_present: Callable[[], bool],
        ready_state: ReadyShellGateStateProtocol,
        readiness_state: StartupReadinessTraceStateProtocol,
        recovery_state: ManagedCompatibilityRecoveryTraceStateProtocol,
        pre_show_restore_projection_state: PreShowRestoreProjectionTraceStateProtocol,
        provisional_restore_projection_present: Callable[[], bool],
    ) -> ReadyShellTraceFieldsProvider:
        """Bind prompt-safe trace field assembly for this managed launch."""

        return create_ready_shell_trace_fields_provider(
            startup_cancelled=startup_cancelled,
            shell_frame_present=shell_frame_present,
            ready_state=ready_state,
            readiness_state=readiness_state,
            recovery_state=recovery_state,
            pre_show_restore_projection_state=pre_show_restore_projection_state,
            provisional_restore_projection_present=(
                provisional_restore_projection_present
            ),
        )

    def build_metadata_bridge_task(
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        register_bridge: Callable[[object], object],
        main_window_for_shell: Callable[[object], object],
        set_metadata_update_bridge: Callable[
            [ModelMetadataUpdateSignalBridgeProtocol | None], None
        ],
        trace_fields: Callable[[], dict[str, object]],
    ) -> ReadyShellMetadataBridgeTask:
        """Bind model metadata bridge construction to this managed runtime."""

        return create_ready_shell_metadata_bridge_task(
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            bridge_factory=managed_ready_ports.create_model_metadata_update_bridge,
            register_bridge=register_bridge,
            main_window_for_shell=main_window_for_shell,
            set_metadata_update_bridge=set_metadata_update_bridge,
            trace_fields=trace_fields,
        )

    def build_local_editor_warmup_adapter(
        *,
        state: StartupWarmupState,
        startup_cancelled: Callable[[], bool],
        main_window_for_shell: Callable[[object], object],
        registry: object,
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellLocalEditorWarmupAdapter:
        """Bind local-editor warmup startup to this managed runtime."""

        return create_ready_shell_local_editor_warmup_adapter(
            state=state,
            startup_cancelled=startup_cancelled,
            main_window_for_shell=main_window_for_shell,
            registry=registry,
            trace_fields=trace_fields,
            start_local_editor_warmup=start_local_editor_startup_warmup,
        )

    def build_managed_startup_prelude(
        *,
        connect_cancel_request: Callable[[Callable[[], None]], object],
        request_startup_cancel: Callable[[], None],
        initial_splash_cancel_connector: (Callable[[Callable[[], None]], None] | None),
        emit_splash_cancel: Callable[[], None],
        splash: Callable[[], object | None],
        set_splash: Callable[[object | None], None],
        startup_timer: object,
        resolved_appearance: object,
        start_or_adopt_launch_splash: Callable[..., object],
    ) -> ReadyShellManagedStartupPrelude:
        """Bind launch-splash startup wiring into the managed prelude."""

        return create_ready_shell_managed_startup_prelude(
            connect_cancel_request=connect_cancel_request,
            request_startup_cancel=request_startup_cancel,
            initial_splash_cancel_connector=initial_splash_cancel_connector,
            emit_splash_cancel=emit_splash_cancel,
            splash=splash,
            set_splash=set_splash,
            startup_timer=startup_timer,
            resolved_appearance=resolved_appearance,
            start_or_adopt_launch_splash=lambda **kwargs: start_or_adopt_launch_splash(
                **kwargs,
                process_pump_task_factory=managed_process_task_factory,
            ),
        )

    def build_qpane_sam_warmup_callback(
        *,
        state: StartupWarmupState,
        startup_cancelled: Callable[[], bool],
        registry: StartupWarmupRegistryProtocol,
        trace_fields: Callable[[], dict[str, object]],
    ) -> Callable[[], None]:
        """Bind delayed QPane SAM warmup to this managed runtime."""

        def start_qpane_sam_after_minimum_ready() -> None:
            """Start QPane SAM warmup after first shell readiness."""

            start_qpane_sam_startup_warmup(
                state=state,
                startup_cancelled=startup_cancelled(),
                registry=registry,
                trace_fields=trace_fields,
                execution_runtime=execution_runtime,
            )

        return start_qpane_sam_after_minimum_ready

    def build_post_show_controller(
        *,
        backend_state_updater: ReadyShellBackendStateUpdater,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object],
        state: ReadyShellHydrationStateProtocol,
        queue_named_task: Callable[[str, Callable[[], None]], None],
        start_queue: Callable[[], None],
        workspace: Callable[[], object | None],
        hidden_restore_runtime_prepared: Callable[[], bool],
        prehydration_succeeded: Callable[[], bool],
        startup_timer: StartupTimer,
        schedule_warmups: Callable[[str], None],
        schedule_visible_summary: Callable[[Callable[[], None]], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellPostShowController:
        """Bind backend-state updates into the post-show controller."""

        return create_bound_ready_shell_post_show_controller(
            backend_state_updater=backend_state_updater,
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            state=state,
            queue_named_task=queue_named_task,
            start_queue=start_queue,
            workspace=workspace,
            hidden_restore_runtime_prepared=hidden_restore_runtime_prepared,
            prehydration_succeeded=prehydration_succeeded,
            startup_timer=startup_timer,
            schedule_warmups=schedule_warmups,
            schedule_visible_summary=schedule_visible_summary,
            trace_fields=trace_fields,
        )

    def build_prompt_editor_warmup_task(
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object | None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellPromptEditorWarmupTask:
        """Bind prompt-editor GUI warmup to this managed runtime."""

        return create_ready_shell_prompt_editor_warmup_task(
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            warm_prompt_editor_gui=warm_prompt_editor_gui_from_window,
            trace_fields=trace_fields,
        )

    def build_initial_workspace_prehydration_task(
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object],
        workspace: Callable[[], object | None],
        startup_timer: StartupPhaseTimerProtocol,
        state: ReadyShellPrehydrationStateProtocol,
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellInitialWorkspacePrehydrationTask:
        """Bind restored workspace fact lookup to the prehydration task."""

        return create_ready_shell_initial_workspace_prehydration_task(
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            workspace=workspace,
            startup_timer=startup_timer,
            workspace_workflow_count=restored_workspace_workflow_count,
            state=state,
            trace_fields=trace_fields,
        )

    def build_minimum_ready_task(
        *,
        startup_cancelled: Callable[[], bool],
        state: ReadyShellMinimumReadyStateProtocol,
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
        after_mark_ready: Callable[[], object] | None = None,
    ) -> ReadyShellMinimumReadyTask:
        """Bind minimum-ready task construction to this managed runtime."""

        return create_ready_shell_minimum_ready_task(
            startup_cancelled=startup_cancelled,
            state=state,
            try_show_main_window=try_show_main_window,
            trace_fields=trace_fields,
            after_mark_ready=after_mark_ready,
        )

    def build_reveal_task(
        *,
        splash: Callable[[], ReadyShellSplashProtocol | None],
        shell_frame: Callable[[], object | None],
        initial_shell_placement: Callable[[], object | None],
        comfy_http_ready: Callable[[], bool],
        startup_timer: ReadyShellRevealTimerProtocol,
        show_built_main_window: Callable[..., object],
        set_current_shell: Callable[[object], None],
        update_backend_state: Callable[[str], object],
        startup_warmup_state: StartupWarmupState,
        schedule_warmups: Callable[[str], None],
        request_startup_diagnostics_update: Callable[[object], object],
        schedule_post_show_hydration: Callable[[], object],
        set_shell_frame: Callable[[object], None],
        set_splash: Callable[[ReadyShellSplashProtocol | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellRevealTask:
        """Bind reveal task construction to this managed runtime."""

        return create_ready_shell_reveal_task(
            splash=splash,
            shell_frame=shell_frame,
            initial_shell_placement=initial_shell_placement,
            comfy_http_ready=comfy_http_ready,
            startup_timer=startup_timer,
            show_built_main_window=show_built_main_window,
            set_current_shell=set_current_shell,
            update_backend_state=update_backend_state,
            startup_warmup_state=startup_warmup_state,
            schedule_warmups=schedule_warmups,
            request_startup_diagnostics_update=request_startup_diagnostics_update,
            schedule_post_show_hydration=schedule_post_show_hydration,
            set_shell_frame=set_shell_frame,
            set_splash=set_splash,
            trace_fields=trace_fields,
        )

    def build_show_gate_task(
        *,
        startup_cancelled: Callable[[], bool],
        state: ReadyShellShowStateProtocol,
        pre_show_projection_pending: Callable[[], bool],
        minimum_shell_ready: Callable[[], bool],
        comfy_http_ready: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        comfy_state: Callable[[], object | None],
        handle_fatal_incident: Callable[[object], object],
        main_window_for_shell: Callable[[object], object],
        workspace: Callable[[], object | None],
        prehydration_succeeded: Callable[[], bool],
        startup_timer: StartupPhaseTimerProtocol,
        pre_show_projection_state: PreShowRestoreProjectionState,
        provisional_restore_projection: Callable[[], object | None],
        startup_cancelled_callback: Callable[[], bool],
        reveal_main_window: Callable[[object], object],
        scheduler: Callable[[int, Callable[[], None]], None],
        set_hidden_restore_runtime_prepared: Callable[[bool], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellShowGateTask:
        """Bind fatal-incident and restored-workflow lookups to the show gate."""

        return create_ready_shell_show_gate_task(
            startup_cancelled=startup_cancelled,
            state=state,
            pre_show_projection_pending=pre_show_projection_pending,
            minimum_shell_ready=minimum_shell_ready,
            comfy_http_ready=comfy_http_ready,
            shell_frame=shell_frame,
            comfy_state=comfy_state,
            fatal_incident_for_state=managed_ready_ports.managed_startup_fatal_incident,
            handle_fatal_incident=handle_fatal_incident,
            main_window_for_shell=main_window_for_shell,
            workspace=workspace,
            prehydration_succeeded=prehydration_succeeded,
            startup_timer=startup_timer,
            pre_show_projection_state=pre_show_projection_state,
            provisional_restore_projection=provisional_restore_projection,
            fallback_workflow_id=lambda: restored_active_workflow_id(workspace()),
            startup_cancelled_callback=startup_cancelled_callback,
            reveal_main_window=reveal_main_window,
            scheduler=scheduler,
            set_hidden_restore_runtime_prepared=set_hidden_restore_runtime_prepared,
            trace_fields=trace_fields,
        )

    def schedule_startup_tasks(
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
        """Bind ready-shell task scheduling to this managed runtime."""

        schedule_ready_shell_controller_startup_tasks(
            queue=queue,
            target_activation_task=target_activation_task,
            start_readiness_timer=start_readiness_timer,
            shell_build_task=shell_build_task,
            metadata_bridge_task=metadata_bridge_task,
            prompt_editor_warmup_task=prompt_editor_warmup_task,
            initial_workspace_prehydration_task=initial_workspace_prehydration_task,
            minimum_shell_ready_task=minimum_shell_ready_task,
        )

    def build_readiness_failure_adapter(
        *,
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
    ) -> StartupReadinessFailureAdapter:
        """Bind readiness failure reporting to this launch context."""

        return create_startup_readiness_failure_adapter(
            installation_context=context,
            transcript=startup_diagnostics.transcript,
            handle_managed_startup_failure=handle_managed_startup_failure,
            build_readiness_timeout_incident=(
                managed_ready_ports.build_startup_readiness_timeout_incident
            ),
            build_runtime_compatibility_incident=(
                managed_ready_ports.build_startup_runtime_compatibility_incident
            ),
        )

    def build_startup_diagnostics_update_adapter(
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame_available: Callable[[], bool],
        trace_fields: Callable[[], dict[str, object]],
    ) -> ReadyShellStartupDiagnosticsUpdateAdapter:
        """Bind diagnostics update requests to this managed-ready runtime."""

        return create_ready_shell_startup_diagnostics_update_adapter(
            incidents=startup_diagnostics.incidents,
            transcript=startup_diagnostics.transcript,
            ignore_repository=startup_ignore_repository,
            installation_context=context,
            startup_resources=startup_resources,
            execution_runtime=execution_runtime,
            execution_dispatcher_factory=execution_dispatcher_factory,
            startup_cancelled=startup_cancelled,
            shell_frame_available=shell_frame_available,
            request_update=(
                managed_ready_ports.request_startup_diagnostics_titlebar_update
            ),
            trace_fields=trace_fields,
        )

    def bind_startup_readiness_controller(
        *,
        starter: StartupReadinessStarter,
        state: StartupReadinessControllerState,
        comfy_http_ready_state: ComfyHttpReadyStateProtocol,
        is_startup_cancelled: Callable[[], bool],
        readiness_probe: Callable[[str, int], bool],
        current_comfy_state: Callable[[], object | None],
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        recovery_attempted: Callable[[], bool],
        recovery_running: Callable[[], bool],
        start_managed_compatibility_recovery: Callable[
            [BackendCompatibilityResult], None
        ],
        set_backend_state: Callable[[str], None],
        backend_ready_phase: Callable[[], AbstractContextManager[object]],
        release_nonessential_startup_warmups: Callable[[], None],
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> StartupReadinessController:
        """Bind the readiness controller to this managed-ready runtime."""

        readiness_failure_adapter = build_readiness_failure_adapter(
            handle_managed_startup_failure=handle_managed_startup_failure,
        )
        return create_bound_startup_readiness_controller(
            starter=starter,
            state=state,
            comfy_http_ready_state=comfy_http_ready_state,
            target=context.comfy_target,
            timer_factory=readiness_runtime_adapters.create_readiness_timer,
            readiness_probe_factory=(readiness_runtime_adapters.create_readiness_probe),
            runtime_compatibility_probe_factory=(
                readiness_runtime_adapters.create_runtime_compatibility_probe
            ),
            register_timer=readiness_runtime_adapters.register_timer,
            register_readiness_probe=(
                readiness_runtime_adapters.register_readiness_probe
            ),
            register_runtime_compatibility_probe=(
                readiness_runtime_adapters.register_runtime_compatibility_probe
            ),
            is_startup_cancelled=is_startup_cancelled,
            readiness_probe=readiness_probe,
            assess_runtime_compatibility=managed_startup_compatibility_assessor.assess,
            fatal_incident=lambda: managed_ready_ports.managed_startup_fatal_incident(
                current_comfy_state()
            ),
            handle_managed_startup_failure=handle_managed_startup_failure,
            build_readiness_timeout_incident=(
                readiness_failure_adapter.build_readiness_timeout_incident
            ),
            handle_runtime_compatibility_failure=(
                readiness_failure_adapter.handle_runtime_compatibility_failure
            ),
            recovery_attempted=recovery_attempted,
            recovery_running=recovery_running,
            start_managed_compatibility_recovery=(start_managed_compatibility_recovery),
            set_backend_state=set_backend_state,
            backend_ready_phase=backend_ready_phase,
            mark_startup_timer=readiness_runtime_adapters.mark_startup_timer,
            release_nonessential_startup_warmups=(release_nonessential_startup_warmups),
            try_show_main_window=try_show_main_window,
            trace_fields=trace_fields,
        )

    def build_managed_compatibility_recovery_controller(
        *,
        state: ManagedCompatibilityRecoveryControllerState,
        comfy_ready_state: ManagedRecoveryComfyReadyStateProtocol,
        readiness_state: ManagedRecoveryReadinessStateProtocol,
        splash: Callable[[], LaunchSplashClient | None],
        comfy_output_stream: ManagedRecoveryOutputStreamProtocol,
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        current_comfy_state: Callable[[], object | None],
        set_comfy_state: Callable[[object | None], None],
        set_backend_state: Callable[[str], None],
        is_startup_cancelled: Callable[[], bool],
        restart_readiness_timer: Callable[[], None],
        trace_fields: Callable[[], dict[str, object]],
        relaunch_phase: Callable[[], AbstractContextManager[object]],
    ) -> ManagedCompatibilityRecoveryController:
        """Bind live recovery controller wiring to this managed-ready runtime."""

        startup_adapters = build_managed_recovery_startup_adapters(
            splash=splash,
            comfy_output_stream=comfy_output_stream,
            handle_managed_startup_failure=handle_managed_startup_failure,
        )
        return create_connected_managed_compatibility_recovery_controller(
            state=state,
            comfy_ready_state=comfy_ready_state,
            readiness_state=readiness_state,
            target=context.comfy_target,
            controller_adapters=managed_recovery_controller_adapters,
            startup_adapters=startup_adapters,
            current_comfy_state=current_comfy_state,
            set_comfy_state=set_comfy_state,
            set_backend_state=set_backend_state,
            publish_outcome=managed_compatibility_recovery_bridge.finished.emit,
            connect_finished=lambda callback: (
                connect_managed_compatibility_recovery_bridge(
                    bridge=managed_compatibility_recovery_bridge,
                    callback=callback,
                )
            ),
            is_startup_cancelled=is_startup_cancelled,
            restart_readiness_timer=restart_readiness_timer,
            trace_fields=trace_fields,
            relaunch_phase=relaunch_phase,
        )

    managed_recovery_controller_adapters = create_managed_recovery_controller_adapters(
        startup_resources=startup_resources,
        execution_runtime=execution_runtime,
        execution_dispatcher_factory=execution_dispatcher_factory,
    )

    return StartupManagedReadyRuntimeResources(
        create_failure_queue=build_failure_queue,
        create_shell_build_task=build_shell_build_task,
        create_target_activation_task=build_target_activation_task,
        create_metadata_bridge_task=build_metadata_bridge_task,
        create_local_editor_warmup_adapter=build_local_editor_warmup_adapter,
        create_managed_startup_prelude=build_managed_startup_prelude,
        create_qpane_sam_warmup_callback=build_qpane_sam_warmup_callback,
        create_post_show_controller=build_post_show_controller,
        create_ready_shell_trace_fields_provider=(
            build_ready_shell_trace_fields_provider
        ),
        create_nonessential_startup_warmup_runtime=(
            create_nonessential_startup_warmup_runtime
        ),
        create_prompt_editor_warmup_task=build_prompt_editor_warmup_task,
        create_initial_workspace_prehydration_task=(
            build_initial_workspace_prehydration_task
        ),
        create_minimum_ready_task=build_minimum_ready_task,
        create_reveal_task=build_reveal_task,
        create_show_gate_task=build_show_gate_task,
        schedule_startup_tasks=schedule_startup_tasks,
        create_startup_diagnostics_update_adapter=(
            build_startup_diagnostics_update_adapter
        ),
        bind_startup_readiness_controller=bind_startup_readiness_controller,
        create_managed_compatibility_recovery_controller=(
            build_managed_compatibility_recovery_controller
        ),
    )


def warm_prompt_editor_gui_from_window(main_window: object) -> object:
    """Warm prompt editor GUI costs without importing the warmup module early."""

    from substitute.app.bootstrap.prompt_editor_gui_warmup import (
        warm_prompt_editor_gui_from_window,
    )

    return warm_prompt_editor_gui_from_window(main_window)


__all__ = (
    "ManagedCompatibilityRecoveryControllerFactory",
    "ReadyShellBuildTaskFactory",
    "ReadyShellFailureQueueFactory",
    "ReadyShellInitialWorkspacePrehydrationTaskFactory",
    "ReadyShellLocalEditorWarmupAdapterFactory",
    "ReadyShellManagedStartupPreludeFactory",
    "ReadyShellMetadataBridgeTaskFactory",
    "ReadyShellMinimumReadyTaskFactory",
    "ReadyShellPostShowControllerFactory",
    "ReadyShellPromptEditorWarmupTaskFactory",
    "ReadyShellRevealTaskFactory",
    "ReadyShellShowGateTaskFactory",
    "ReadyShellStartupDiagnosticsUpdateAdapterFactory",
    "ReadyShellStartupTaskScheduler",
    "ReadyShellTargetActivationTaskFactory",
    "ReadyShellTraceFieldsProviderFactory",
    "StartupReadinessControllerBinder",
    "StartupManagedCompatibilityRecoveryBridgeProtocol",
    "StartupManagedReadyRuntimeResources",
    "StartupManagedRecoverySignalProtocol",
    "create_startup_managed_ready_runtime_resources",
)
