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

"""Parse internal launcher command-line flags."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LauncherArguments:
    """Capture parsed launcher command-line behavior switches."""

    continue_install: bool
    headless_install: bool
    verify_release_connectivity: bool
    repair: bool
    no_update_check: bool
    install_root: Path | None
    handoff_geometry: str | None
    manifest_url: str | None


def parse_launcher_args(argv: Sequence[str]) -> LauncherArguments:
    """Parse launcher flags used by setup, repair, and normal launch modes."""

    parser = argparse.ArgumentParser(add_help=True)
    execution_mode = parser.add_mutually_exclusive_group()
    execution_mode.add_argument("--continue-install", action="store_true")
    execution_mode.add_argument("--headless-install", action="store_true")
    execution_mode.add_argument("--verify-release-connectivity", action="store_true")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--no-update-check", action="store_true")
    parser.add_argument("--install-root", type=Path, default=None)
    parser.add_argument("--handoff-geometry", type=str, default=None)
    parser.add_argument("--manifest-url", type=str, default=None)
    namespace = parser.parse_args(argv)
    if namespace.headless_install and namespace.install_root is None:
        parser.error("--headless-install requires --install-root")
    return LauncherArguments(
        continue_install=namespace.continue_install,
        headless_install=namespace.headless_install,
        verify_release_connectivity=namespace.verify_release_connectivity,
        repair=namespace.repair,
        no_update_check=namespace.no_update_check,
        install_root=namespace.install_root,
        handoff_geometry=namespace.handoff_geometry,
        manifest_url=namespace.manifest_url,
    )
