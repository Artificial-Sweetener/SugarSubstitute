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

"""Identify one image within Comfy list execution and tensor batch space."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class OutputResultPosition:
    """Preserve independent Comfy list and image-batch coordinates."""

    list_index: int
    batch_index: int

    def __post_init__(self) -> None:
        """Reject coordinates that cannot identify a Comfy image result."""

        if self.list_index < 0 or self.batch_index < 0:
            raise ValueError("Output result coordinates must be non-negative.")


__all__ = ["OutputResultPosition"]
