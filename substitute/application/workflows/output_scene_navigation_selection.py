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

"""Describe atomic scene-level Output canvas navigation selections."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OutputSceneNavigationSelection:
    """Carry one complete Scene-to-Batch-to-output route transition."""

    scene_key: str | None
    overview: bool
    source_key: str | None
    set_index: int
    image_id: UUID | None

    def __post_init__(self) -> None:
        """Reject partial route combinations that cannot be persisted safely."""

        if self.set_index < 0:
            raise ValueError("Output set index cannot be negative")
        if self.overview and (
            self.scene_key is not None
            or self.source_key is not None
            or self.set_index != 1
            or self.image_id is not None
        ):
            raise ValueError(
                "Scene overview cannot include a scene, source, grid, or image"
            )
        if not self.overview and not self.scene_key:
            raise ValueError("Concrete scene selection requires a scene key")
        if self.set_index == 0 and self.image_id is not None:
            raise ValueError("Batch grid selection cannot include an image")
        if self.image_id is not None and self.source_key is None:
            raise ValueError("Concrete output selection requires a source")


__all__ = ["OutputSceneNavigationSelection"]
