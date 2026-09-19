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

"""Route the standalone launcher while keeping installed startup splash-first."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
    from launcher.sugarsubstitute_launcher.startup_plan import LauncherStartupPlan
    from launcher.sugarsubstitute_launcher.startup_splash_session import (
        StartupSplashSession,
    )
    from sugarsubstitute_shared.application_broker_session import (
        ApplicationBrokerSession,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Route one launcher invocation and reveal installed startup immediately."""

    from launcher.sugarsubstitute_launcher.cli import parse_launcher_args

    process_arguments = tuple(sys.argv if argv is None else [sys.argv[0], *argv])
    args = parse_launcher_args(process_arguments[1:])
    if args.verify_release_connectivity:
        from launcher.sugarsubstitute_launcher.headless_operations import (
            verify_release_connectivity,
        )

        return verify_release_connectivity(args)
    if args.headless_install:
        from launcher.sugarsubstitute_launcher.headless_operations import (
            run_headless_install,
        )

        return run_headless_install(args)
    from launcher.sugarsubstitute_launcher.crash_routing import (
        route_explicit_crash_operation,
    )

    crash_operation_result = route_explicit_crash_operation(args)
    if crash_operation_result is not None:
        return crash_operation_result
    from launcher.sugarsubstitute_launcher.startup_plan import (
        resolve_startup_candidate,
        should_attempt_installed_app_launch,
    )
    from launcher.sugarsubstitute_launcher.runtime_paths import (
        frozen_invocation_path,
        frozen_support_path,
        native_frozen_executable_path,
    )

    startup_candidate = resolve_startup_candidate(
        explicit_install_root=args.install_root,
        executable_path=Path(sys.executable),
        frozen_support_path=frozen_support_path(),
        invocation_path=frozen_invocation_path(),
        native_executable_path=native_frozen_executable_path(),
        working_directory_path=Path.cwd(),
        launcher_ui_child=args.launcher_ui_child,
    )
    layout = startup_candidate.layout
    from launcher.sugarsubstitute_launcher.logging_setup import (
        configure_launcher_logging,
    )

    configure_launcher_logging(layout=layout)
    if args.instance_recovery_request is not None:
        from launcher.sugarsubstitute_launcher.instance_recovery_application import (
            run_instance_recovery_window,
        )

        return run_instance_recovery_window(
            layout=layout,
            request_path=args.instance_recovery_request,
            locale_override=args.locale_override,
        )

    app_launch_error: Exception | None = None
    broker: ApplicationBrokerSession | None = None
    startup_plan: LauncherStartupPlan | None = None
    splash_session: StartupSplashSession | None = None
    startup_resource_registrar: Callable[[Callable[[], None]], str] | None = None
    from sugarsubstitute_shared.supervisor_handoff import supervisor_handoff_present

    if (
        not args.launcher_ui_child
        and supervisor_handoff_present(os.environ)
        and should_attempt_installed_app_launch(
            args=args,
            candidate=startup_candidate,
        )
    ):
        from launcher.sugarsubstitute_launcher.supervisor_handoff_wait import (
            wait_for_outgoing_supervisor,
        )

        splash_session = wait_for_outgoing_supervisor(
            layout=layout,
            locale_override=args.locale_override,
            environment=os.environ,
        )
    from sugarsubstitute_shared.application_broker_session import DELEGATED_LAUNCHER_ENV

    delegated_launcher = os.environ.pop(DELEGATED_LAUNCHER_ENV, None) == "1"
    if not args.launcher_ui_child:
        if delegated_launcher:
            from sugarsubstitute_shared.delegated_application_broker import (
                DelegatedApplicationBroker,
            )

            broker = DelegatedApplicationBroker(os.environ)
            from launcher.sugarsubstitute_launcher.splash_transfer import (
                take_borrowed_splash_session,
            )

            splash_session = take_borrowed_splash_session(
                os.environ, release=broker.release_startup_resource
            )
        else:
            from launcher.sugarsubstitute_launcher.application_launch import (
                elect_application,
            )
            from launcher.sugarsubstitute_launcher.application_election_recovery import (
                ApplicationElectionRecovery,
            )

            election_recovery = ApplicationElectionRecovery(
                layout=layout,
                process_arguments=process_arguments,
                locale_override=args.locale_override,
                elect=elect_application,
            )
            broker = election_recovery.run()
            if broker is None:
                if splash_session is not None:
                    splash_session.close()
                return 0
            startup_resource_registrar = broker.register_startup_resource
    attempt_installed_app = (
        not args.launcher_ui_child
        and should_attempt_installed_app_launch(
            args=args,
            candidate=startup_candidate,
        )
    )
    if not args.launcher_ui_child:
        from launcher.sugarsubstitute_launcher.splash_session import (
            start_launcher_splash_session,
        )

        try:
            if splash_session is None:
                splash_session = start_launcher_splash_session(
                    layout=layout, locale_override=args.locale_override
                )
            from launcher.sugarsubstitute_launcher.startup_recovery import (
                recover_startup_candidate,
            )

            try:
                recovered_candidate = recover_startup_candidate(startup_candidate)
                if recovered_candidate is not startup_candidate:
                    startup_candidate = recovered_candidate
                    attempt_installed_app = should_attempt_installed_app_launch(
                        args=args, candidate=startup_candidate
                    )
            except Exception as error:
                app_launch_error = error
                logging.getLogger(__name__).exception(
                    "Interrupted installation recovery failed; retaining recovery UI."
                )
            if app_launch_error is None and not delegated_launcher:
                assert broker is not None
                from launcher.sugarsubstitute_launcher.generation_dispatch import (
                    dispatch_selected_launcher,
                )

                def resume_baseline_startup() -> None:
                    """Replace the transferred session before continuing baseline startup."""
                    nonlocal splash_session
                    if splash_session is not None:
                        splash_session.close()
                    splash_session = start_launcher_splash_session(
                        layout=layout, locale_override=args.locale_override
                    )

                selected_result = dispatch_selected_launcher(
                    layout=layout,
                    broker=broker,
                    arguments=process_arguments[1:],
                    splash_session=splash_session,
                    register_startup_resource=startup_resource_registrar,
                    on_baseline_fallback=resume_baseline_startup,
                )
                if selected_result is not None:
                    broker.close()
                    if splash_session is not None:
                        splash_session.close()
                    return selected_result
        except BaseException:
            if broker is not None:
                broker.close()
            if splash_session is not None:
                splash_session.close()
            raise
    if attempt_installed_app and app_launch_error is None:
        assert broker is not None
        from launcher.sugarsubstitute_launcher.splash_session import (
            start_launcher_splash_session,
        )
        from launcher.sugarsubstitute_launcher.application_startup_contract import (
            ApplicationStartupCancelled,
        )

        try:
            if splash_session is None:
                logging.getLogger(__name__).warning(
                    "Launcher splash unavailable; continuing supervised application "
                    "launch | install_root=%s",
                    layout.root,
                )
            else:
                broker.bind_startup_presenter(
                    lambda _invocation: splash_session.present()
                )
            from launcher.sugarsubstitute_launcher.localization import (
                resolve_launcher_locale,
            )
            from sugarsubstitute_shared.localization import format_locale_argument

            resolved_locale = resolve_launcher_locale(
                layout,
                locale_override=args.locale_override,
            )
            locale_argument = format_locale_argument(
                resolved_locale.effective_language.identifier
            )
            from launcher.sugarsubstitute_launcher.crash_routing import (
                recover_pending_crash_reports,
            )

            try:
                recover_pending_crash_reports(
                    layout=layout,
                    locale_override=args.locale_override,
                    environment=broker.child_environment(os.environ),
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "Pending crash-report recovery failed; continuing installed "
                    "application launch. | install_root=%s",
                    layout.root,
                )
            from launcher.sugarsubstitute_launcher.startup_plan import (
                assess_startup_candidate,
            )

            startup_plan = assess_startup_candidate(startup_candidate)
            _configure_normal_logging(startup_plan)
            if not startup_plan.installed_config_valid:
                raise ValueError(
                    startup_plan.config_error or "Installed launcher config is invalid."
                )
            from launcher.sugarsubstitute_launcher.installed_app_handoff import (
                complete_installed_app_handoff,
            )

            from launcher.sugarsubstitute_launcher.startup_plan import (
                should_launch_installed_app,
            )

            if should_launch_installed_app(args=args, startup_plan=startup_plan):
                complete_installed_app_handoff(
                    layout=layout,
                    broker=broker,
                    locale_argument=locale_argument,
                    no_update_check=args.no_update_check,
                    splash_session=splash_session,
                    handoff_geometry=args.handoff_geometry,
                )
                broker.close()
                broker = None
                return 0
        except ApplicationStartupCancelled:
            logging.getLogger(__name__).info(
                "Installed application launch cancelled by the user"
            )
            try:
                if splash_session is not None:
                    splash_session.close()
            finally:
                if broker is not None:
                    broker.close()
            return 0
        except Exception as error:
            app_launch_error = error
            _configure_launch_error_logging(
                layout=layout,
                startup_plan=startup_plan,
            )
            logging.getLogger(__name__).exception(
                "Installed app launch failed; showing repair UI."
            )
    else:
        from launcher.sugarsubstitute_launcher.startup_plan import (
            assess_startup_candidate,
        )

        startup_plan = assess_startup_candidate(startup_candidate)
        _configure_normal_logging(startup_plan)

    if startup_plan is None:
        from launcher.sugarsubstitute_launcher.startup_plan import (
            assess_startup_candidate,
        )

        startup_plan = assess_startup_candidate(startup_candidate)

    from launcher.sugarsubstitute_launcher.startup_plan import should_show_repair

    repair = should_show_repair(
        args=args,
        startup_plan=startup_plan,
        app_launch_error=app_launch_error,
    )
    if not args.launcher_ui_child:
        from launcher.sugarsubstitute_launcher.launcher_ui_supervision import (
            supervise_launcher_window,
        )

        try:
            return supervise_launcher_window(
                layout=layout,
                arguments=args,
                repair=repair,
                on_ready=lambda: _complete_launcher_surface_handoff(
                    layout=layout,
                    splash_session=splash_session,
                    broker=broker,
                    launch_error=app_launch_error,
                ),
                environment=(
                    broker.child_environment(os.environ) if broker is not None else None
                ),
            )
        finally:
            if splash_session is not None:
                splash_session.close()
            _release_launch_ownership(broker)
    from launcher.sugarsubstitute_launcher.launcher_window_application import (
        run_launcher_window,
    )

    return run_launcher_window(
        args=args,
        startup_plan=startup_plan,
        broker=broker,
    )


def _configure_normal_logging(startup_plan: LauncherStartupPlan) -> None:
    """Configure durable diagnostics after the installed splash boundary."""

    from launcher.sugarsubstitute_launcher.logging_setup import (
        configure_launcher_logging,
    )

    configure_launcher_logging(layout=startup_plan.layout)
    _record_qualification_startup_route(startup_plan)


def _configure_launch_error_logging(
    *,
    layout: InstallLayout,
    startup_plan: LauncherStartupPlan | None,
) -> None:
    """Configure diagnostics even when startup assessment fails unexpectedly."""

    if startup_plan is not None:
        _configure_normal_logging(startup_plan)
        return
    from launcher.sugarsubstitute_launcher.logging_setup import (
        configure_launcher_logging,
    )

    configure_launcher_logging(layout=layout)


def _complete_launcher_surface_handoff(
    *,
    layout: InstallLayout,
    splash_session: StartupSplashSession | None,
    broker: ApplicationBrokerSession | None,
    launch_error: Exception | None,
) -> None:
    """Retire the splash authority after the launcher window has painted."""

    _acknowledge_startup_incident_handled_by_repair(
        layout=layout,
        launch_error=launch_error,
    )
    if splash_session is not None:
        splash_session.close()
    if broker is not None:
        broker.bind_startup_presenter(None)


def _acknowledge_startup_incident_handled_by_repair(
    *,
    layout: InstallLayout,
    launch_error: Exception | None,
) -> None:
    """Retain but retire an incident only after painted recovery replaces splash."""

    from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
        ApplicationReadinessError,
    )

    if not isinstance(launch_error, ApplicationReadinessError):
        return
    incident_id = launch_error.incident_id
    if incident_id is None:
        return
    from sugarsubstitute_shared.crash_reporting import CrashIncidentStore

    try:
        CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes").acknowledge(
            incident_id
        )
    except OSError:
        logging.getLogger(__name__).exception(
            "Startup incident could not be marked handled after repair painted | "
            "incident_id=%s",
            incident_id,
        )


def _release_launch_ownership(
    broker: ApplicationBrokerSession | None,
) -> None:
    """Release parent launcher ownership after child UI reaches terminal state."""

    if broker is not None:
        broker.close()


def _record_qualification_startup_route(
    startup_plan: LauncherStartupPlan,
) -> None:
    """Record packaged route evidence only for an authenticated CI chain."""

    from launcher.sugarsubstitute_launcher.runtime_paths import (
        frozen_invocation_path,
        frozen_support_path,
        native_frozen_executable_path,
    )
    from sugarsubstitute_shared.installer_qualification import (
        InstallerQualificationPlan,
    )

    logger = logging.getLogger(__name__)
    try:
        plan = InstallerQualificationPlan.from_environment()
    except ValueError as error:
        logger.warning("Ignored invalid installer qualification plan: %s", error)
        return
    if plan is None:
        return
    try:
        plan.record(
            "launcher.startup.resolved",
            config_error=startup_plan.config_error,
            installed_config_found=startup_plan.installed_config_found,
            installed_config_valid=startup_plan.installed_config_valid,
            resolved_root=str(startup_plan.layout.root),
            invocation_path=str(frozen_invocation_path()),
            native_executable_path=str(native_frozen_executable_path()),
            python_executable=sys.executable,
            support_path=str(frozen_support_path()),
            working_directory=str(Path.cwd()),
        )
    except OSError as error:
        logger.warning("Could not record launcher startup route: %s", error)


__all__ = ["main"]
