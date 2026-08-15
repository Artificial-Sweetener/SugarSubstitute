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

"""Resolve installed, setup, and repair launcher startup routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from launcher.sugarsubstitute_launcher.cli import LauncherArguments
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import (
    InstallLayout,
    default_install_root,
)
from launcher.sugarsubstitute_launcher.platforms import detect_launcher_target
from sugarsubstitute_shared.windows_long_paths import operational_path


@dataclass(frozen=True, slots=True)
class LauncherStartupPlan:
    """Describe how one launcher executable invocation should behave."""

    layout: InstallLayout
    installed_config_found: bool
    installed_config_valid: bool
    config_error: str | None = None


def resolve_install_root(
    *,
    explicit_install_root: Path | None,
    executable_path: Path,
    frozen_support_path: Path | None = None,
    invocation_path: Path | None = None,
) -> Path:
    """Resolve the launcher install root from flags, installed exe, or bundle."""

    return resolve_startup_plan(
        explicit_install_root=explicit_install_root,
        executable_path=executable_path,
        frozen_support_path=frozen_support_path,
        invocation_path=invocation_path,
    ).layout.root


def resolve_startup_plan(
    *,
    explicit_install_root: Path | None,
    executable_path: Path,
    frozen_support_path: Path | None = None,
    invocation_path: Path | None = None,
) -> LauncherStartupPlan:
    """Resolve setup, installed, or repair behavior from package-owned paths."""

    if explicit_install_root is not None:
        return LauncherStartupPlan(
            layout=InstallLayout.from_root(explicit_install_root),
            installed_config_found=False,
            installed_config_valid=True,
        )

    target = detect_launcher_target()
    candidate_roots: list[Path] = []
    if invocation_path is not None:
        candidate_roots.append(target.install_root_for_invocation(invocation_path))
    if frozen_support_path is not None:
        frozen_install_root = target.install_root_for_support_path(frozen_support_path)
        if frozen_install_root is not None:
            candidate_roots.append(frozen_install_root)
    executable_install_root = target.install_root_for_executable(executable_path)
    candidate_roots.append(executable_install_root)

    checked_roots: set[Path] = set()
    for candidate_root in candidate_roots:
        candidate_layout = InstallLayout.from_root(candidate_root, target=target)
        if candidate_layout.root in checked_roots:
            continue
        checked_roots.add(candidate_layout.root)
        if candidate_layout.config_path.is_file():
            return _resolve_installed_config_plan(candidate_layout)

    return LauncherStartupPlan(
        layout=InstallLayout.from_root(default_install_root(executable_path)),
        installed_config_found=False,
        installed_config_valid=True,
    )


def _resolve_installed_config_plan(layout: InstallLayout) -> LauncherStartupPlan:
    """Load and validate the installed launcher config beside its bundle."""

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
    *,
    args: LauncherArguments,
    startup_plan: LauncherStartupPlan,
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


def should_show_repair(
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


__all__ = [
    "LauncherStartupPlan",
    "is_installed_app_launchable",
    "resolve_install_root",
    "resolve_startup_plan",
    "should_launch_installed_app",
    "should_show_repair",
]
