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

"""Verify app-runtime managed-Comfy maintenance command composition."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair import ManagedComfyOwnership
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.managed_comfy_repair import (
    SubprocessManagedComfyRepairer,
)
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64


class _Runner:
    """Record maintenance commands without creating a process."""

    def __init__(self) -> None:
        """Initialize the captured command list."""

        self.commands: list[tuple[str, ...]] = []

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Capture command, working directory, and release import path."""

        assert cwd == Path(command[0]).parents[3] / "app"
        assert env["PYTHONPATH"] == str(cwd)
        self.commands.append(tuple(command))


def test_repairer_uses_repaired_runtime_and_exact_managed_workspace(
    tmp_path: Path,
) -> None:
    """Both repair and validation should execute code from the promoted app release."""

    layout = InstallLayout.from_root(tmp_path / "install", target=WINDOWS_X64)
    ownership = ManagedComfyOwnership("managed_local", layout.root / "comfyui", True)
    runner = _Runner()
    repairer = SubprocessManagedComfyRepairer(runner=runner)

    repairer.repair_owned_nodes(layout=layout, ownership=ownership)
    repairer.validate_owned_nodes(layout=layout, ownership=ownership)

    prefix = (
        str(layout.runtime_python),
        "-m",
        "substitute.app.maintenance",
    )
    suffix = ("--workspace", str(layout.root / "comfyui"))
    assert runner.commands == [
        (*prefix, "repair-owned-nodes", *suffix),
        (*prefix, "validate-owned-nodes", *suffix),
    ]
