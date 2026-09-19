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

"""Represent completion units reported by the owner of a startup operation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SplashProgress:
    """Carry honest completed units; activity must never increment this value."""

    completed: int
    total: int

    def __post_init__(self) -> None:
        """Reject impossible counts and implicit numeric coercion at process boundaries."""
        if type(self.completed) is not int or type(self.total) is not int:
            raise ValueError("Splash progress units must be integers.")
        if self.total <= 0 or not 0 <= self.completed <= self.total:
            raise ValueError("Splash progress units are outside their total.")
