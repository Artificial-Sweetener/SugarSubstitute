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

"""Resolve SugarCubes runtime capabilities from repository contents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SugarCubesRuntimeContract:
    """Describe one supported SugarCubes maintenance package layout."""

    maintenance_path: Path
    maintenance_module: str
    backend_path: Path

    def is_available(self, sugarcubes_root: Path) -> bool:
        """Return whether every runtime capability file exists."""

        return all(
            (sugarcubes_root / relative_path).is_file()
            for relative_path in (self.maintenance_path, self.backend_path)
        )


SUGARCUBES_RUNTIME_CONTRACTS = (
    SugarCubesRuntimeContract(
        maintenance_path=Path("sugarcubes/maintenance.py"),
        maintenance_module="sugarcubes.maintenance",
        backend_path=Path("sugarcubes/backend/__init__.py"),
    ),
    SugarCubesRuntimeContract(
        maintenance_path=Path("backend/maintenance.py"),
        maintenance_module="backend.maintenance",
        backend_path=Path("backend/__init__.py"),
    ),
)


def resolve_sugarcubes_runtime_contract(
    sugarcubes_root: Path,
) -> SugarCubesRuntimeContract:
    """Return the supported runtime contract implemented by a checkout."""

    for contract in SUGARCUBES_RUNTIME_CONTRACTS:
        if contract.is_available(sugarcubes_root):
            return contract
    raise RuntimeError("SugarCubes offline maintenance entrypoint is missing.")


__all__ = [
    "SUGARCUBES_RUNTIME_CONTRACTS",
    "SugarCubesRuntimeContract",
    "resolve_sugarcubes_runtime_contract",
]
