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

"""Resolve canonical Substitute runtime paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


@dataclass(frozen=True, slots=True)
class RuntimeLayout:
    """Describe the canonical launcher-managed runtime layout."""

    runtime_root: Path
    platform: str

    @property
    def venv_root(self) -> Path:
        """Return the runtime virtual-environment root."""

        return self.runtime_root / ".venv"

    @property
    def python_executable(self) -> Path:
        """Return the target platform's runtime Python executable path."""

        if self.platform.startswith("win"):
            return self.venv_root / "Scripts" / "python.exe"
        return self.venv_root / "bin" / "python"


def runtime_layout_for_root(
    runtime_root: Path,
    *,
    platform: str | None = None,
) -> RuntimeLayout:
    """Return the canonical runtime layout for one runtime root."""

    return RuntimeLayout(
        runtime_root=runtime_root,
        platform=sys.platform if platform is None else platform,
    )
