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

"""Run startup route dispatch through ready and non-ready route adapters."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from substitute.app.bootstrap.bootstrap_route_controller import (
    ShowBootstrapWindow,
    SplashCloseProtocol,
    create_bootstrap_route_controller,
    trace_bootstrap_route,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    InstallationContext,
    ReadinessAssessment,
)


@dataclass(frozen=True, slots=True)
class StartupRouteFlowResult:
    """Return startup-owned references after route dispatch."""

    onboarding_window: object | None
    route_controller: object | None
    splash: object | None
    update_splash_reference: bool


def run_startup_route_flow(
    *,
    readiness_assessment: ReadinessAssessment,
    no_comfy: bool,
    installation_context: InstallationContext,
    initial_workspace: object | None,
    initial_shell_placement: object | None,
    entrypoint_path: object,
    initial_geometry: object | None,
    splash: SplashCloseProtocol | None,
    show_onboarding_window: ShowBootstrapWindow,
    show_repair_window: ShowBootstrapWindow,
    start_ready_app_process: Callable[[Sequence[str]], bool],
    launch_ready_shell: Callable[[InstallationContext], None],
    quit_app: Callable[[], None],
) -> StartupRouteFlowResult:
    """Trace and execute the selected startup route."""

    trace_bootstrap_route(
        readiness_assessment.route,
        no_comfy=no_comfy,
        installation_context=installation_context,
        workspace_present=initial_workspace is not None,
        shell_placement_present=initial_shell_placement is not None,
    )
    if readiness_assessment.route is BootstrapRoute.READY:
        launch_ready_shell(installation_context)
        return StartupRouteFlowResult(
            onboarding_window=None,
            route_controller=None,
            splash=splash,
            update_splash_reference=False,
        )

    bootstrap_route_controller = create_bootstrap_route_controller(
        no_comfy=no_comfy,
        start_ready_app_process=start_ready_app_process,
        launch_ready_shell=launch_ready_shell,
        quit_app=quit_app,
    )
    bootstrap_route_result = bootstrap_route_controller.show_onboarding_or_repair_route(
        readiness_assessment=readiness_assessment,
        installation_context=installation_context,
        entrypoint_path=entrypoint_path,
        initial_geometry=initial_geometry,
        splash=splash,
        show_onboarding_window=show_onboarding_window,
        show_repair_window=show_repair_window,
    )
    return StartupRouteFlowResult(
        onboarding_window=bootstrap_route_result.onboarding_window,
        route_controller=bootstrap_route_controller,
        splash=bootstrap_route_result.splash,
        update_splash_reference=True,
    )


__all__ = [
    "StartupRouteFlowResult",
    "run_startup_route_flow",
]
