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

"""Define generation-time asset staging result models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

AssetStagingOperation = Literal["direct", "uploaded"]


@dataclass(frozen=True)
class ComfyStagedAsset:
    """Describe a source asset after it has been made usable by Comfy."""

    source_path: Path
    execution_value: str
    operation: AssetStagingOperation


@dataclass(frozen=True)
class AssetStagingFailure:
    """Describe one graph asset that could not be staged for execution."""

    node_id: str
    node_class: str
    input_name: str
    source_value: str
    message: str


__all__ = ["AssetStagingFailure", "AssetStagingOperation", "ComfyStagedAsset"]
