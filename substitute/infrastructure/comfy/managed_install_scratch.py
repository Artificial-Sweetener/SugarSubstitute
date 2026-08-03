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

"""Declare and allocate managed-install external scratch storage."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.external_path_contract import ExternalPathContract
from sugarsubstitute_shared.external_scratch import (
    ExternalScratchWorkspace,
    allocate_external_scratch,
)

PIP_TEMP_DESCENDANT_BUDGET = 180
_MANAGED_TEMP_DIRECTORY_LENGTH = len("\\temp")
MANAGED_INSTALL_PATH_CONTRACT = ExternalPathContract(
    component="managed ComfyUI installer",
    reserved_descendant_length=(
        _MANAGED_TEMP_DIRECTORY_LENGTH + PIP_TEMP_DESCENDANT_BUDGET
    ),
)


def allocate_managed_install_scratch(workspace: Path) -> ExternalScratchWorkspace:
    """Reserve short scratch storage for managed-install child processes."""

    return allocate_external_scratch(
        preferred_storage_path=workspace,
        namespace="managed-comfy",
        contract=MANAGED_INSTALL_PATH_CONTRACT,
    )


__all__ = [
    "MANAGED_INSTALL_PATH_CONTRACT",
    "PIP_TEMP_DESCENDANT_BUDGET",
    "allocate_managed_install_scratch",
]
