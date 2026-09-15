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

"""Define process-image and invocation authority independently of OS inspection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ApplicationProcessScope(Protocol):
    """Constrain process recovery to the image and operation owned by one caller."""

    def accepts_executable(self, executable: Path) -> bool:
        """Reject unrelated images before inspecting their arguments."""

    def accepts_invocation(
        self, executable: Path, arguments: Sequence[str], working_directory: Path
    ) -> bool:
        """Bind a kernel-observed image and command to the caller's ownership scope."""


@dataclass(frozen=True, slots=True)
class ExactExecutableProcessScope:
    """Constrain an authenticated source-runtime owner to explicit interpreter images."""

    executables: tuple[Path, ...]

    def accepts_executable(self, executable: Path) -> bool:
        """Require an exact resolved image, independent of argv spelling."""
        return executable.resolve() in {path.resolve() for path in self.executables}

    def accepts_invocation(
        self, executable: Path, arguments: Sequence[str], working_directory: Path
    ) -> bool:
        """Retain image authority for an already authenticated source-runtime owner."""
        return self.accepts_executable(executable)
