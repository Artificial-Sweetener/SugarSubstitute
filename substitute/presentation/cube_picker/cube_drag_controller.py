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

"""Qt-free drag state for the cube staging drawer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from substitute.application.cubes import CubeStackDraftEntry

CubeDragSource = Literal["library", "draft_stack"]


@dataclass
class CubeDragState:
    """Track one active staging drag."""

    source: CubeDragSource
    entry: CubeStackDraftEntry
    source_draft_id: str | None = None
    insertion_index: int | None = None


class CubeDragController:
    """Own the current cube staging drag state."""

    def __init__(self) -> None:
        """Create an idle drag controller."""

        self._state: CubeDragState | None = None

    @property
    def state(self) -> CubeDragState | None:
        """Return the current drag state, if any."""

        return self._state

    def begin(
        self,
        *,
        source: CubeDragSource,
        entry: CubeStackDraftEntry,
        source_draft_id: str | None = None,
    ) -> CubeDragState:
        """Begin one drag."""

        self._state = CubeDragState(
            source=source,
            entry=entry,
            source_draft_id=source_draft_id,
        )
        return self._state

    def update_insertion_index(self, insertion_index: int | None) -> None:
        """Store the current stack insertion index candidate."""

        if self._state is not None:
            self._state.insertion_index = insertion_index

    def cancel(self) -> None:
        """Return to idle state."""

        self._state = None


__all__ = ["CubeDragController", "CubeDragSource", "CubeDragState"]
