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

"""Verify installer app handoffs return through the stable supervisor."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher import process
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.windows_long_paths import subprocess_path


def test_installer_handoff_builds_stable_launcher_command(tmp_path: Path) -> None:
    """Setup completion must not execute the application child directly."""

    layout = InstallLayout.from_root(tmp_path / "install")
    app_command = [
        subprocess_path(layout.runtime_python),
        subprocess_path(layout.app_entrypoint),
        f"--install-root={subprocess_path(layout.root)}",
        "--handoff-geometry=10,20,1200,800",
        "--locale=ja",
        "--unrelated-internal-flag",
    ]

    assert process.build_installed_launcher_handoff_command(app_command) == [
        subprocess_path(layout.executable_path),
        f"--install-root={subprocess_path(layout.root)}",
        "--handoff-geometry=10,20,1200,800",
        "--locale=ja",
    ]


def test_installer_handoff_starts_only_stable_launcher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The handoff adapter should delegate its rewritten launcher command."""

    layout = InstallLayout.from_root(tmp_path / "install")
    app_command = [
        "python",
        "main.py",
        f"--install-root={layout.root}",
    ]
    started: list[list[str]] = []
    monkeypatch.setattr(
        process,
        "start_detached_handoff",
        lambda command: started.append(list(command)),
    )

    process.start_installed_launcher_handoff(app_command)

    assert started == [
        [
            subprocess_path(layout.executable_path),
            f"--install-root={subprocess_path(layout.root)}",
        ]
    ]
