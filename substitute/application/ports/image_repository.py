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

"""Define image persistence and loading contracts for canvas orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ImageRepository(Protocol):
    """Describe image IO operations used by application canvas services."""

    def load_image(self, path: Path) -> object | None:
        """Load image payload for UI presentation from a filesystem path."""

    def save_image(self, path: Path, *, image: object) -> bool:
        """Save provided image payload to filesystem destination."""

    def save_blank_mask(self, path: Path, *, size: object) -> bool:
        """Create and save a transparent mask image to the destination path."""

    def image_dimensions(self, path: Path) -> tuple[int, int] | None:
        """Return image dimensions when the filesystem image is readable."""


__all__ = [
    "ImageRepository",
]
