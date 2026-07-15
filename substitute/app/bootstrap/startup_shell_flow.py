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

"""Run ready-shell startup routing and event-loop handoff."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from substitute.app.bootstrap.bootstrap_route_controller import ShowBootstrapWindow
from substitute.app.bootstrap.launch_splash import SplashCancelCallback
from substitute.app.bootstrap.managed_recovery_adapters import (
    ManagedRecoveryOutputStreamProtocol,
)
from substitute.app.bootstrap.startup_cli import StartupReadyAppLaunch
from substitute.app.bootstrap.startup_event_loop import (
    StartupRuntimeServicesProtocol,
    run_startup_event_loop_and_shutdown,
)
from substitute.app.bootstrap.startup_ready_shell_launch import (
    create_startup_ready_shell_launch_graph,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_route_flow import run_startup_route_flow
from substitute.app.bootstrap.startup_shell_runtime import StartupShellRuntimeGraph
from substitute.app.bootstrap.startup_support_graph import StartupSupportGraph
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.application.workspace_state import InitialWorkspaceRestorePlan
from substitute.domain.onboarding import InstallationContext, ReadinessAssessment


class StartupShellFlowAppProtocol(Protocol):
    """Expose application ports needed by shell startup flow."""

    def exec(self) -> int:
        """Run the application event loop."""

    def quit(self) -> None:
        """Request application shutdown."""


def run_startup_shell_flow(
    *,
    no_comfy: bool,
    handoff_geometry: tuple[int, int, int, int] | None,
    readiness_assessment: ReadinessAssessment,
    installation_context: InstallationContext,
    app: StartupShellFlowAppProtocol,
    resolved_appearance: object | None,
    configure_theme: Callable[[], object],
    comfy_output_stream: ManagedRecoveryOutputStreamProtocol,
    runtime_services: StartupRuntimeServicesProtocol,
    startup_timer: StartupTimer,
    startup_resources: StartupResourceRegistry,
    initial_restore_plan: InitialWorkspaceRestorePlan,
    startup_support_graph: StartupSupportGraph,
    shell_runtime_graph: StartupShellRuntimeGraph,
    ready_app_launch: StartupReadyAppLaunch,
    initial_splash_cancel_connector: Callable[[SplashCancelCallback], None] | None,
    show_onboarding_window: ShowBootstrapWindow,
    show_repair_window: ShowBootstrapWindow,
    start_ready_app_process: Callable[[Sequence[str]], bool],
) -> int:
    """Create the ready-shell route graph, dispatch startup, and run shutdown."""

    def resolve_appearance() -> object:
        """Return the configured appearance for UI surfaces that need it."""

        nonlocal resolved_appearance
        if resolved_appearance is None:
            resolved_appearance = configure_theme()
        return resolved_appearance

    ready_shell_state = startup_support_graph.ready_shell_state
    ready_shell_reference_state = ready_shell_state.reference_state
    ready_shell_launch_controller = create_startup_ready_shell_launch_graph(
        no_comfy=no_comfy,
        ready_shell_reference_state=ready_shell_reference_state,
        ready_shell_runtime_state=ready_shell_state.runtime_state,
        shell_reload_state=startup_support_graph.shell_reload_state,
        startup_cancellation_state=startup_support_graph.startup_cancellation_state,
        shutdown_runtime=shell_runtime_graph.shutdown_runtime,
        shell_reload_adapter=shell_runtime_graph.shell_reload_adapter,
        shell_ports=startup_support_graph.shell_ports,
        managed_ready_ports=startup_support_graph.managed_ready_ports,
        startup_resources=startup_resources,
        startup_timer=startup_timer,
        startup_qt_schedulers=startup_support_graph.startup_qt_schedulers,
        connect_cancel_request=(
            startup_support_graph.startup_cancel_bridge.cancel_requested.connect
        ),
        emit_splash_cancel=(
            startup_support_graph.startup_cancel_bridge.cancel_requested.emit
        ),
        initial_splash_cancel_connector=initial_splash_cancel_connector,
        startup_splash_start_or_adopt=(
            startup_support_graph.startup_splash_ports.start_or_adopt_launch_splash
        ),
        resolve_appearance=resolve_appearance,
        comfy_output_stream=comfy_output_stream,
        request_shell_shutdown=shell_runtime_graph.request_shell_shutdown,
        quit_app=app.quit,
        runtime_services=runtime_services,
        initial_workspace=initial_restore_plan.workspace,
        initial_shell_placement=initial_restore_plan.shell_placement,
        provisional_restore_projection=(
            initial_restore_plan.provisional_restore_projection
        ),
    )

    route_flow_result = run_startup_route_flow(
        readiness_assessment=readiness_assessment,
        no_comfy=no_comfy,
        installation_context=installation_context,
        initial_workspace=initial_restore_plan.workspace,
        initial_shell_placement=initial_restore_plan.shell_placement,
        entrypoint_path=ready_app_launch.entrypoint_path,
        initial_geometry=handoff_geometry,
        splash=ready_shell_reference_state.splash,
        show_onboarding_window=show_onboarding_window,
        show_repair_window=show_repair_window,
        start_ready_app_process=start_ready_app_process,
        launch_ready_shell=ready_shell_launch_controller.launch,
        quit_app=app.quit,
    )
    if route_flow_result.update_splash_reference:
        ready_shell_reference_state.set_splash(route_flow_result.splash)

    exit_code: int = run_startup_event_loop_and_shutdown(
        app=app,
        splash=ready_shell_reference_state.splash,
        startup_resources=startup_resources,
        shutdown_runtime=shell_runtime_graph.shutdown_runtime,
        shell_reload=shell_runtime_graph.shell_reload_adapter,
        runtime_services=runtime_services,
        start_ready_app_process=start_ready_app_process,
        keep_alive_references=(
            route_flow_result.onboarding_window,
            route_flow_result.route_controller,
            startup_support_graph.shell_reload_state.shell_frame,
            ready_shell_reference_state.splash,
        ),
    )
    return exit_code


__all__ = [
    "StartupShellFlowAppProtocol",
    "run_startup_shell_flow",
]
