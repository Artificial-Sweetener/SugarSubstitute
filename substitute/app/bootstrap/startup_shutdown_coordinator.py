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

"""Create coordinated startup shutdown UI adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from substitute.app.bootstrap.shutdown_coordinator import (
    AppQuitProtocol,
    ShutdownCoordinator,
)
from substitute.app.bootstrap.startup_shutdown import StartupShutdownRuntime
from substitute.presentation.qt.execution import QtOwnerThreadDispatcher


@dataclass(frozen=True)
class StartupShutdownRequestPorts:
    """Group startup shutdown request ports derived from the coordinator."""

    request_shell_shutdown: Callable[[object | None], None]


def create_startup_shutdown_coordinator(
    *,
    app: AppQuitProtocol,
    shutdown_runtime: StartupShutdownRuntime,
    execution_runtime: Any,
) -> ShutdownCoordinator:
    """Create the shell shutdown coordinator for one startup runtime."""

    cleanup_submitter = execution_runtime.submitter(
        "shutdown",
        owner_id="managed_comfy_shutdown",
        dispatcher=QtOwnerThreadDispatcher(),
    )
    return ShutdownCoordinator(
        app=app,
        cleanup=shutdown_runtime.cleanup,
        cleanup_submitter=cleanup_submitter,
        before_cleanup=shutdown_runtime.save_session_before_cleanup,
        skip_cleanup_on_force_close=shutdown_runtime.cleanup_bypass,
    )


def shell_shutdown_request(
    coordinator: ShutdownCoordinator,
) -> Callable[[object | None], None]:
    """Adapt the Qt shutdown coordinator request to an object-level shell port."""

    def request_shutdown(parent_window: object | None = None) -> None:
        """Request shutdown for one optional shell parent window."""

        coordinator.request_shutdown(cast(Any, parent_window))

    return request_shutdown


def create_startup_shutdown_request_ports(
    *,
    app: AppQuitProtocol,
    shutdown_runtime: StartupShutdownRuntime,
    execution_runtime: Any,
) -> StartupShutdownRequestPorts:
    """Create the object-level shutdown request ports used by startup."""

    coordinator = create_startup_shutdown_coordinator(
        app=app,
        shutdown_runtime=shutdown_runtime,
        execution_runtime=execution_runtime,
    )
    return StartupShutdownRequestPorts(
        request_shell_shutdown=shell_shutdown_request(coordinator),
    )


__all__ = [
    "StartupShutdownRequestPorts",
    "create_startup_shutdown_coordinator",
    "create_startup_shutdown_request_ports",
    "shell_shutdown_request",
]
