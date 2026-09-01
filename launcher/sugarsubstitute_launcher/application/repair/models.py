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

"""Define immutable repair scopes, ownership evidence, and filesystem plans."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class RepairScope(str, Enum):
    """Identify the product boundary refreshed by a repair."""

    APPLICATION = "application"
    OWNED_COMFY_NODES = "owned_comfy_nodes"
    FULL_MANAGED_COMFY = "full_managed_comfy"


class RepairDisposition(str, Enum):
    """Describe what repair does with one existing path."""

    PRESERVE = "preserve"
    REPLACE = "replace"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class ManagedComfyOwnership:
    """Carry persisted facts used to prove a Comfy workspace is installer-owned."""

    target_mode: str
    workspace_root: Path | None
    install_owned: bool


@dataclass(frozen=True, slots=True)
class RepairOperation:
    """Describe one path decision in a repair plan."""

    path: Path
    disposition: RepairDisposition
    reason: str


@dataclass(frozen=True, slots=True)
class RepairPlan:
    """Describe a deterministic, reviewable repair without performing side effects."""

    scope: RepairScope
    install_root: Path
    operations: tuple[RepairOperation, ...]

    def operation_for(self, path: Path) -> RepairOperation | None:
        """Return the most-specific operation governing a path."""

        resolved = path.resolve()
        candidates = tuple(
            operation
            for operation in self.operations
            if resolved == operation.path or resolved.is_relative_to(operation.path)
        )
        if not candidates:
            return None
        return max(candidates, key=lambda operation: len(operation.path.parts))


@dataclass(frozen=True, slots=True)
class RepairReplacement:
    """Bind one verified staged artifact to its final repair destination."""

    destination: Path
    staged_path: Path
