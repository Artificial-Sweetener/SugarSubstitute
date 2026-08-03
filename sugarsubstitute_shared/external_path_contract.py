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

"""Define path-capacity contracts for external components."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

from sugarsubstitute_shared.windows_long_paths import WINDOWS_LEGACY_PATH_LIMIT


@dataclass(frozen=True, slots=True)
class ExternalPathContract:
    """Describe descendant capacity required below an external-tool path."""

    component: str
    reserved_descendant_length: int

    def accepts(self, root: Path) -> bool:
        """Return whether the root preserves the required Windows path capacity."""

        if self.reserved_descendant_length < 0:
            raise ValueError("Reserved descendant length cannot be negative.")
        if sys.platform != "win32":
            return True
        return (
            len(str(root)) + self.reserved_descendant_length < WINDOWS_LEGACY_PATH_LIMIT
        )

    @property
    def maximum_windows_root_length(self) -> int:
        """Return the longest accepted Windows root for this contract."""

        return WINDOWS_LEGACY_PATH_LIMIT - self.reserved_descendant_length - 1


__all__ = ["ExternalPathContract"]
