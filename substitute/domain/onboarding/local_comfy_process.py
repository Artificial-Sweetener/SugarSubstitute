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

"""Describe confidently identified local ComfyUI processes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LocalComfyProcess:
    """Identify one running ComfyUI Python process without owning its lifecycle."""

    pid: int
    create_time: float
    python_executable: Path
    workspace: Path


@dataclass(frozen=True, slots=True)
class LocalComfyTerminationResult:
    """Report the verified outcome of one explicit local-Comfy shutdown request."""

    requested_pids: tuple[int, ...]
    terminated_pids: tuple[int, ...]
    rejected_pids: tuple[int, ...]
    remaining_pids: tuple[int, ...]

    @property
    def succeeded(self) -> bool:
        """Return whether every requested process was safely terminated."""

        return bool(self.requested_pids) and not (
            self.rejected_pids or self.remaining_pids
        )


__all__ = ["LocalComfyProcess", "LocalComfyTerminationResult"]
