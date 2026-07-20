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

"""Parse startup CLI arguments and build ready-app launch commands."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import sys

from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.startup_trace import trace_mark
from sugarsubstitute_shared.localization import parse_locale_override


@dataclass(frozen=True, slots=True)
class StartupCliArguments:
    """Describe parsed startup arguments used by bootstrap orchestration."""

    args: tuple[str, ...]
    argv_provided: bool
    no_comfy: bool
    handoff_geometry: tuple[int, int, int, int] | None
    install_root: Path | None
    locale_override: str | None


@dataclass(frozen=True, slots=True)
class StartupReadyAppLaunch:
    """Describe the ready-app entrypoint and restart command."""

    entrypoint_path: Path
    restart_launch_command: list[str]


def extract_install_root(cli_args: Sequence[str]) -> Path | None:
    """Return an optional install-root override from startup CLI arguments."""

    prefix = "--install-root="
    for raw_arg in cli_args:
        if raw_arg.startswith(prefix):
            raw_path = raw_arg[len(prefix) :].strip()
            if raw_path:
                return Path(raw_path)
    return None


def extract_handoff_geometry(
    cli_args: Sequence[str],
) -> tuple[int, int, int, int] | None:
    """Return optional installer handoff geometry from startup CLI arguments."""

    prefix = "--handoff-geometry="
    for raw_arg in cli_args:
        if not raw_arg.startswith(prefix):
            continue
        raw_value = raw_arg[len(prefix) :].strip()
        parts = raw_value.split(",")
        if len(parts) != 4:
            return None
        try:
            x, y, width, height = (int(part) for part in parts)
        except ValueError:
            return None
        if width <= 0 or height <= 0:
            return None
        return (x, y, width, height)
    return None


def extract_locale_override(cli_args: Sequence[str]) -> str | None:
    """Return a validated effective locale passed between executable processes."""

    prefix = "--locale="
    for raw_arg in cli_args:
        if raw_arg.startswith(prefix):
            return parse_locale_override(raw_arg[len(prefix) :].strip())
    return None


def parse_startup_cli_arguments(argv: Sequence[str] | None) -> StartupCliArguments:
    """Parse startup CLI arguments into one immutable bootstrap input object."""

    args = tuple(str(arg) for arg in (argv if argv is not None else sys.argv))
    return StartupCliArguments(
        args=args,
        argv_provided=argv is not None,
        no_comfy="--no-comfy" in args,
        handoff_geometry=extract_handoff_geometry(args),
        install_root=extract_install_root(args),
        locale_override=extract_locale_override(args),
    )


def trace_startup_cli_arguments(arguments: StartupCliArguments) -> None:
    """Emit prompt-safe startup trace fields for parsed CLI arguments."""

    trace_mark("run_application.enter", argv_provided=arguments.argv_provided)
    trace_mark(
        "startup.args_parsed",
        no_comfy=arguments.no_comfy,
        arg_count=len(arguments.args),
        handoff_geometry_present=arguments.handoff_geometry is not None,
        locale_override_present=arguments.locale_override is not None,
    )


def build_ready_app_launch_command(
    *,
    entrypoint_path: Path,
    install_root: Path,
) -> list[str]:
    """Build the normal ready-app command used for in-app restarts."""

    return [
        sys.executable,
        str(entrypoint_path),
        f"--install-root={install_root}",
    ]


def prepare_ready_app_launch(*, install_root: Path) -> StartupReadyAppLaunch:
    """Resolve the ready-app entrypoint and restart command for startup."""

    entrypoint_path = resolve_app_layout(install_root).entrypoint_path
    return StartupReadyAppLaunch(
        entrypoint_path=entrypoint_path,
        restart_launch_command=build_ready_app_launch_command(
            entrypoint_path=entrypoint_path,
            install_root=install_root,
        ),
    )


__all__ = [
    "StartupCliArguments",
    "StartupReadyAppLaunch",
    "build_ready_app_launch_command",
    "extract_handoff_geometry",
    "extract_install_root",
    "extract_locale_override",
    "parse_startup_cli_arguments",
    "prepare_ready_app_launch",
    "trace_startup_cli_arguments",
]
