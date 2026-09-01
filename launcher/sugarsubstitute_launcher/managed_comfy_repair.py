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

"""Invoke exact managed-Comfy maintenance through the repaired app runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import logging
from pathlib import Path
import subprocess
import sys
from typing import Protocol

from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
    standard_child_process_dll_search_path,
)
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
    subprocess_working_directory,
)

_LOGGER = logging.getLogger(__name__)
_MAINTENANCE_TIMEOUT_SECONDS = 1800.0


class ManagedComfyRepairCommandRunner(Protocol):
    """Run one bounded application maintenance command."""

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Run the command or raise with captured failure context."""


class SubprocessManagedComfyRepairCommandRunner:
    """Run maintenance hidden, without a shell, and with a hard deadline."""

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Run one maintenance child and retain bounded diagnostic output."""

        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            creationflags = subprocess.CREATE_NO_WINDOW
        with standard_child_process_dll_search_path():
            result = subprocess.run(  # noqa: S603
                list(command),
                cwd=subprocess_working_directory(cwd),
                env=dict(env),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_MAINTENANCE_TIMEOUT_SECONDS,
                check=False,
                shell=False,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
        if result.returncode != 0:
            output = (result.stdout + "\n" + result.stderr).strip()
            raise RuntimeError(
                "Managed Comfy maintenance failed "
                f"with exit code {result.returncode}: {output[-8000:]}"
            )


class SubprocessManagedComfyRepairer:
    """Restore and validate owned nodes using code from the repaired exact app."""

    def __init__(
        self,
        *,
        runner: ManagedComfyRepairCommandRunner | None = None,
    ) -> None:
        """Store the bounded hidden subprocess adapter."""

        self._runner = runner or SubprocessManagedComfyRepairCommandRunner()

    def repair_owned_nodes(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Restore exact owned nodepack sources and their dependencies."""

        self._run("repair-owned-nodes", layout=layout, ownership=ownership)

    def validate_owned_nodes(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Prove exact nodepack identities through the same release code."""

        self._run("validate-owned-nodes", layout=layout, ownership=ownership)

    def stage_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
        destination: Path,
    ) -> None:
        """Build a fresh workspace candidate through the repaired exact app."""

        self._run(
            "stage-full-managed-comfy",
            layout=layout,
            ownership=ownership,
            destination=destination,
        )

    def validate_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Validate promoted core, environment, and owned nodepacks."""

        self._run(
            "validate-full-managed-comfy",
            layout=layout,
            ownership=ownership,
        )

    def _run(
        self,
        operation: str,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
        destination: Path | None = None,
    ) -> None:
        """Validate ownership again and invoke one application maintenance command."""

        workspace = ownership.workspace_root
        expected = (layout.root / "comfyui").resolve()
        if (
            ownership.target_mode != "managed_local"
            or not ownership.install_owned
            or workspace is None
            or workspace.resolve() != expected
        ):
            raise RuntimeError("Managed Comfy repair ownership is not exact.")
        environment = clean_frozen_parent_environment()
        environment["PYTHONPATH"] = str(layout.app_dir)
        workspace_argument = destination if destination is not None else expected
        command: tuple[str, ...] = (
            subprocess_path(layout.runtime_python),
            "-m",
            "substitute.app.maintenance",
            operation,
            "--workspace",
            subprocess_path(workspace_argument),
        )
        if destination is not None:
            command += (
                "--install-root",
                subprocess_path(layout.root),
            )
        _LOGGER.info(
            "Running managed Comfy repair operation | operation=%s workspace=%s",
            operation,
            expected,
        )
        self._runner.run(command, cwd=layout.app_dir, env=environment)


__all__ = [
    "ManagedComfyRepairCommandRunner",
    "SubprocessManagedComfyRepairCommandRunner",
    "SubprocessManagedComfyRepairer",
]
