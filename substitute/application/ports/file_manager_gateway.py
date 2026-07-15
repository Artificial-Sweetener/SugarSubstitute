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

"""Define the cross-platform file-manager reveal boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class FileRevealStatus(str, Enum):
    """Describe the outcome of one native file-manager reveal request."""

    REVEALED = "revealed"
    OPENED_PARENT_DIRECTORY = "opened_parent_directory"
    PATH_UNAVAILABLE = "path_unavailable"
    MISSING = "missing"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FileRevealResult:
    """Report the user-visible outcome of revealing one local file."""

    status: FileRevealStatus

    @property
    def succeeded(self) -> bool:
        """Return whether the user was navigated to the asset or its folder."""

        return self.status in {
            FileRevealStatus.REVEALED,
            FileRevealStatus.OPENED_PARENT_DIRECTORY,
        }


class FileManagerGateway(Protocol):
    """Reveal an existing local file through the host operating system."""

    def reveal_file(self, asset_path: Path) -> FileRevealResult:
        """Reveal ``asset_path`` and return the resulting user-visible outcome."""


__all__ = [
    "FileManagerGateway",
    "FileRevealResult",
    "FileRevealStatus",
]
