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
import socket
import sys

from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.managed_comfy_repair import (
    SubprocessManagedComfyRepairer,
)
from launcher.sugarsubstitute_launcher.platforms import WINDOWS_X64


class _RuntimeLayout(InstallLayout):
    """Use the test interpreter at the external installed-runtime boundary."""

    @property
    def runtime_python(self) -> Path:
        """Run the synthetic maintenance package in the repository environment."""
        return Path(sys.executable)


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
    repairer.provision_full_managed_comfy(layout=layout, ownership=ownership)
    repairer.validate_full_managed_comfy(layout=layout, ownership=ownership)

    prefix = (
        str(layout.runtime_python),
        "-m",
        "substitute.app.maintenance",
    )
    suffix = ("--workspace", str(layout.root / "comfyui"))
    assert runner.commands == [
        (*prefix, "repair-owned-nodes", *suffix),
        (*prefix, "validate-owned-nodes", *suffix),
        (*prefix, "provision-full-managed-comfy", *suffix),
        (*prefix, "validate-full-managed-comfy", *suffix),
    ]


def test_maintenance_activity_arrives_before_command_completion(tmp_path: Path) -> None:
    """Deliver producer output while a real maintenance command waits for its consumer."""
    layout = _RuntimeLayout.from_root(tmp_path)
    package = layout.app_dir / "substitute" / "app"
    package.mkdir(parents=True)
    (package.parent / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "maintenance.py").write_text(
        "import socket, sys\n"
        "with socket.socket() as server:\n"
        "    server.bind(('127.0.0.1', 0))\n"
        "    server.listen(1)\n"
        "    server.settimeout(10)\n"
        "    print(server.getsockname()[1], file=sys.stderr, flush=True)\n"
        "    connection, _ = server.accept()\n"
        "    with connection:\n"
        "        connection.settimeout(10)\n"
        "        assert connection.recv(1) == b'x'\n",
        encoding="utf-8",
    )
    observations: list[str] = []

    def observe(line: str) -> None:
        """Acknowledge output so the still-running producer can finish."""
        observations.append(line)
        with socket.create_connection(("127.0.0.1", int(line)), timeout=5) as peer:
            peer.sendall(b"x")

    SubprocessManagedComfyRepairer(output_callback=observe).repair_owned_nodes(
        layout=layout,
        ownership=ManagedComfyOwnership("managed_local", layout.root / "comfyui", True),
    )
    assert len(observations) == 1
