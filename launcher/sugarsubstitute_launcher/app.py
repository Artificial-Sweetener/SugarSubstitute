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
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from launcher.sugarsubstitute_launcher.cli import LauncherArguments
    from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
    from launcher.sugarsubstitute_launcher.startup_plan import LauncherStartupPlan
    from sugarsubstitute_shared.application_instance_broker import (
        ApplicationInstanceBroker,
    )


LauncherMainWindow: Callable[..., Any] | None = None


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
    )
    layout = startup_candidate.layout
    from launcher.sugarsubstitute_launcher.localization import resolve_launcher_locale
    from sugarsubstitute_shared.localization import format_locale_argument

    resolved_locale = resolve_launcher_locale(
        layout,
        locale_override=args.locale_override,
    )
    locale_argument = format_locale_argument(
        resolved_locale.effective_language.identifier
    )

    app_launch_error: Exception | None = None
    broker: ApplicationInstanceBroker | None = None
    startup_plan: LauncherStartupPlan | None = None
    if not args.launcher_ui_child and should_attempt_installed_app_launch(
        args=args,
        candidate=startup_candidate,
    ):
        from launcher.sugarsubstitute_launcher.application_launch import (
            elect_installed_application,
        )

        broker = elect_installed_application(layout, process_arguments)
        if broker is None:
            return 0
        from launcher.sugarsubstitute_launcher.splash_session import (
            start_launcher_splash_session,
        )

        splash_session = None
        try:
            splash_session = start_launcher_splash_session(
                layout=layout,
                locale_identifier=resolved_locale.effective_language.identifier,
            )
            from launcher.sugarsubstitute_launcher.crash_routing import (
                recover_pending_crash_reports,
            )

            try:
                recover_pending_crash_reports(
                    layout=layout,
                    locale_override=args.locale_override,
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
        except Exception as error:
            app_launch_error = error
            _configure_launch_error_logging(
                layout=layout,
                startup_plan=startup_plan,
            )
            logging.getLogger(__name__).exception(
                "Installed app launch failed; showing repair UI."
            )
            if splash_session is not None:
                try:
                    splash_session.client.close()
                except OSError:
                    logging.getLogger(__name__).debug(
                        "Failed to close launcher splash after error."
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
            )
        finally:
            _release_launch_ownership(broker)
    return _run_launcher_window(
        args=args,
        startup_plan=startup_plan,
        app_launch_error=app_launch_error,
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


def _run_launcher_window(
    *,
    args: LauncherArguments,
    startup_plan: LauncherStartupPlan,
    app_launch_error: Exception | None,
    broker: ApplicationInstanceBroker | None,
) -> int:
    """Show setup or repair UI after installed launch routing is complete."""

    from PySide6.QtWidgets import QApplication

    from launcher.sugarsubstitute_launcher.application.installation.composition import (
        build_installation_workflow,
    )
    from launcher.sugarsubstitute_launcher.application.model_onboarding import (
        build_installer_model_onboarding,
    )
    from launcher.sugarsubstitute_launcher.localization import (
        build_launcher_localization_runtime,
    )
    from launcher.sugarsubstitute_launcher.process import (
        start_installed_launcher_handoff,
    )
    from launcher.sugarsubstitute_launcher.release_source_routing import (
        initial_install_release_source,
    )

    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        application = QApplication(sys.argv[:1])
    application = cast(QApplication, application)
    build_launcher_localization_runtime(
        application,
        layout=startup_plan.layout,
        locale_override=args.locale_override,
    )

    try:
        window = _launcher_main_window_class()(
            initial_layout=startup_plan.layout,
            continue_install=args.continue_install,
            repair=args.repair,
            update_check_enabled=not args.no_update_check,
            initial_release_source=initial_install_release_source(args.manifest_url),
            workflow_factory=lambda output_callback: build_installation_workflow(
                output_callback=output_callback,
                process_starter=start_installed_launcher_handoff,
            ),
            model_onboarding_service_factory=lambda model_root: (
                build_installer_model_onboarding(model_root=model_root)
            ),
            handoff_geometry=args.handoff_geometry,
        )
        if owns_application:
            window.handoff_completed.connect(application.quit)
        window.show()
        from launcher.sugarsubstitute_launcher.ui.installer_qualification import (
            schedule_installer_qualification,
        )

        schedule_installer_qualification(window)
        if owns_application:
            return int(application.exec())
        return 0
    finally:
        _release_launch_ownership(broker)


def _launcher_main_window_class() -> Callable[..., Any]:
    """Return the launcher window class without importing GUI code on handoff."""

    global LauncherMainWindow
    if LauncherMainWindow is None:
        from launcher.sugarsubstitute_launcher.ui.main_window import (
            LauncherMainWindow as ImportedLauncherMainWindow,
        )

        LauncherMainWindow = ImportedLauncherMainWindow
    return LauncherMainWindow


def _release_launch_ownership(
    broker: ApplicationInstanceBroker | None,
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
