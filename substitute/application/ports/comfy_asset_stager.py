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

"""Define Comfy asset staging contracts consumed by generation orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from substitute.domain.generation import ComfyStagedAsset


@runtime_checkable
class ComfyAssetStager(Protocol):
    """Make one local source asset addressable by the active Comfy target."""

    def stage_file_for_load_image(
        self,
        *,
        source_path: Path,
        target_subfolder: str,
        content_hash: str,
    ) -> ComfyStagedAsset:
        """Stage one file and return the value to write into LoadImage inputs."""


__all__ = ["ComfyAssetStager"]
