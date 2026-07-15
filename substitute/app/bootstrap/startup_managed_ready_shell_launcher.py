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

"""Launch managed-ready shell startup through explicit state and ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from substitute.app.bootstrap.managed_recovery_adapters import (
    ManagedRecoveryOutputStreamProtocol,
)
from substitute.app.bootstrap.model_metadata_refresh import (
    ModelMetadataRefreshServiceFactory,
    StartupModelMetadataRefreshHandle,
)
from substitute.app.bootstrap.ready_shell_state import (
    ReadyShellReferenceState,
    ReadyShellRuntimeState,
)
from substitute.app.bootstrap.shell_reload_adapter import (
    ShellReloadAdapter,
    StartupShellReloadState,
)
from substitute.app.bootstrap.startup_cancellation import StartupCancellationState
from substitute.app.bootstrap.startup_managed_ready_launch import (
    create_startup_managed_ready_launch_runtime,
)
from substitute.app.bootstrap.startup_model_metadata import (
    StartupModelMetadataProgressSink,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupShellCompositionPorts,
)
from substitute.app.bootstrap.startup_qt_timers import StartupQtSchedulerPorts
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_shutdown import StartupShutdownRuntime
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.application.execution import DirectExecutionDispatcher
from substitute.domain.onboarding import InstallationContext
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher


@dataclass(frozen=True, slots=True)
class StartupManagedReadyShellLauncher:
    """Launch managed-Comfy ready shell startup through composed ports."""

    ready_shell_reference_state: ReadyShellReferenceState
    ready_shell_runtime_state: ReadyShellRuntimeState
    shell_reload_state: StartupShellReloadState
    startup_cancellation_state: StartupCancellationState
    shutdown_runtime: StartupShutdownRuntime
    shell_reload_adapter: ShellReloadAdapter
    shell_ports: StartupShellCompositionPorts
    managed_ready_ports: StartupManagedReadyFactoryPorts
    startup_resources: StartupResourceRegistry
    startup_timer: StartupTimer
    startup_qt_schedulers: StartupQtSchedulerPorts
    connect_cancel_request: Callable[[Callable[[], None]], object]
    emit_splash_cancel: Callable[[], None]
    initial_splash_cancel_connector: Callable[[Callable[[], None]], None] | None
    startup_splash_start_or_adopt: Callable[..., object]
    resolve_appearance: Callable[[], object]
    comfy_output_stream: ManagedRecoveryOutputStreamProtocol
    request_shell_shutdown: Callable[[object | None], None]
    quit_app: Callable[[], None]
    runtime_services: object
    initial_workspace: object | None
    initial_shell_placement: object | None
    provisional_restore_projection: object | None

    def launch(self, context: InstallationContext) -> None:
        """Launch the managed-Comfy shell for a ready installation context."""

        managed_ready_launch = create_startup_managed_ready_launch_runtime(
            context=context,
            comfy_state=lambda: self.ready_shell_runtime_state.comfy_state,
            managed_ready_ports=self.managed_ready_ports,
            startup_resources=self.startup_resources,
            startup_timer=self.startup_timer,
            execution_runtime=cast(Any, self.runtime_services).execution_runtime,
            execution_dispatcher_factory=QtOwnerThreadDispatcher,
        )

        ready_trace_fields = managed_ready_launch.create_ready_trace_fields(
            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            shell_frame_present=lambda: self.shell_reload_state.shell_frame is not None,
            provisional_restore_projection_present=lambda: (
                self.provisional_restore_projection is not None
            ),
        )
        failure_queue = managed_ready_launch.create_failure_queue(
            is_startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            mark_startup_cancelled=self.startup_cancellation_state.cancel,
            managed_comfy_state=lambda: self.ready_shell_runtime_state.comfy_state,
            splash=lambda: self.ready_shell_reference_state.splash,
            cleanup=self.shutdown_runtime.cleanup,
            quit_app=self.quit_app,
            trace_fields=ready_trace_fields,
            scheduler=self.startup_qt_schedulers.single_shot,
        )

        target_activation_task = managed_ready_launch.create_target_activation_task(
            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            splash=lambda: self.ready_shell_reference_state.splash,
            comfy_output_stream=self.comfy_output_stream,
            set_comfy_state=self.ready_shell_runtime_state.set_comfy_state,
            trace_fields=ready_trace_fields,
        )
        if _should_pre_activate_managed_target(context):
            try:
                target_activation_task.activate()
            except Exception:
                failure_queue.request_startup_cancel()
                raise

        resolved_appearance = self.resolve_appearance()
        managed_ready_launch.create_managed_startup_prelude(
            connect_cancel_request=self.connect_cancel_request,
            request_startup_cancel=failure_queue.request_startup_cancel,
            initial_splash_cancel_connector=self.initial_splash_cancel_connector,
            emit_splash_cancel=self.emit_splash_cancel,
            splash=lambda: self.ready_shell_reference_state.splash,
            set_splash=self.ready_shell_reference_state.set_splash,
            startup_timer=self.startup_timer,
            resolved_appearance=resolved_appearance,
            start_or_adopt_launch_splash=self.startup_splash_start_or_adopt,
        ).run()
        local_editor_warmup = managed_ready_launch.create_local_editor_warmup_adapter(
            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            main_window_for_shell=self.shell_ports.main_window_for_shell,
            registry=self.startup_resources,
            trace_fields=ready_trace_fields,
        )

        shell_build_task = managed_ready_launch.create_shell_build_task(
            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            splash=lambda: self.ready_shell_reference_state.splash,
            context=context,
            comfy_output_stream=self.comfy_output_stream,
            shutdown_request=self.request_shell_shutdown,
            startup_timer=self.startup_timer,
            runtime_services=self.runtime_services,
            build_main_window=self.shell_ports.build_main_window,
            attach_gui_reload_command=(
                self.shell_reload_adapter.attach_gui_reload_command
            ),
            set_current_shell=self.shell_reload_adapter.set_current_shell,
            main_window_for_shell=self.shell_ports.main_window_for_shell,
            restore_asset_preload=(
                self.startup_resources.first_workspace_restore_asset_preload
            ),
            trace_fields=ready_trace_fields,
            set_shell_frame=self.shell_reload_state.set_shell_frame,
        )

        metadata_bridge_task = managed_ready_launch.create_metadata_bridge_task(
            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            shell_frame=lambda: self.shell_reload_state.shell_frame,
            register_bridge=self.startup_resources.register_metadata_update_bridge,
            main_window_for_shell=self.shell_ports.main_window_for_shell,
            set_metadata_update_bridge=(
                self.ready_shell_runtime_state.set_metadata_update_bridge
            ),
            trace_fields=ready_trace_fields,
        )
        prompt_editor_warmup_task = (
            managed_ready_launch.create_prompt_editor_warmup_task(
                startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
                shell_frame=lambda: self.shell_reload_state.shell_frame,
                main_window_for_shell=self.shell_ports.main_window_for_shell,
                trace_fields=ready_trace_fields,
            )
        )

        initial_workspace_prehydration_task = (
            managed_ready_launch.create_initial_workspace_prehydration_task(
                startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
                shell_frame=lambda: self.shell_reload_state.shell_frame,
                main_window_for_shell=self.shell_ports.main_window_for_shell,
                workspace=lambda: self.initial_workspace,
                startup_timer=self.startup_timer,
                trace_fields=ready_trace_fields,
            )
        )

        recovery_controller = (
            managed_ready_launch.create_managed_compatibility_recovery_controller(
                splash=lambda: self.ready_shell_reference_state.splash,
                comfy_output_stream=self.comfy_output_stream,
                handle_managed_startup_failure=(
                    failure_queue.handle_managed_startup_failure
                ),
                current_comfy_state=lambda: self.ready_shell_runtime_state.comfy_state,
                set_comfy_state=self.ready_shell_runtime_state.set_comfy_state,
                is_startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
                trace_fields=ready_trace_fields,
                relaunch_phase=lambda: self.startup_timer.phase(
                    "startup.runtime_compatibility.relaunch"
                ),
            )
        )

        nonessential_warmup_runtime = (
            managed_ready_launch.create_nonessential_startup_warmup_runtime(
                startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
                metadata_update_bridge=lambda: (
                    self.ready_shell_runtime_state.metadata_update_bridge
                ),
                shell_frame=lambda: self.shell_reload_state.shell_frame,
                main_window_for_shell=self.shell_ports.main_window_for_shell,
                registry=self.startup_resources,
                model_metadata_refreshes=self.startup_resources.metadata_refreshes,
                model_metadata_service_factory=lambda: (
                    self.shell_ports.build_model_metadata_refresh_service(context)
                ),
                model_metadata_refresh_handle_factory=(
                    self._create_model_metadata_refresh_handle
                ),
                comfy_output_stream=self.comfy_output_stream,
                scheduler=self.startup_qt_schedulers.single_shot,
                trace_fields=ready_trace_fields,
            )
        )

        diagnostics_update_adapter = (
            managed_ready_launch.create_startup_diagnostics_update_adapter(
                startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
                shell_frame_available=lambda: (
                    self.shell_reload_state.shell_frame is not None
                ),
                trace_fields=ready_trace_fields,
            )
        )

        post_show_controller = managed_ready_launch.create_post_show_controller(
            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            shell_frame=lambda: self.shell_reload_state.shell_frame,
            main_window_for_shell=self.shell_ports.main_window_for_shell,
            queue_named_task=failure_queue.add_task,
            start_queue=failure_queue.start_queue,
            workspace=lambda: self.initial_workspace,
            hidden_restore_runtime_prepared=lambda: (
                self.ready_shell_reference_state.hidden_restore_runtime_prepared
            ),
            startup_timer=self.startup_timer,
            schedule_warmups=nonessential_warmup_runtime.schedule,
            schedule_visible_summary=self.startup_qt_schedulers.visible_summary,
            trace_fields=ready_trace_fields,
        )

        shell_reveal_task = managed_ready_launch.create_reveal_task(
            splash=lambda: self.ready_shell_reference_state.splash,
            shell_frame=lambda: self.shell_reload_state.shell_frame,
            initial_shell_placement=lambda: self.initial_shell_placement,
            startup_timer=self.startup_timer,
            show_built_main_window=self.shell_ports.show_built_main_window,
            set_current_shell=self.shell_reload_adapter.set_current_shell,
            schedule_warmups=nonessential_warmup_runtime.schedule,
            request_startup_diagnostics_update=diagnostics_update_adapter.request,
            schedule_post_show_hydration=post_show_controller.schedule_hydration,
            set_shell_frame=self.shell_reload_state.set_shell_frame,
            set_splash=self.ready_shell_reference_state.set_splash,
            trace_fields=ready_trace_fields,
        )

        shell_show_gate_task = managed_ready_launch.create_show_gate_task(
            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            shell_frame=lambda: self.shell_reload_state.shell_frame,
            comfy_state=lambda: self.ready_shell_runtime_state.comfy_state,
            handle_fatal_incident=lambda incident: (
                failure_queue.handle_managed_startup_failure(incident)
            ),
            main_window_for_shell=self.shell_ports.main_window_for_shell,
            workspace=lambda: self.initial_workspace,
            startup_timer=self.startup_timer,
            provisional_restore_projection=lambda: self.provisional_restore_projection,
            startup_cancelled_callback=lambda: (
                self.startup_cancellation_state.cancelled
            ),
            reveal_main_window=shell_reveal_task.reveal,
            scheduler=self.startup_qt_schedulers.single_shot,
            set_hidden_restore_runtime_prepared=(
                self.ready_shell_reference_state.set_hidden_restore_runtime_prepared
            ),
            trace_fields=ready_trace_fields,
        )

        managed_ready_launch.bind_startup_readiness_controller(
            is_startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            readiness_probe=self.shell_ports.is_comfy_http_ready,
            current_comfy_state=lambda: self.ready_shell_runtime_state.comfy_state,
            handle_managed_startup_failure=(
                failure_queue.handle_managed_startup_failure
            ),
            start_managed_compatibility_recovery=recovery_controller.start,
            backend_ready_phase=lambda: self.startup_timer.phase(
                "startup.backend_ready_transition"
            ),
            release_nonessential_startup_warmups=nonessential_warmup_runtime.start,
            try_show_main_window=shell_show_gate_task.run,
            trace_fields=ready_trace_fields,
        )

        def start_post_minimum_ready_warmups() -> None:
            """Start best-effort warmups after the minimum shell can be shown."""

            shell_frame = self.shell_reload_state.shell_frame
            if shell_frame is not None:
                local_editor_warmup.start(shell_frame)

        minimum_shell_ready_task = managed_ready_launch.create_minimum_ready_task(
            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,
            try_show_main_window=shell_show_gate_task.run,
            trace_fields=ready_trace_fields,
            after_mark_ready=start_post_minimum_ready_warmups,
        )
        managed_ready_launch.schedule_startup_tasks(
            queue=failure_queue.queue,
            target_activation_task=target_activation_task,
            shell_build_task=shell_build_task,
            metadata_bridge_task=metadata_bridge_task,
            prompt_editor_warmup_task=prompt_editor_warmup_task,
            initial_workspace_prehydration_task=initial_workspace_prehydration_task,
            minimum_shell_ready_task=minimum_shell_ready_task,
        )

    def _create_model_metadata_refresh_handle(
        self,
        *,
        service_factory: ModelMetadataRefreshServiceFactory,
        progress_sink: StartupModelMetadataProgressSink,
        finished_callback: Callable[[], None] | None,
    ) -> StartupModelMetadataRefreshHandle:
        """Create one startup metadata refresh handle on the runtime execution lane."""

        execution_runtime = getattr(self.runtime_services, "execution_runtime")
        submitter = execution_runtime.submitter(
            "model_metadata",
            owner_id=f"startup_model_metadata_refresh_{id(progress_sink):x}",
            dispatcher=DirectExecutionDispatcher(),
        )
        return StartupModelMetadataRefreshHandle(
            service_factory=service_factory,
            progress_sink=progress_sink,
            submitter=submitter,
            close_submitter=submitter.close,
            finished_callback=finished_callback,
        )


def create_startup_managed_ready_shell_launcher(
    *,
    ready_shell_reference_state: ReadyShellReferenceState,
    ready_shell_runtime_state: ReadyShellRuntimeState,
    shell_reload_state: StartupShellReloadState,
    startup_cancellation_state: StartupCancellationState,
    shutdown_runtime: StartupShutdownRuntime,
    shell_reload_adapter: ShellReloadAdapter,
    shell_ports: StartupShellCompositionPorts,
    managed_ready_ports: StartupManagedReadyFactoryPorts,
    startup_resources: StartupResourceRegistry,
    startup_timer: StartupTimer,
    startup_qt_schedulers: StartupQtSchedulerPorts,
    connect_cancel_request: Callable[[Callable[[], None]], object],
    emit_splash_cancel: Callable[[], None],
    initial_splash_cancel_connector: Callable[[Callable[[], None]], None] | None,
    startup_splash_start_or_adopt: Callable[..., object],
    resolve_appearance: Callable[[], object],
    comfy_output_stream: ManagedRecoveryOutputStreamProtocol,
    request_shell_shutdown: Callable[[object | None], None],
    quit_app: Callable[[], None],
    runtime_services: object,
    initial_workspace: object | None,
    initial_shell_placement: object | None,
    provisional_restore_projection: object | None,
) -> StartupManagedReadyShellLauncher:
    """Create the managed-ready shell launcher used by startup routing."""

    return StartupManagedReadyShellLauncher(
        ready_shell_reference_state=ready_shell_reference_state,
        ready_shell_runtime_state=ready_shell_runtime_state,
        shell_reload_state=shell_reload_state,
        startup_cancellation_state=startup_cancellation_state,
        shutdown_runtime=shutdown_runtime,
        shell_reload_adapter=shell_reload_adapter,
        shell_ports=shell_ports,
        managed_ready_ports=managed_ready_ports,
        startup_resources=startup_resources,
        startup_timer=startup_timer,
        startup_qt_schedulers=startup_qt_schedulers,
        connect_cancel_request=connect_cancel_request,
        emit_splash_cancel=emit_splash_cancel,
        initial_splash_cancel_connector=initial_splash_cancel_connector,
        startup_splash_start_or_adopt=startup_splash_start_or_adopt,
        resolve_appearance=resolve_appearance,
        comfy_output_stream=comfy_output_stream,
        request_shell_shutdown=request_shell_shutdown,
        quit_app=quit_app,
        runtime_services=runtime_services,
        initial_workspace=initial_workspace,
        initial_shell_placement=initial_shell_placement,
        provisional_restore_projection=provisional_restore_projection,
    )


def _should_pre_activate_managed_target(context: InstallationContext) -> bool:
    """Return whether activation can safely begin before theme/prelude work."""

    target = context.comfy_target
    return bool(target.launch_owned and target.workspace_path is not None)


__all__ = (
    "StartupManagedReadyShellLauncher",
    "create_startup_managed_ready_shell_launcher",
)
