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
from launcher.sugarsubstitute_launcher.platforms import (
    LauncherTarget,
    detect_launcher_target,
)
from sugarsubstitute_shared.windows_long_paths import operational_path


_MAX_PACKAGED_ROOT_ANCESTORS = 6


@dataclass(frozen=True, slots=True)
class LauncherStartupPlan:
    """Describe how one launcher executable invocation should behave."""

    layout: InstallLayout
    installed_config_found: bool
    installed_config_valid: bool
    config_error: str | None = None


@dataclass(frozen=True, slots=True)
class LauncherStartupCandidate:
    """Describe the minimal install candidate needed to start a splash."""

    layout: InstallLayout
    installed_config_found: bool


def resolve_install_root(
    *,
    explicit_install_root: Path | None,
    executable_path: Path,
    frozen_support_path: Path | None = None,
    invocation_path: Path | None = None,
    native_executable_path: Path | None = None,
    working_directory_path: Path | None = None,
) -> Path:
    """Resolve the launcher install root from flags, installed exe, or bundle."""

    return resolve_startup_plan(
        explicit_install_root=explicit_install_root,
        executable_path=executable_path,
        frozen_support_path=frozen_support_path,
        invocation_path=invocation_path,
        native_executable_path=native_executable_path,
        working_directory_path=working_directory_path,
    ).layout.root


def resolve_startup_plan(
    *,
    explicit_install_root: Path | None,
    executable_path: Path,
    frozen_support_path: Path | None = None,
    invocation_path: Path | None = None,
    native_executable_path: Path | None = None,
    working_directory_path: Path | None = None,
) -> LauncherStartupPlan:
    """Resolve and validate setup, installed, or repair startup state."""

    return assess_startup_candidate(
        resolve_startup_candidate(
            explicit_install_root=explicit_install_root,
            executable_path=executable_path,
            frozen_support_path=frozen_support_path,
            invocation_path=invocation_path,
            native_executable_path=native_executable_path,
            working_directory_path=working_directory_path,
        )
    )


def resolve_startup_candidate(
    *,
    explicit_install_root: Path | None,
    executable_path: Path,
    frozen_support_path: Path | None = None,
    invocation_path: Path | None = None,
    native_executable_path: Path | None = None,
    working_directory_path: Path | None = None,
) -> LauncherStartupCandidate:
    """Find a possible installed layout without reading its configuration."""

    if explicit_install_root is not None:
        layout = InstallLayout.from_root(explicit_install_root)
        return LauncherStartupCandidate(
            layout=layout,
            installed_config_found=(
                _matches_installed_executable(executable_path, layout.target)
                and layout.config_path.is_file()
            ),
        )

    target = detect_launcher_target()
    candidate_roots: list[Path] = []
    installed_invocation = _matches_installed_executable(invocation_path, target)
    installed_native_executable = _matches_installed_executable(
        native_executable_path,
        target,
    )
    installed_executable = _matches_installed_executable(executable_path, target)
    if installed_invocation and invocation_path is not None:
        candidate_roots.append(target.install_root_for_invocation(invocation_path))
        candidate_roots.extend(_bounded_ancestor_roots(invocation_path))
    if installed_native_executable and native_executable_path is not None:
        candidate_roots.append(
            target.install_root_for_executable(native_executable_path)
        )
        candidate_roots.extend(_bounded_ancestor_roots(native_executable_path))
    if installed_invocation or installed_native_executable or installed_executable:
        if frozen_support_path is not None:
            frozen_install_root = target.install_root_for_support_path(
                frozen_support_path
            )
            if frozen_install_root is not None:
                candidate_roots.append(frozen_install_root)
            candidate_roots.extend(
                _bounded_ancestor_roots(frozen_support_path, include_path=True)
            )
        executable_install_root = target.install_root_for_executable(executable_path)
        candidate_roots.append(executable_install_root)
        candidate_roots.extend(_bounded_ancestor_roots(executable_path))
        if working_directory_path is not None:
            candidate_roots.extend(
                _bounded_ancestor_roots(
                    working_directory_path,
                    include_path=True,
                )
            )

    checked_roots: set[Path] = set()
    for candidate_root in candidate_roots:
        candidate_layout = InstallLayout.from_root(candidate_root, target=target)
        if candidate_layout.root in checked_roots:
            continue
        checked_roots.add(candidate_layout.root)
        if candidate_layout.config_path.is_file():
            return LauncherStartupCandidate(
                layout=candidate_layout,
                installed_config_found=True,
            )

    return LauncherStartupCandidate(
        layout=InstallLayout.from_root(default_install_root(executable_path)),
        installed_config_found=False,
    )


def assess_startup_candidate(
    candidate: LauncherStartupCandidate,
) -> LauncherStartupPlan:
    """Validate one discovered candidate after its splash is visible."""

    if not candidate.installed_config_found:
        return LauncherStartupPlan(
            layout=candidate.layout,
            installed_config_found=False,
            installed_config_valid=True,
        )
    return _resolve_installed_config_plan(candidate.layout)


def should_attempt_installed_app_launch(
    *,
    args: LauncherArguments,
    candidate: LauncherStartupCandidate,
) -> bool:
    """Return whether one candidate warrants immediate splash presentation."""

    if args.continue_install or args.repair:
        return False
    return candidate.installed_config_found and is_installed_app_launchable(
        candidate.layout
    )


def _matches_installed_executable(
    path: Path | None,
    target: LauncherTarget,
) -> bool:
    """Return whether one runtime path names the installed launcher executable."""

    if path is None:
        return False
    expected_name = target.executable_relative_path.name
    return path.name.casefold() == expected_name.casefold()


def _bounded_ancestor_roots(
    path: Path,
    *,
    include_path: bool = False,
) -> tuple[Path, ...]:
    """Return nearby lexical roots without searching arbitrary parent trees."""

    absolute_path = path.expanduser().absolute()
    roots = list(absolute_path.parents[:_MAX_PACKAGED_ROOT_ANCESTORS])
    if include_path:
        roots.insert(0, absolute_path)
    return tuple(roots)


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
        if operational_path(configured_path) != operational_path(expected_path):
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
    """Return whether validated startup state can launch the installed app."""

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
    "LauncherStartupCandidate",
    "LauncherStartupPlan",
    "assess_startup_candidate",
    "is_installed_app_launchable",
    "resolve_install_root",
    "resolve_startup_candidate",
    "resolve_startup_plan",
    "should_attempt_installed_app_launch",
    "should_launch_installed_app",
    "should_show_repair",
]
