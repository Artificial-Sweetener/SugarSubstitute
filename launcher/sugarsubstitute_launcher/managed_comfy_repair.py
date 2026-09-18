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

from collections.abc import Callable
import logging
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.subprocess_environment import (
    clean_frozen_parent_environment,
)
from sugarsubstitute_shared.windows_long_paths import (
    subprocess_path,
)

from launcher.sugarsubstitute_launcher.runtime_command import (
    SubprocessRuntimeCommandRunner,
)
from launcher.sugarsubstitute_launcher.runtime_models import RuntimeCommandRunner

_LOGGER = logging.getLogger(__name__)
_MAINTENANCE_TIMEOUT_SECONDS = 1800.0


class SubprocessManagedComfyRepairer:
    """Restore and validate owned nodes using code from the repaired exact app."""

    def __init__(
        self,
        *,
        runner: RuntimeCommandRunner | None = None,
        output_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Store the bounded hidden subprocess adapter."""

        self._runner = runner or SubprocessRuntimeCommandRunner(
            output_callback, timeout_seconds=_MAINTENANCE_TIMEOUT_SECONDS
        )

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

    def provision_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Build and reconcile the active environment within the repair transaction."""

        self._run("provision-full-managed-comfy", layout=layout, ownership=ownership)

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
    "SubprocessManagedComfyRepairer",
]
