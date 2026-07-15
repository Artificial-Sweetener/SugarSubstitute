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

"""Bind ready-shell launch controller construction for startup."""

from __future__ import annotations

from collections.abc import Callable

from substitute.app.bootstrap.managed_recovery_adapters import (
    ManagedRecoveryOutputStreamProtocol,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellLaunchController,
    create_ready_shell_launch_controller,
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
from substitute.app.bootstrap.startup_managed_ready_shell_launcher import (
    create_startup_managed_ready_shell_launcher,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupShellCompositionPorts,
)
from substitute.app.bootstrap.startup_qt_timers import StartupQtSchedulerPorts
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_shutdown import StartupShutdownRuntime
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.domain.onboarding import InstallationContext


def create_startup_ready_shell_launch_controller(
    *,
    no_comfy: bool,
    startup_cancelled: Callable[[], bool],
    shell_frame_present: Callable[[], bool],
    splash: Callable[[], object | None],
    set_splash: Callable[[object | None], None],
    comfy_output_stream: object,
    shutdown_request: object,
    startup_timer: object,
    runtime_services: object,
    initial_shell_placement: object | None,
    initial_workspace: object | None,
    show_main_window: Callable[..., object],
    attach_gui_reload_command: Callable[[object], None],
    set_current_shell: Callable[[object], None],
    launch_managed_ready_shell: Callable[[InstallationContext], None],
) -> ReadyShellLaunchController:
    """Create the ready-shell launch controller from startup-level ports."""

    return create_ready_shell_launch_controller(
        no_comfy=no_comfy,
        startup_cancelled=startup_cancelled,
        shell_frame_present=shell_frame_present,
        splash=splash,
        set_splash=set_splash,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=shutdown_request,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        initial_shell_placement=initial_shell_placement,
        initial_workspace=initial_workspace,
        show_main_window=show_main_window,
        attach_gui_reload_command=attach_gui_reload_command,
        set_current_shell=set_current_shell,
        launch_managed_ready_shell=launch_managed_ready_shell,
    )


def create_startup_ready_shell_launch_graph(
    *,
    no_comfy: bool,
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
) -> ReadyShellLaunchController:
    """Create the ready-shell controller with its managed-ready launch graph."""

    managed_ready_shell_launcher = create_startup_managed_ready_shell_launcher(
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

    return create_startup_ready_shell_launch_controller(
        no_comfy=no_comfy,
        startup_cancelled=lambda: startup_cancellation_state.cancelled,
        shell_frame_present=lambda: shell_reload_state.shell_frame is not None,
        splash=lambda: ready_shell_reference_state.splash,
        set_splash=ready_shell_reference_state.set_splash,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=request_shell_shutdown,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        initial_shell_placement=initial_shell_placement,
        initial_workspace=initial_workspace,
        show_main_window=shell_ports.show_main_window,
        attach_gui_reload_command=shell_reload_adapter.attach_gui_reload_command,
        set_current_shell=shell_reload_adapter.set_current_shell,
        launch_managed_ready_shell=managed_ready_shell_launcher.launch,
    )


__all__ = [
    "create_startup_ready_shell_launch_controller",
    "create_startup_ready_shell_launch_graph",
]
