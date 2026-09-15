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

"""Define the completion and failure contract of a prepared repair."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


class RepairExecutionError(RuntimeError):
    """Report a prepared repair that cannot be executed or validated safely."""


@dataclass(frozen=True, slots=True)
class CompletedRepair:
    """Describe one committed repair and its retained rollback quarantine."""

    version: str
    quarantine_root: Path
    repaired_managed_comfy_nodes: bool
    comfy_quarantine_root: Path | None = None
