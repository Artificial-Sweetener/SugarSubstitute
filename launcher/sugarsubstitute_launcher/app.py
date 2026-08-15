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

"""Start the standalone launcher GUI."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from launcher.sugarsubstitute_launcher.cli import parse_launcher_args
from launcher.sugarsubstitute_launcher.candidate_update_launch import (
    launch_prepared_update,
)
from launcher.sugarsubstitute_launcher.application.installation.composition import (
    build_installation_workflow,
)
from launcher.sugarsubstitute_launcher.application.installation.release_source_policy import (
    resolve_initial_install_release_source,
)
from launcher.sugarsubstitute_launcher.application_launch import (
    enter_installed_application_launch,
    installed_application_environment,
)
from launcher.sugarsubstitute_launcher.connectivity import ReleaseConnectivityVerifier
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
)
from launcher.sugarsubstitute_launcher.headless_install import HeadlessInstallService
from launcher.sugarsubstitute_launcher.logging_setup import configure_launcher_logging
from launcher.sugarsubstitute_launcher.localization import (
    build_launcher_localization_runtime,
    resolve_launcher_locale,
    seed_headless_locale_preference,
)
from launcher.sugarsubstitute_launcher.process import (
    build_app_launch_command,
    start_detached,
    start_detached_handoff,
)
from launcher.sugarsubstitute_launcher.release_sources import (
    GitHubReleaseSource,
    ReleaseSource,
    default_production_release_source,
    release_source_from_config,
)
from launcher.sugarsubstitute_launcher.splash_session import (
    append_splash_session_args,
    start_launcher_splash_session,
)
from launcher.sugarsubstitute_launcher.startup_plan import (
    resolve_startup_plan,
    should_launch_installed_app,
    should_show_repair,
)
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    LauncherUpdateOrchestrator,
)
from sugarsubstitute_shared.application_launch_guard import ApplicationLaunchGuard
from sugarsubstitute_shared.launcher_update.process import schedule_launcher_update
from sugarsubstitute_shared.localization import format_locale_argument


_LOGGER = logging.getLogger(__name__)
_PRE_LAUNCH_MANIFEST_TIMEOUT_SECONDS = 3.0
LauncherMainWindow: Callable[..., Any] | None = None


def main(argv: Sequence[str] | None = None) -> int:
    """Create the Qt application and run the launcher window."""

    args = parse_launcher_args(sys.argv[1:] if argv is None else argv)
    if args.verify_release_connectivity:
        ReleaseConnectivityVerifier().verify(
            release_source=_explicit_release_source(args.manifest_url)
        )
        return 0
    if args.headless_install:
        if args.install_root is None:
            raise ValueError("Headless installation requires an explicit install root.")
        layout = InstallLayout.from_root(args.install_root)
        configure_launcher_logging(layout=layout)
        HeadlessInstallService(
            workflow=build_installation_workflow(output_callback=_LOGGER.info)
        ).install(
            install_root=layout.root,
            release_source=_initial_install_release_source(args.manifest_url),
        )
        seed_headless_locale_preference(
            layout,
            locale_override=args.locale_override,
        )
        return 0
    startup_plan = resolve_startup_plan(
        explicit_install_root=args.install_root,
        executable_path=Path(sys.executable),
        frozen_support_path=_frozen_support_path(),
        invocation_path=_frozen_invocation_path(),
        working_directory_path=Path.cwd(),
    )
    layout = startup_plan.layout
    configure_launcher_logging(layout=layout)
    resolved_locale = resolve_launcher_locale(
        layout,
        locale_override=args.locale_override,
    )
    locale_argument = format_locale_argument(
        resolved_locale.effective_language.identifier
    )

    app_launch_error: Exception | None = None
    launch_guard: ApplicationLaunchGuard | None = None
    if should_launch_installed_app(args=args, startup_plan=startup_plan):
        launch_guard = enter_installed_application_launch(layout)
        if launch_guard is None:
            _LOGGER.info(
                "Ignored launch request because SugarSubstitute is already running."
            )
            return 0
        splash_session = None
        try:
            config = LauncherConfig.load(layout.config_path)
            splash_session = start_launcher_splash_session(
                layout=layout,
                locale_identifier=resolved_locale.effective_language.identifier,
            )
            update_result = LauncherUpdateOrchestrator().run(
                layout=layout,
                config=config,
                release_source=create_normal_launch_release_source(config),
                no_update_check=args.no_update_check,
                progress=splash_session.client if splash_session is not None else None,
            )
            if update_result.launcher_update_request_path is not None:
                if splash_session is not None:
                    splash_session.client.close()
                schedule_launcher_update(
                    request_path=Path(update_result.launcher_update_request_path),
                    runtime_python=layout.runtime_python,
                    app_dir=layout.app_dir,
                    relaunch=True,
                    wait_pid=os.getpid(),
                )
                return 0
            app_command = append_splash_session_args(
                build_app_launch_command(
                    layout=layout,
                    extra_args=(locale_argument,),
                ),
                splash_session,
            )
            if update_result.pending_activation is not None:
                launch_prepared_update(
                    layout=layout,
                    command=app_command,
                    initial_guard=launch_guard,
                    activation=update_result.pending_activation,
                )
            else:
                start_detached(
                    app_command,
                    environment=installed_application_environment(
                        launch_guard,
                        remote_failure_reason=update_result.failure_reason,
                    ),
                )
            return 0
        except Exception as error:
            app_launch_error = error
            _LOGGER.exception("Installed app launch failed; showing repair UI.")
            if splash_session is not None:
                try:
                    splash_session.client.close()
                except OSError:
                    _LOGGER.debug("Failed to close launcher splash after error.")

    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        application = QApplication(sys.argv[:1])
    application = cast(QApplication, application)

    build_launcher_localization_runtime(
        application,
        layout=layout,
        locale_override=args.locale_override,
    )

    try:
        window = _launcher_main_window_class()(
            initial_layout=layout,
            continue_install=args.continue_install,
            repair=should_show_repair(
                args=args,
                startup_plan=startup_plan,
                app_launch_error=app_launch_error,
            ),
            update_check_enabled=not args.no_update_check,
            initial_release_source=_initial_install_release_source(args.manifest_url),
            workflow_factory=lambda output_callback: build_installation_workflow(
                output_callback=output_callback,
                process_starter=start_detached_handoff,
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
        if launch_guard is not None:
            launch_guard.release()


def _explicit_release_source(manifest_url: str | None) -> ReleaseSource:
    """Return the requested HTTPS source or the production release channel."""

    if manifest_url is None:
        return default_production_release_source()
    return GitHubReleaseSource(manifest_url)


def _initial_install_release_source(manifest_url: str | None) -> ReleaseSource:
    """Return an explicit test source or the installer-bound release source."""

    if manifest_url is not None:
        return GitHubReleaseSource(manifest_url)
    return resolve_initial_install_release_source(
        frozen_setup=bool(getattr(sys, "frozen", False))
    )


def _launcher_main_window_class() -> Callable[..., Any]:
    """Return the launcher window class without importing GUI code on handoff."""

    global LauncherMainWindow
    if LauncherMainWindow is None:
        from launcher.sugarsubstitute_launcher.ui.main_window import (
            LauncherMainWindow as ImportedLauncherMainWindow,
        )

        LauncherMainWindow = ImportedLauncherMainWindow
    return LauncherMainWindow


def create_normal_launch_release_source(config: LauncherConfig) -> ReleaseSource | None:
    """Return the configured release source for normal launcher startup."""

    return release_source_from_config(
        config.release_source,
        timeout_seconds=_PRE_LAUNCH_MANIFEST_TIMEOUT_SECONDS,
    )


def _frozen_support_path() -> Path | None:
    """Return PyInstaller's authoritative bundle support directory when frozen."""

    raw_path = getattr(sys, "_MEIPASS", None)
    if not bool(getattr(sys, "frozen", False)) or not isinstance(raw_path, str):
        return None
    return Path(raw_path)


def _frozen_invocation_path() -> Path | None:
    """Return the packaged launcher path exactly as the operating system invoked it."""

    if not bool(getattr(sys, "frozen", False)) or not sys.argv or not sys.argv[0]:
        return None
    return Path(sys.argv[0])
