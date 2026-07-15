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

"""Run the Qt event loop and perform orderly startup shutdown cleanup."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from substitute.app.bootstrap.startup_trace import close_startup_trace, trace_mark
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("app.bootstrap.startup_event_loop")


class StartupApplicationProtocol(Protocol):
    """Expose the application event loop entry point."""

    def exec(self) -> int:
        """Run the application event loop and return its exit code."""


class StartupSplashProtocol(Protocol):
    """Expose launch-splash cleanup behavior."""

    def close(self) -> None:
        """Close the launch splash."""


class StartupResourceRegistryProtocol(Protocol):
    """Expose startup resource cleanup and retention behavior."""

    def shutdown_all(self) -> None:
        """Release startup-owned resources."""

    def keep_alive_references(self) -> tuple[object, ...]:
        """Return references retained until startup shutdown completes."""


class StartupShutdownRuntimeProtocol(Protocol):
    """Expose managed cleanup and relaunch behavior."""

    def register_shutdown_handlers(self, app: object) -> None:
        """Register process shutdown hooks before event-loop entry."""

    def cleanup(self) -> object:
        """Run managed startup cleanup."""

    def relaunch_after_cleanup_if_requested(
        self,
        *,
        restart_requested: bool,
        restart_launch_command: Sequence[str],
        start_ready_app_process: Callable[[Sequence[str]], bool],
    ) -> None:
        """Relaunch the ready app when requested and cleanup succeeded."""


class StartupShellReloadProtocol(Protocol):
    """Expose GUI reload relaunch state needed after cleanup."""

    @property
    def restart_after_cleanup_requested(self) -> bool:
        """Return whether a ready-app relaunch was requested."""

    @property
    def restart_launch_command(self) -> Sequence[str]:
        """Return the ready-app relaunch command."""


class StartupExecutionRuntimeProtocol(Protocol):
    """Expose process-lifetime execution shutdown."""

    def shutdown(self) -> None:
        """Release execution runtime resources."""


class StartupRuntimeServicesProtocol(Protocol):
    """Expose runtime services needed by event-loop shutdown."""

    @property
    def execution_runtime(self) -> StartupExecutionRuntimeProtocol:
        """Return the process-lifetime execution runtime."""


def run_startup_event_loop_and_shutdown(
    *,
    app: StartupApplicationProtocol,
    splash: StartupSplashProtocol | None,
    startup_resources: StartupResourceRegistryProtocol,
    shutdown_runtime: StartupShutdownRuntimeProtocol,
    shell_reload: StartupShellReloadProtocol,
    runtime_services: StartupRuntimeServicesProtocol,
    start_ready_app_process: Callable[[Sequence[str]], bool],
    keep_alive_references: Sequence[object] = (),
) -> int:
    """Run the app event loop, then close splash, resources, cleanup, and trace."""

    shutdown_runtime.register_shutdown_handlers(app)
    trace_mark("startup.event_loop.enter")
    exit_code = app.exec()
    trace_mark("startup.event_loop.exit", exit_code=exit_code)
    close_launch_splash_for_shutdown(splash)
    startup_resources.shutdown_all()
    trace_mark("startup.shutdown.cleanup.start")
    shutdown_runtime.cleanup()
    trace_mark("startup.shutdown.cleanup.end")
    shutdown_runtime.relaunch_after_cleanup_if_requested(
        restart_requested=shell_reload.restart_after_cleanup_requested,
        restart_launch_command=shell_reload.restart_launch_command,
        start_ready_app_process=start_ready_app_process,
    )
    shutdown_execution_runtime(runtime_services.execution_runtime)
    close_startup_trace()

    # Keep references alive until all shutdown side effects finish.
    _ = (
        splash,
        *startup_resources.keep_alive_references(),
        *keep_alive_references,
    )
    return exit_code


def shutdown_execution_runtime(
    execution_runtime: StartupExecutionRuntimeProtocol,
) -> None:
    """Release process-lifetime execution resources during app shutdown."""

    try:
        execution_runtime.shutdown()
    except Exception:
        log_exception(_LOGGER, "Failed to shut down execution runtime")


def close_launch_splash_for_shutdown(splash: StartupSplashProtocol | None) -> None:
    """Close the launch splash during normal shutdown while preserving cleanup."""

    if splash is None:
        return
    try:
        splash.close()
    except Exception:
        log_exception(_LOGGER, "Failed to close launch splash during shutdown")


__all__ = [
    "StartupApplicationProtocol",
    "StartupResourceRegistryProtocol",
    "StartupExecutionRuntimeProtocol",
    "StartupRuntimeServicesProtocol",
    "StartupShellReloadProtocol",
    "StartupShutdownRuntimeProtocol",
    "StartupSplashProtocol",
    "close_launch_splash_for_shutdown",
    "run_startup_event_loop_and_shutdown",
]
