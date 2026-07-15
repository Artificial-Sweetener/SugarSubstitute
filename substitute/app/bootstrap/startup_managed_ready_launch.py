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

"""Assemble per-launch managed-ready startup state and runtime resources."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass

from substitute.application.backend_compatibility import BackendCompatibilityResult
from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryController,
)
from substitute.app.bootstrap.managed_recovery_adapters import (
    ManagedRecoveryOutputStreamProtocol,
)
from substitute.app.bootstrap.ready_shell_trace_fields import (
    ReadyShellTraceFieldsProvider,
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
    ReadyShellRevealTimerProtocol,
    ReadyShellShowGateTask,
    ReadyShellSplashProtocol,
    ReadyShellStartupDiagnosticsUpdateAdapter,
    ReadyShellTargetActivationTask,
    StartupSplashLogProtocol,
    StartupPhaseTimerProtocol,
)
from substitute.app.bootstrap.startup_failure_controller import SplashCloseProtocol
from substitute.app.bootstrap.startup_managed_ready_runtime import (
    StartupManagedReadyRuntimeResources,
    create_startup_managed_ready_runtime_resources as _create_runtime_resources,
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
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_readiness_controller import (
    StartupReadinessController,
)
from substitute.app.bootstrap.ready_shell_startup_tasks import (
    ReadyShellStartupTaskQueueProtocol,
)
from substitute.app.bootstrap.startup_warmup_controller import (
    NonessentialStartupWarmupRuntime,
    StartupWarmupRegistryProtocol,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident
from substitute.domain.onboarding import InstallationContext


@dataclass(frozen=True, slots=True)
class StartupManagedReadyLaunchRuntime:
    """Group the per-launch mutable state and runtime factory surface."""

    state: StartupManagedReadyStateBundle
    runtime: StartupManagedReadyRuntimeResources

    def create_ready_trace_fields(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame_present: Callable[[], bool],
        provisional_restore_projection_present: Callable[[], bool],
    ) -> ReadyShellTraceFieldsProvider:
        """Bind managed-ready launch state into the trace-field provider."""

        return self.runtime.create_ready_shell_trace_fields_provider(
            startup_cancelled=startup_cancelled,
            shell_frame_present=shell_frame_present,
            ready_state=self.state.ready_state,
            readiness_state=self.state.readiness_controller_state,
            recovery_state=self.state.managed_compatibility_recovery_state,
            pre_show_restore_projection_state=(
                self.state.pre_show_restore_projection_state
            ),
            provisional_restore_projection_present=(
                provisional_restore_projection_present
            ),
        )

    def create_failure_queue(
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
        """Delegate failure queue construction through the launch runtime."""

        return self.runtime.create_failure_queue(
            is_startup_cancelled=is_startup_cancelled,
            mark_startup_cancelled=mark_startup_cancelled,
            managed_comfy_state=managed_comfy_state,
            splash=splash,
            cleanup=cleanup,
            quit_app=quit_app,
            trace_fields=trace_fields,
            scheduler=scheduler,
        )

    def create_target_activation_task(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        splash: Callable[[], object | None],
        comfy_output_stream: object,
        set_comfy_state: Callable[[object | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellTargetActivationTask:
        """Bind managed-ready launch state into the target activation task."""

        return self.runtime.create_target_activation_task(
            startup_cancelled=startup_cancelled,
            splash=splash,
            comfy_output_stream=comfy_output_stream,
            state=self.state.ready_state,
            set_comfy_state=set_comfy_state,
            trace_fields=trace_fields,
        )

    def create_metadata_bridge_task(
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
        """Delegate metadata bridge task construction through the launch runtime."""

        return self.runtime.create_metadata_bridge_task(
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            register_bridge=register_bridge,
            main_window_for_shell=main_window_for_shell,
            set_metadata_update_bridge=set_metadata_update_bridge,
            trace_fields=trace_fields,
        )

    def create_prompt_editor_warmup_task(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object | None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellPromptEditorWarmupTask:
        """Delegate prompt-editor warmup task construction through the launch runtime."""

        return self.runtime.create_prompt_editor_warmup_task(
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            trace_fields=trace_fields,
        )

    def create_local_editor_warmup_adapter(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        main_window_for_shell: Callable[[object], object],
        registry: object,
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellLocalEditorWarmupAdapter:
        """Bind managed-ready launch state into the local-editor warmup adapter."""

        return self.runtime.create_local_editor_warmup_adapter(
            state=self.state.startup_warmup_state,
            startup_cancelled=startup_cancelled,
            main_window_for_shell=main_window_for_shell,
            registry=registry,
            trace_fields=trace_fields,
        )

    def create_managed_startup_prelude(
        self,
        *,
        connect_cancel_request: Callable[[Callable[[], None]], object],
        request_startup_cancel: Callable[[], None],
        initial_splash_cancel_connector: Callable[[Callable[[], None]], None] | None,
        emit_splash_cancel: Callable[[], None],
        splash: Callable[[], object | None],
        set_splash: Callable[[object | None], None],
        startup_timer: object,
        resolved_appearance: object,
        start_or_adopt_launch_splash: Callable[..., object],
    ) -> ReadyShellManagedStartupPrelude:
        """Bind managed-ready launch state into the startup prelude."""

        return self.runtime.create_managed_startup_prelude(
            connect_cancel_request=connect_cancel_request,
            request_startup_cancel=request_startup_cancel,
            initial_splash_cancel_connector=initial_splash_cancel_connector,
            emit_splash_cancel=emit_splash_cancel,
            splash=splash,
            set_splash=set_splash,
            startup_timer=startup_timer,
            resolved_appearance=resolved_appearance,
            start_or_adopt_launch_splash=start_or_adopt_launch_splash,
        )

    def create_qpane_sam_warmup_callback(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        registry: StartupWarmupRegistryProtocol,
        trace_fields: Callable[[], dict[str, object]],
    ) -> Callable[[], None]:
        """Bind managed-ready launch state into delayed QPane SAM warmup."""

        warmup_callback: Callable[[], None] = (
            self.runtime.create_qpane_sam_warmup_callback(
                state=self.state.startup_warmup_state,
                startup_cancelled=startup_cancelled,
                registry=registry,
                trace_fields=trace_fields,
            )
        )
        return warmup_callback

    def create_shell_build_task(
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
        set_shell_frame: Callable[[object], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellBuildTask:
        """Bind managed-ready launch state into the shell-build task."""

        return self.runtime.create_shell_build_task(
            startup_cancelled=startup_cancelled,
            splash=splash,
            context=context,
            comfy_output_stream=comfy_output_stream,
            shutdown_request=shutdown_request,
            startup_timer=startup_timer,
            runtime_services=runtime_services,
            build_main_window=build_main_window,
            attach_gui_reload_command=attach_gui_reload_command,
            set_current_shell=set_current_shell,
            main_window_for_shell=main_window_for_shell,
            restore_asset_preload=restore_asset_preload,
            comfy_http_ready=lambda: self.state.ready_state.comfy_http_ready,
            set_backend_state=self.state.backend_state_updater.update,
            set_shell_frame=set_shell_frame,
            trace_fields=trace_fields,
        )

    def create_initial_workspace_prehydration_task(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object],
        workspace: Callable[[], object | None],
        startup_timer: StartupPhaseTimerProtocol,
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellInitialWorkspacePrehydrationTask:
        """Bind managed-ready launch state into workspace prehydration."""

        return self.runtime.create_initial_workspace_prehydration_task(
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            workspace=workspace,
            startup_timer=startup_timer,
            state=self.state.ready_state,
            trace_fields=trace_fields,
        )

    def create_minimum_ready_task(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
        after_mark_ready: Callable[[], object] | None = None,
    ) -> ReadyShellMinimumReadyTask:
        """Bind managed-ready launch state into the minimum-ready task."""

        return self.runtime.create_minimum_ready_task(
            startup_cancelled=startup_cancelled,
            state=self.state.ready_state,
            try_show_main_window=try_show_main_window,
            trace_fields=trace_fields,
            after_mark_ready=after_mark_ready,
        )

    def schedule_startup_tasks(
        self,
        *,
        queue: ReadyShellStartupTaskQueueProtocol,
        target_activation_task: ReadyShellTargetActivationTask,
        shell_build_task: ReadyShellBuildTask,
        metadata_bridge_task: ReadyShellMetadataBridgeTask,
        prompt_editor_warmup_task: ReadyShellPromptEditorWarmupTask,
        initial_workspace_prehydration_task: ReadyShellInitialWorkspacePrehydrationTask,
        minimum_shell_ready_task: ReadyShellMinimumReadyTask,
    ) -> None:
        """Bind the readiness starter into managed-ready startup scheduling."""

        self.runtime.schedule_startup_tasks(
            queue=queue,
            target_activation_task=target_activation_task,
            start_readiness_timer=self.state.readiness_starter.start,
            shell_build_task=shell_build_task,
            metadata_bridge_task=metadata_bridge_task,
            prompt_editor_warmup_task=prompt_editor_warmup_task,
            initial_workspace_prehydration_task=initial_workspace_prehydration_task,
            minimum_shell_ready_task=minimum_shell_ready_task,
        )

    def create_reveal_task(
        self,
        *,
        splash: Callable[[], ReadyShellSplashProtocol | None],
        shell_frame: Callable[[], object | None],
        initial_shell_placement: Callable[[], object | None],
        startup_timer: ReadyShellRevealTimerProtocol,
        show_built_main_window: Callable[..., object],
        set_current_shell: Callable[[object], None],
        schedule_warmups: Callable[[str], None],
        request_startup_diagnostics_update: Callable[[object], object],
        schedule_post_show_hydration: Callable[[], object],
        set_shell_frame: Callable[[object], None],
        set_splash: Callable[[ReadyShellSplashProtocol | None], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellRevealTask:
        """Bind managed-ready launch state into the reveal task."""

        return self.runtime.create_reveal_task(
            splash=splash,
            shell_frame=shell_frame,
            initial_shell_placement=initial_shell_placement,
            comfy_http_ready=lambda: self.state.ready_state.comfy_http_ready,
            startup_timer=startup_timer,
            show_built_main_window=show_built_main_window,
            set_current_shell=set_current_shell,
            update_backend_state=self.state.backend_state_updater.update,
            startup_warmup_state=self.state.startup_warmup_state,
            schedule_warmups=schedule_warmups,
            request_startup_diagnostics_update=request_startup_diagnostics_update,
            schedule_post_show_hydration=schedule_post_show_hydration,
            set_shell_frame=set_shell_frame,
            set_splash=set_splash,
            trace_fields=trace_fields,
        )

    def create_show_gate_task(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        comfy_state: Callable[[], object | None],
        handle_fatal_incident: Callable[[object], object],
        main_window_for_shell: Callable[[object], object],
        workspace: Callable[[], object | None],
        startup_timer: StartupPhaseTimerProtocol,
        provisional_restore_projection: Callable[[], object | None],
        startup_cancelled_callback: Callable[[], bool],
        reveal_main_window: Callable[[object], object],
        scheduler: Callable[[int, Callable[[], None]], None],
        set_hidden_restore_runtime_prepared: Callable[[bool], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellShowGateTask:
        """Bind managed-ready launch state into the show-gate task."""

        return self.runtime.create_show_gate_task(
            startup_cancelled=startup_cancelled,
            state=self.state.ready_state,
            pre_show_projection_pending=(
                lambda: self.state.pre_show_restore_projection_state.pending
            ),
            minimum_shell_ready=lambda: self.state.ready_state.minimum_shell_ready,
            comfy_http_ready=lambda: self.state.ready_state.comfy_http_ready,
            shell_frame=shell_frame,
            comfy_state=comfy_state,
            handle_fatal_incident=handle_fatal_incident,
            main_window_for_shell=main_window_for_shell,
            workspace=workspace,
            prehydration_succeeded=(
                lambda: self.state.ready_state.prehydration_succeeded
            ),
            startup_timer=startup_timer,
            pre_show_projection_state=self.state.pre_show_restore_projection_state,
            provisional_restore_projection=provisional_restore_projection,
            startup_cancelled_callback=startup_cancelled_callback,
            reveal_main_window=reveal_main_window,
            scheduler=scheduler,
            set_hidden_restore_runtime_prepared=set_hidden_restore_runtime_prepared,
            trace_fields=trace_fields,
        )

    def create_post_show_controller(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object],
        queue_named_task: Callable[[str, Callable[[], None]], None],
        start_queue: Callable[[], None],
        workspace: Callable[[], object | None],
        hidden_restore_runtime_prepared: Callable[[], bool],
        startup_timer: StartupTimer,
        schedule_warmups: Callable[[str], None],
        schedule_visible_summary: Callable[[Callable[[], None]], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> ReadyShellPostShowController:
        """Bind managed-ready launch state into the post-show controller."""

        return self.runtime.create_post_show_controller(
            backend_state_updater=self.state.backend_state_updater,
            startup_cancelled=startup_cancelled,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            state=self.state.ready_state,
            queue_named_task=queue_named_task,
            start_queue=start_queue,
            workspace=workspace,
            hidden_restore_runtime_prepared=hidden_restore_runtime_prepared,
            prehydration_succeeded=(
                lambda: self.state.ready_state.prehydration_succeeded
            ),
            startup_timer=startup_timer,
            schedule_warmups=schedule_warmups,
            schedule_visible_summary=schedule_visible_summary,
            trace_fields=trace_fields,
        )

    def create_nonessential_startup_warmup_runtime(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        metadata_update_bridge: Callable[[], object | None],
        shell_frame: Callable[[], object | None],
        main_window_for_shell: Callable[[object], object | None],
        registry: object,
        model_metadata_refreshes: Callable[[], object],
        model_metadata_service_factory: Callable[[], object],
        model_metadata_refresh_handle_factory: Callable[..., object],
        comfy_output_stream: object,
        scheduler: Callable[[int, Callable[[], None]], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> NonessentialStartupWarmupRuntime:
        """Bind managed-ready launch state into nonessential warmups."""

        return self.runtime.create_nonessential_startup_warmup_runtime(
            state=self.state.startup_warmup_state,
            startup_cancelled=startup_cancelled,
            comfy_http_ready=lambda: self.state.ready_state.comfy_http_ready,
            readiness_state=self.state.readiness_controller_state,
            metadata_update_bridge=metadata_update_bridge,
            shell_frame=shell_frame,
            main_window_for_shell=main_window_for_shell,
            registry=registry,
            model_metadata_refresh_state=self.state.model_metadata_refresh_state,
            model_metadata_refreshes=model_metadata_refreshes,
            model_metadata_service_factory=model_metadata_service_factory,
            model_metadata_refresh_handle_factory=model_metadata_refresh_handle_factory,
            comfy_output_stream=comfy_output_stream,
            scheduler=scheduler,
            trace_fields=trace_fields,
        )

    def create_startup_diagnostics_update_adapter(
        self,
        *,
        startup_cancelled: Callable[[], bool],
        shell_frame_available: Callable[[], bool],
        trace_fields: Callable[[], dict[str, object]],
    ) -> ReadyShellStartupDiagnosticsUpdateAdapter:
        """Delegate diagnostics update adapter construction through launch runtime."""

        return self.runtime.create_startup_diagnostics_update_adapter(
            startup_cancelled=startup_cancelled,
            shell_frame_available=shell_frame_available,
            trace_fields=trace_fields,
        )

    def create_managed_compatibility_recovery_controller(
        self,
        *,
        splash: Callable[[], LaunchSplashClient | None],
        comfy_output_stream: ManagedRecoveryOutputStreamProtocol,
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        current_comfy_state: Callable[[], object | None],
        set_comfy_state: Callable[[object | None], None],
        is_startup_cancelled: Callable[[], bool],
        trace_fields: Callable[[], dict[str, object]],
        relaunch_phase: Callable[[], AbstractContextManager[object]],
    ) -> ManagedCompatibilityRecoveryController:
        """Bind managed-ready launch state into compatibility recovery."""

        return self.runtime.create_managed_compatibility_recovery_controller(
            state=self.state.managed_compatibility_recovery_state,
            comfy_ready_state=self.state.ready_state,
            readiness_state=self.state.readiness_controller_state,
            splash=splash,
            comfy_output_stream=comfy_output_stream,
            handle_managed_startup_failure=handle_managed_startup_failure,
            current_comfy_state=current_comfy_state,
            set_comfy_state=set_comfy_state,
            set_backend_state=self.state.backend_state_updater.update,
            is_startup_cancelled=is_startup_cancelled,
            restart_readiness_timer=self.state.readiness_starter.start,
            trace_fields=trace_fields,
            relaunch_phase=relaunch_phase,
        )

    def bind_startup_readiness_controller(
        self,
        *,
        is_startup_cancelled: Callable[[], bool],
        readiness_probe: Callable[[str, int], bool],
        current_comfy_state: Callable[[], object | None],
        handle_managed_startup_failure: Callable[[ComfyStartupIncident], None],
        start_managed_compatibility_recovery: Callable[
            [BackendCompatibilityResult], None
        ],
        backend_ready_phase: Callable[[], AbstractContextManager[object]],
        release_nonessential_startup_warmups: Callable[[], None],
        try_show_main_window: Callable[[], None],
        trace_fields: Callable[[], Mapping[str, object]],
    ) -> StartupReadinessController:
        """Bind managed-ready launch state into readiness orchestration."""

        recovery_state = self.state.managed_compatibility_recovery_state
        controller: StartupReadinessController = (
            self.runtime.bind_startup_readiness_controller(
                starter=self.state.readiness_starter,
                state=self.state.readiness_controller_state,
                comfy_http_ready_state=self.state.ready_state,
                is_startup_cancelled=is_startup_cancelled,
                readiness_probe=readiness_probe,
                current_comfy_state=current_comfy_state,
                handle_managed_startup_failure=handle_managed_startup_failure,
                recovery_attempted=lambda: recovery_state.recovery_attempted,
                recovery_running=lambda: recovery_state.recovery_running,
                start_managed_compatibility_recovery=(
                    start_managed_compatibility_recovery
                ),
                set_backend_state=self.state.backend_state_updater.update,
                backend_ready_phase=backend_ready_phase,
                release_nonessential_startup_warmups=(
                    release_nonessential_startup_warmups
                ),
                try_show_main_window=try_show_main_window,
                trace_fields=trace_fields,
            )
        )
        return controller


def create_startup_managed_ready_launch_runtime(
    *,
    context: InstallationContext,
    comfy_state: Callable[[], object | None],
    managed_ready_ports: StartupManagedReadyFactoryPorts,
    startup_resources: StartupResourceRegistry,
    startup_timer: StartupTimer,
    execution_runtime: object,
    execution_dispatcher_factory: Callable[[], object],
) -> StartupManagedReadyLaunchRuntime:
    """Create the state and runtime resources for one managed-ready launch."""

    return StartupManagedReadyLaunchRuntime(
        state=create_startup_managed_ready_state_bundle(),
        runtime=_create_runtime_resources(
            context=context,
            comfy_state=comfy_state,
            managed_ready_ports=managed_ready_ports,
            startup_resources=startup_resources,
            startup_timer=startup_timer,
            execution_runtime=execution_runtime,
            execution_dispatcher_factory=execution_dispatcher_factory,
        ),
    )


__all__ = (
    "StartupManagedReadyLaunchRuntime",
    "create_startup_managed_ready_launch_runtime",
)
