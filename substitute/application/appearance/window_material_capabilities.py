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

"""Describe native window-material support separately from system colors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WindowMaterialCapabilities:
    """Capture native shell materials supported by the current platform."""

    acrylic_available: bool = False
    mica_alt_available: bool = False

    @property
    def backdrop_available(self) -> bool:
        """Return whether any native window material is supported."""

        return self.acrylic_available or self.mica_alt_available


__all__ = ["WindowMaterialCapabilities"]
