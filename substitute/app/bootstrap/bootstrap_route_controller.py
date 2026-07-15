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

"""Coordinate non-ready bootstrap routes and onboarding completion handoff."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.domain.onboarding import (
    BootstrapRoute,
    InstallationContext,
    ReadinessAssessment,
)
from substitute.app.bootstrap.startup_trace import trace_mark
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("app.bootstrap.bootstrap_route_controller")


class BootstrapSignalProtocol(Protocol):
    """Describe the signal surface used by onboarding and repair windows."""

    def connect(self, callback: Callable[..., object]) -> None:
        """Connect one signal callback."""


class BootstrapRouteWindowProtocol(Protocol):
    """Describe the window signals used by startup route handling."""

    @property
    def launch_requested(self) -> BootstrapSignalProtocol:
        """Return the signal emitted when setup can launch the ready app."""

    @property
    def close_requested(self) -> BootstrapSignalProtocol:
        """Return the signal emitted when the route window requests app close."""


class SplashCloseProtocol(Protocol):
    """Describe the launch splash close surface used before route handoff."""

    def close(self) -> object:
        """Close the splash surface."""


ShowBootstrapWindow = Callable[..., BootstrapRouteWindowProtocol]


@dataclass(frozen=True, slots=True)
class BootstrapRouteResult:
    """Return startup-owned references after non-ready route handling."""

    onboarding_window: BootstrapRouteWindowProtocol
    splash: object | None


class BootstrapRouteController:
    """Own onboarding/repair route presentation and completion handoff."""

    def __init__(
        self,
        *,
        no_comfy: bool,
        start_ready_app_process: Callable[[Sequence[str]], bool],
        launch_ready_shell: Callable[[InstallationContext], None],
        quit_app: Callable[[], None],
    ) -> None:
        """Store ports needed to continue after onboarding or repair."""

        self._no_comfy = no_comfy
        self._start_ready_app_process = start_ready_app_process
        self._launch_ready_shell = launch_ready_shell
        self._quit_app = quit_app

    def launch_after_onboarding_completion(self, completion: object) -> None:
        """Start a ready app process after setup saves configuration."""

        context = cast(
            InstallationContext,
            getattr(completion, "context", completion),
        )
        raw_launch_command = getattr(completion, "launch_command", ())
        launch_command = [str(part) for part in raw_launch_command]
        trace_mark(
            "onboarding_completion.launch_requested",
            launch_command_present=bool(launch_command),
            no_comfy=self._no_comfy,
        )
        if launch_command:
            if self._no_comfy and "--no-comfy" not in launch_command:
                launch_command.append("--no-comfy")
            if self._start_ready_app_process(launch_command):
                trace_mark("onboarding_completion.process_handoff.started")
                self._quit_app()
                return
            trace_mark("onboarding_completion.process_handoff.failed")
        trace_mark("onboarding_completion.ready_shell_fallback.started")
        self._launch_ready_shell(context)

    def show_onboarding_or_repair_route(
        self,
        *,
        readiness_assessment: ReadinessAssessment,
        installation_context: InstallationContext,
        entrypoint_path: object,
        initial_geometry: object | None,
        splash: SplashCloseProtocol | None,
        show_onboarding_window: ShowBootstrapWindow,
        show_repair_window: ShowBootstrapWindow,
    ) -> BootstrapRouteResult:
        """Close splash, show the selected non-ready route, and wire signals."""

        self._close_splash_before_route(splash)
        show_window = (
            show_onboarding_window
            if readiness_assessment.route is BootstrapRoute.ONBOARDING
            else show_repair_window
        )
        onboarding_window = show_window(
            context=installation_context,
            readiness_assessment=readiness_assessment,
            entrypoint_path=entrypoint_path,
            initial_geometry=initial_geometry,
        )
        onboarding_window.launch_requested.connect(
            self.launch_after_onboarding_completion
        )
        onboarding_window.close_requested.connect(self._quit_app)
        return BootstrapRouteResult(onboarding_window=onboarding_window, splash=None)

    def _close_splash_before_route(self, splash: SplashCloseProtocol | None) -> None:
        """Close the launch splash before showing onboarding or repair."""

        if splash is None:
            return
        try:
            splash.close()
        except Exception:
            log_exception(_LOGGER, "Failed to close launch splash before routing")


def create_bootstrap_route_controller(
    *,
    no_comfy: bool,
    start_ready_app_process: Callable[[Sequence[str]], bool],
    launch_ready_shell: Callable[[InstallationContext], None],
    quit_app: Callable[[], None],
) -> BootstrapRouteController:
    """Create the controller for non-ready bootstrap routes."""

    return BootstrapRouteController(
        no_comfy=no_comfy,
        start_ready_app_process=start_ready_app_process,
        launch_ready_shell=launch_ready_shell,
        quit_app=quit_app,
    )


def trace_bootstrap_route(
    route: BootstrapRoute,
    *,
    no_comfy: bool,
    installation_context: InstallationContext,
    workspace_present: bool,
    shell_placement_present: bool,
) -> None:
    """Emit the prompt-safe startup route trace event."""

    event_name = (
        "startup.route.ready"
        if route is BootstrapRoute.READY
        else "startup.route.onboarding"
        if route is BootstrapRoute.ONBOARDING
        else "startup.route.repair"
    )
    target = installation_context.comfy_target
    trace_mark(
        event_name,
        no_comfy=no_comfy,
        target_mode=target.mode,
        target_host=target.endpoint.host,
        target_port=target.endpoint.port,
        workspace_present=workspace_present,
        shell_placement_present=shell_placement_present,
    )


__all__ = [
    "BootstrapRouteController",
    "BootstrapRouteResult",
    "BootstrapRouteWindowProtocol",
    "create_bootstrap_route_controller",
    "trace_bootstrap_route",
]
