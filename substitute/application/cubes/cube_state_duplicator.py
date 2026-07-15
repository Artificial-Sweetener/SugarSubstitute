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

"""Create independent copies of durable cube authoring state."""

from __future__ import annotations

from copy import deepcopy

from substitute.domain.workflow import CubeState


class CubeStateDuplicator:
    """Duplicate the complete cube aggregate while assigning a new alias."""

    def duplicate_as(self, source: CubeState, alias: str) -> CubeState:
        """Return an independent cube copy whose only changed field is its alias."""

        duplicate = deepcopy(source)
        duplicate.alias = alias
        return duplicate


__all__ = ["CubeStateDuplicator"]
