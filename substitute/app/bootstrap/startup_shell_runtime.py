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

"""Compose startup shell shutdown and reload runtime collaborators."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from substitute.app.bootstrap.ready_shell_state import ReadyShellRuntimeState
from substitute.app.bootstrap.shell_reload_adapter import (
    ComfyRuntimeRestartActions,
    ShellReloadAdapter,
    StartupShellReloadState,
    create_bound_shell_reload_adapter,
)
from substitute.app.bootstrap.startup_ports import StartupShellCompositionPorts
from substitute.app.bootstrap.startup_shutdown import StartupShutdownRuntime
from substitute.app.bootstrap.startup_shutdown_adapter import (
    create_process_manager_startup_shutdown_runtime,
)
from substitute.app.bootstrap.startup_shutdown_coordinator import (
    create_startup_shutdown_request_ports,
)


class StartupShellRuntimeAppProtocol(Protocol):
    """Describe the application quit port needed by shell runtime graph."""

    def quit(self) -> None:
        """Request event-loop shutdown."""


class StartupShellRuntimeServicesProtocol(Protocol):
    """Describe runtime services needed while composing shell runtime ports."""

    @property
    def execution_runtime(self) -> object:
        """Return the process-lifetime execution runtime."""


@dataclass(frozen=True, slots=True)
class StartupShellRuntimeGraph:
    """Group shell shutdown, shutdown-request, and reload collaborators."""

    shutdown_runtime: StartupShutdownRuntime
    request_shell_shutdown: Callable[[object | None], None]
    shell_reload_adapter: ShellReloadAdapter


def create_startup_shell_runtime_graph(
    *,
    app: StartupShellRuntimeAppProtocol,
    ready_shell_runtime_state: ReadyShellRuntimeState,
    shell_reload_state: StartupShellReloadState,
    shell_ports: StartupShellCompositionPorts,
    installation_context: object,
    comfy_output_stream: object,
    startup_timer: object,
    runtime_services: StartupShellRuntimeServicesProtocol,
    restart_launch_command: Sequence[str],
) -> StartupShellRuntimeGraph:
    """Create startup shell shutdown and reload graph collaborators."""

    shutdown_runtime = create_process_manager_startup_shutdown_runtime(
        comfy_state_getter=lambda: ready_shell_runtime_state.comfy_state,
        save_session_before_cleanup=shell_reload_state.save_session_before_cleanup,
    )
    shutdown_request_ports = create_startup_shutdown_request_ports(
        app=app,
        shutdown_runtime=shutdown_runtime,
        execution_runtime=runtime_services.execution_runtime,
    )
    request_shell_shutdown = shutdown_request_ports.request_shell_shutdown
    shell_reload_adapter = create_bound_shell_reload_adapter(
        state=shell_reload_state,
        main_window_for_shell=shell_ports.main_window_for_shell,
        build_main_window=shell_ports.build_main_window,
        show_built_main_window=shell_ports.show_built_main_window,
        comfy_runtime_actions_for=comfy_runtime_actions_for,
        installation_context=installation_context,
        comfy_output_stream=comfy_output_stream,
        shutdown_request=request_shell_shutdown,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        managed_comfy_lease=shutdown_runtime.managed_comfy_lease,
        restart_launch_command=restart_launch_command,
    )
    return StartupShellRuntimeGraph(
        shutdown_runtime=shutdown_runtime,
        request_shell_shutdown=request_shell_shutdown,
        shell_reload_adapter=shell_reload_adapter,
    )


def comfy_runtime_actions_for(candidate: object) -> ComfyRuntimeRestartActions:
    """Return shell runtime actions without importing presentation code early."""

    from substitute.presentation.shell.comfy_runtime_actions import (
        comfy_runtime_actions_for as resolve_comfy_runtime_actions,
    )

    return resolve_comfy_runtime_actions(candidate)


__all__ = [
    "StartupShellRuntimeAppProtocol",
    "StartupShellRuntimeGraph",
    "StartupShellRuntimeServicesProtocol",
    "comfy_runtime_actions_for",
    "create_startup_shell_runtime_graph",
]
