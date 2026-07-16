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

"""Prepare an attached Comfy workspace without creating or replacing Python."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from substitute.domain.onboarding import ComfyPythonBinding
from substitute.infrastructure.comfy.core_nodepack_reconciler import (
    ensure_core_comfy_nodepacks,
)
from substitute.infrastructure.comfy.manager_provisioner import (
    ensure_workspace_manager_custom_node,
)
from substitute.infrastructure.comfy.hardware_detection import detect_hardware
from substitute.infrastructure.comfy.managed_acceleration_reconciler import (
    reconcile_managed_acceleration_stack,
)
from substitute.infrastructure.comfy.sugarcubes_maintenance_runner import (
    run_sugarcubes_baseline_maintenance,
)
from substitute.infrastructure.comfy.workspace_python_discovery import (
    resolve_attached_comfy_python,
)

StatusCallback = Callable[[str], None]
LogCallback = Callable[[str], None]


def prepare_attached_comfy_setup(
    *,
    workspace: Path,
    python_executable: Path | None = None,
    on_status: StatusCallback | None = None,
    on_log: LogCallback | None = None,
    **_unused: object,
) -> ComfyPythonBinding:
    """Verify and prepare an existing Comfy installation in its own environment."""

    binding = resolve_attached_comfy_python(
        workspace,
        explicit_executable=python_executable,
    )
    if on_log is not None:
        on_log(
            f"Using ComfyUI Python {binding.version} ({binding.architecture}) at "
            f"{binding.executable}."
        )
    if on_status is not None:
        on_status("Provisioning ComfyUI-Manager.")
    ensure_workspace_manager_custom_node(
        workspace,
        python_executable=binding.executable,
        on_log=on_log,
    )
    if on_status is not None:
        on_status("Installing Substitute Comfy nodepacks.")
    ensure_core_comfy_nodepacks(
        workspace,
        python_executable=binding.executable,
        on_log=on_log,
    )
    if on_status is not None:
        on_status("Preparing Base-Cubes dependencies.")
    run_sugarcubes_baseline_maintenance(
        workspace,
        python_executable=binding.executable,
        on_log=on_log,
    )
    if on_status is not None:
        on_status("Preparing acceleration support.")
    reconcile_managed_acceleration_stack(
        workspace=workspace,
        python_executable=binding.executable,
        detection=detect_hardware(),
        on_status=on_status,
        on_log=on_log,
    )
    return binding


__all__ = ["prepare_attached_comfy_setup"]
