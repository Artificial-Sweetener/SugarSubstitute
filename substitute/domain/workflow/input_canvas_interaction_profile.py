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

"""Define workflow-owned Input canvas interaction semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class InputCanvasInteractionCapability(StrEnum):
    """Name workflow facts that authorize families of Input interactions."""

    RASTER_ANALYSIS_SOURCE = "raster_analysis_source"


@dataclass(frozen=True, slots=True)
class InputCanvasInteractionProfile:
    """Describe interactions supported by one authoritative workflow surface."""

    capabilities: frozenset[InputCanvasInteractionCapability] = field(
        default_factory=frozenset
    )

    def supports(self, capability: InputCanvasInteractionCapability) -> bool:
        """Return whether the workflow surface authorizes one interaction family."""

        return capability in self.capabilities


__all__ = [
    "InputCanvasInteractionCapability",
    "InputCanvasInteractionProfile",
]
