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

"""Orchestrate application startup flow and branch-specific lifecycle wiring."""

from __future__ import annotations

from typing import Any, Callable, Sequence

from substitute.app.bootstrap.launch_splash import (
    LaunchSplashClient,
    SplashCancelCallback,
)
from substitute.app.bootstrap.startup_timing import StartupTimer, StartupTimingRecord
from substitute.app.bootstrap.startup_cli import (
    parse_startup_cli_arguments,
    prepare_ready_app_launch,
    trace_startup_cli_arguments,
)
from substitute.app.bootstrap.startup_process_launch import start_ready_app_process
from substitute.app.bootstrap.startup_logging import configure_startup_observability
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.app.bootstrap.qt_message_trace import install_qt_message_trace_handler
from substitute.app.bootstrap.startup_environment import prepare_startup_environment
from substitute.app.bootstrap.startup_resources import create_startup_resource_registry
from substitute.app.bootstrap.startup_runtime_bootstrap import (
    build_startup_runtime_bootstrap,
)
from substitute.app.bootstrap.startup_shell_runtime import (
    create_startup_shell_runtime_graph,
)
from substitute.app.bootstrap.startup_shell_flow import run_startup_shell_flow
from substitute.app.bootstrap.startup_support_graph import create_startup_support_graph
from substitute.app.bootstrap.legacy_launcher_update_start import (
    start_legacy_launcher_update_bridge,
)


def prepare_startup_restore_plan(*args: Any, **kwargs: Any) -> Any:
    """Build the startup restore plan after the early startup import boundary."""

    from substitute.app.bootstrap.startup_restore_plan import (
        prepare_startup_restore_plan as build_restore_plan,
    )

    return build_restore_plan(*args, **kwargs)


def run_application(
    argv: Sequence[str] | None = None,
    *,
    initial_splash: LaunchSplashClient | None = None,
    initial_splash_cancel_connector: Callable[[SplashCancelCallback], None]
    | None = None,
    prebootstrap_timing_records: Sequence[StartupTimingRecord] = (),
) -> int:
    """Run startup orchestration and return the Qt event-loop exit code."""

    cli_options = parse_startup_cli_arguments(argv)
    cli_args = list(cli_options.args)
    no_comfy = cli_options.no_comfy
    handoff_geometry = cli_options.handoff_geometry
    trace_startup_cli_arguments(cli_options)
    startup_timer = StartupTimer()
    startup_environment = prepare_startup_environment(
        explicit_install_root=cli_options.install_root,
        startup_timer=startup_timer,
    )
    install_root = startup_environment.install_root
    readiness_assessment = startup_environment.readiness_assessment
    installation_context = startup_environment.installation_context
    with startup_timer.phase("startup.configure_file_logging"):
        configure_startup_observability(installation_context.installation.logs_dir)
    start_legacy_launcher_update_bridge(install_root=install_root)
    _trace_preconfigured_startup_timings(
        prebootstrap_timing_records=prebootstrap_timing_records,
        startup_timer=startup_timer,
    )
    with startup_timer.phase("startup.import_runtime_modules"):
        with trace_span("startup.import_runtime_modules"):
            composition, lifecycle = _load_startup_runtime_modules()

    lifecycle.register_signal_handlers()
    install_qt_message_trace_handler()
    runtime_bootstrap = build_startup_runtime_bootstrap(
        cli_args=cli_args,
        installation_context=installation_context,
        startup_timer=startup_timer,
        create_application=composition.create_application,
        build_appearance_runtime=composition.build_appearance_runtime,
        configure_theme=composition.configure_theme,
        build_application_runtime_services=(
            composition.build_application_runtime_services
        ),
        configure_theme_immediately=not _should_defer_theme_configuration(
            no_comfy=no_comfy,
            readiness_assessment=readiness_assessment,
            installation_context=installation_context,
        ),
    )
    app = runtime_bootstrap.app
    resolved_appearance = runtime_bootstrap.resolved_appearance
    comfy_output_stream = runtime_bootstrap.comfy_output_stream
    runtime_services = runtime_bootstrap.runtime_services
    startup_resources = create_startup_resource_registry()
    restore_plan_preparation = prepare_startup_restore_plan(
        startup_timer=startup_timer,
        installation_context=installation_context,
        runtime_services=runtime_services,
        startup_resources=startup_resources,
        restore_projection_target_key_for_context=composition._cube_cache_target_key,
    )
    initial_restore_plan = restore_plan_preparation.restore_plan
    startup_support_graph = create_startup_support_graph(initial_splash=initial_splash)
    ready_app_launch = prepare_ready_app_launch(install_root=install_root)
    restart_launch_command = ready_app_launch.restart_launch_command
    shell_runtime_graph = create_startup_shell_runtime_graph(
        app=app,
        ready_shell_runtime_state=(
            startup_support_graph.ready_shell_state.runtime_state
        ),
        shell_reload_state=startup_support_graph.shell_reload_state,
        shell_ports=startup_support_graph.shell_ports,
        installation_context=installation_context,
        comfy_output_stream=comfy_output_stream,
        startup_timer=startup_timer,
        runtime_services=runtime_services,
        restart_launch_command=restart_launch_command,
    )
    exit_code: int = run_startup_shell_flow(
        no_comfy=no_comfy,
        handoff_geometry=handoff_geometry,
        readiness_assessment=readiness_assessment,
        installation_context=installation_context,
        app=app,
        resolved_appearance=resolved_appearance,
        configure_theme=runtime_bootstrap.configure_theme,
        comfy_output_stream=comfy_output_stream,
        runtime_services=runtime_services,
        startup_timer=startup_timer,
        startup_resources=startup_resources,
        initial_restore_plan=initial_restore_plan,
        startup_support_graph=startup_support_graph,
        shell_runtime_graph=shell_runtime_graph,
        ready_app_launch=ready_app_launch,
        initial_splash_cancel_connector=initial_splash_cancel_connector,
        show_onboarding_window=composition.show_onboarding_window,
        show_repair_window=composition.show_repair_window,
        start_ready_app_process=start_ready_app_process,
    )
    return exit_code


def _load_startup_runtime_modules() -> tuple[Any, Any]:
    """Import heavy runtime modules after startup tracing is configured."""

    from substitute.app.bootstrap import composition, lifecycle

    return composition, lifecycle


def _should_defer_theme_configuration(
    *,
    no_comfy: bool,
    readiness_assessment: Any,
    installation_context: Any,
) -> bool:
    """Return whether managed Comfy launch can overlap theme configuration."""

    target = installation_context.comfy_target
    return (
        not no_comfy
        and getattr(readiness_assessment.route, "value", None) == "ready"
        and bool(getattr(target, "launch_owned", False))
        and getattr(target, "workspace_path", None) is not None
    )


def _trace_preconfigured_startup_timings(
    *,
    prebootstrap_timing_records: Sequence[StartupTimingRecord],
    startup_timer: StartupTimer,
) -> None:
    """Flush startup phase timings captured before startup trace configuration."""

    for order_index, record in enumerate(prebootstrap_timing_records):
        trace_mark(
            "startup.pretrace.phase",
            source="entrypoint",
            phase=record.phase,
            elapsed_ms=round(record.elapsed_ms, 3),
            order_index=order_index,
        )
    for order_index, record in enumerate(startup_timer.records()):
        trace_mark(
            "startup.pretrace.phase",
            source="startup_timer",
            phase=record.phase,
            elapsed_ms=round(record.elapsed_ms, 3),
            order_index=order_index,
        )


def __getattr__(name: str) -> object:
    """Expose historically patched startup modules without eager imports."""

    if name == "composition":
        from substitute.app.bootstrap import composition

        return composition
    if name == "lifecycle":
        from substitute.app.bootstrap import lifecycle

        return lifecycle
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["run_application"]
