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

"""Define icon asset fetching contracts for Cube Library presentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CubeIconAsset:
    """Represent one fetched cube icon asset without Qt dependencies."""

    content: bytes
    media_type: str


@runtime_checkable
class CubeIconAssetFetcher(Protocol):
    """Fetch target-relative cube icon asset data for presentation decoding."""

    def fetch_icon_asset(self, relative_url: str) -> CubeIconAsset | None:
        """Return icon bytes for one target-relative URL, or ``None`` on failure."""


__all__ = ["CubeIconAsset", "CubeIconAssetFetcher"]
