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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from launcher.sugarsubstitute_launcher.cli import LauncherArguments, parse_launcher_args
from launcher.sugarsubstitute_launcher.connectivity import ReleaseConnectivityVerifier
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
    default_install_root,
)
from launcher.sugarsubstitute_launcher.headless_install import HeadlessInstallService
from launcher.sugarsubstitute_launcher.logging_setup import configure_launcher_logging
from launcher.sugarsubstitute_launcher.localization import (
    build_launcher_localization_runtime,
    resolve_launcher_locale,
    seed_headless_locale_preference,
)
from launcher.sugarsubstitute_launcher.platforms import detect_launcher_target
from launcher.sugarsubstitute_launcher.process import (
    build_app_launch_command,
    start_detached,
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
from launcher.sugarsubstitute_launcher.update_orchestrator import (
    LauncherUpdateOrchestrator,
)
from sugarsubstitute_shared.launcher_update.process import schedule_launcher_update
from sugarsubstitute_shared.localization import format_locale_argument
from sugarsubstitute_shared.windows_long_paths import operational_path


_LOGGER = logging.getLogger(__name__)
LauncherMainWindow: Callable[..., Any] | None = None


@dataclass(frozen=True, slots=True)
class LauncherStartupPlan:
    """Describe how this executable invocation should behave."""

    layout: InstallLayout
    installed_config_found: bool
    installed_config_valid: bool
    config_error: str | None = None


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
        HeadlessInstallService().install(
            install_root=layout.root,
            release_source=_explicit_release_source(args.manifest_url),
        )
        seed_headless_locale_preference(
            layout,
            locale_override=args.locale_override,
        )
        return 0
    startup_plan = resolve_startup_plan(
        explicit_install_root=args.install_root,
        executable_path=Path(sys.executable),
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
    if should_launch_installed_app(args=args, startup_plan=startup_plan):
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
            start_detached(
                append_splash_session_args(
                    build_app_launch_command(
                        layout=layout,
                        extra_args=(locale_argument,),
                    ),
                    splash_session,
                )
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

    window = _launcher_main_window_class()(
        initial_layout=layout,
        continue_install=args.continue_install,
        repair=_should_show_repair(
            args=args,
            startup_plan=startup_plan,
            app_launch_error=app_launch_error,
        ),
        update_check_enabled=not args.no_update_check,
        handoff_geometry=args.handoff_geometry,
    )
    window.show()
    if owns_application:
        return int(application.exec())
    return 0


def _explicit_release_source(manifest_url: str | None) -> ReleaseSource:
    """Return the requested HTTPS source or the production release channel."""

    if manifest_url is None:
        return default_production_release_source()
    return GitHubReleaseSource(manifest_url)


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

    return release_source_from_config(config.release_source)


def resolve_install_root(
    *,
    explicit_install_root: Path | None,
    executable_path: Path,
) -> Path:
    """Resolve the launcher install root from flags, installed exe, or default."""

    return resolve_startup_plan(
        explicit_install_root=explicit_install_root,
        executable_path=executable_path,
    ).layout.root


def resolve_startup_plan(
    *,
    explicit_install_root: Path | None,
    executable_path: Path,
) -> LauncherStartupPlan:
    """Resolve setup, installed, or repair behavior from executable-local state."""

    if explicit_install_root is not None:
        return LauncherStartupPlan(
            layout=InstallLayout.from_root(explicit_install_root),
            installed_config_found=False,
            installed_config_valid=True,
        )

    target = detect_launcher_target()
    executable_install_root = target.install_root_for_executable(executable_path)
    executable_layout = InstallLayout.from_root(
        executable_install_root,
        target=target,
    )
    if not executable_layout.config_path.is_file():
        return LauncherStartupPlan(
            layout=InstallLayout.from_root(default_install_root(executable_path)),
            installed_config_found=False,
            installed_config_valid=True,
        )

    return _resolve_installed_config_plan(executable_layout)


def _resolve_installed_config_plan(layout: InstallLayout) -> LauncherStartupPlan:
    """Load and validate the installed launcher config beside the executable."""

    try:
        config = LauncherConfig.load(layout.config_path)
    except (OSError, ValueError) as error:
        return LauncherStartupPlan(
            layout=layout,
            installed_config_found=True,
            installed_config_valid=False,
            config_error=str(error),
        )

    expected_values = {
        "install_root": (config.install_root, layout.root),
        "app_dir": (config.app_dir, layout.app_dir),
        "runtime_python": (config.runtime_python, layout.runtime_python),
    }
    for name, (configured_path, expected_path) in expected_values.items():
        if operational_path(configured_path).resolve() != expected_path:
            return LauncherStartupPlan(
                layout=layout,
                installed_config_found=True,
                installed_config_valid=False,
                config_error=(
                    f"Launcher config {name} points to {configured_path}, "
                    f"but this executable is installed at {layout.root}."
                ),
            )

    return LauncherStartupPlan(
        layout=layout,
        installed_config_found=True,
        installed_config_valid=True,
    )


def should_launch_installed_app(
    *, args: LauncherArguments, startup_plan: LauncherStartupPlan
) -> bool:
    """Return whether this launcher invocation should start the installed app."""

    if args.continue_install or args.repair:
        return False
    return (
        startup_plan.installed_config_found
        and startup_plan.installed_config_valid
        and is_installed_app_launchable(startup_plan.layout)
    )


def is_installed_app_launchable(layout: InstallLayout) -> bool:
    """Return whether a layout has enough installed state to start the app."""

    return (
        layout.config_path.is_file()
        and layout.app_entrypoint.is_file()
        and layout.runtime_python.is_file()
    )


def _should_show_repair(
    *,
    args: LauncherArguments,
    startup_plan: LauncherStartupPlan,
    app_launch_error: Exception | None,
) -> bool:
    """Return whether installed-state failures should open repair mode."""

    if args.repair or app_launch_error is not None:
        return True
    if args.continue_install:
        return False
    return startup_plan.installed_config_found
