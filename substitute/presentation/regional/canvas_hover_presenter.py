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

"""Present transient regional hover on CuteCanvas mask layers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from PySide6.QtGui import QColor

from substitute.domain.common import MaskAssociationKey
from substitute.domain.workflow import WorkflowState
from substitute.presentation.regional.color_provider import (
    authored_region_color,
    region_color,
)


class RegionalMaskColorTarget(Protocol):
    """Expose the narrow CuteCanvas color mutation used for hover feedback."""

    def set_mask_properties(self, mask_id: UUID, *, color: QColor) -> bool:
        """Apply one transient or baseline mask color."""


class RegionalCanvasHoverPresenter:
    """Highlight one associated mask layer and restore deterministic colors."""

    def __init__(
        self,
        *,
        workflow: Callable[[], WorkflowState | None],
        color_target: RegionalMaskColorTarget,
    ) -> None:
        """Store active workflow and CuteCanvas presentation boundaries."""

        self._workflow = workflow
        self._color_target = color_target
        self._active: tuple[MaskAssociationKey, int] | None = None

    def show(self, association_key: MaskAssociationKey, region_index: int) -> None:
        """Show transient emphasis for one materialized ordered mask."""

        if self._active == (association_key, region_index):
            return
        self.clear()
        workflow = self._workflow()
        collection = (
            None
            if workflow is None
            else workflow.canvas.regional_mask_collection(association_key)
        )
        if collection is None or not 0 <= region_index < len(collection.entries):
            return
        entry = collection.entries[region_index]
        if entry.mask_id is None:
            return
        highlighted = authored_region_color(
            entry.authored_color,
            region_color(region_index, len(collection.entries)),
        ).lighter(135)
        if self._color_target.set_mask_properties(entry.mask_id, color=highlighted):
            self._active = (association_key, region_index)

    def clear(self) -> None:
        """Restore the deterministic baseline color of the hovered mask."""

        active = self._active
        self._active = None
        if active is None:
            return
        workflow = self._workflow()
        collection = (
            None
            if workflow is None
            else workflow.canvas.regional_mask_collection(active[0])
        )
        if collection is None or not 0 <= active[1] < len(collection.entries):
            return
        entry = collection.entries[active[1]]
        if entry.mask_id is None:
            return
        self._color_target.set_mask_properties(
            entry.mask_id,
            color=authored_region_color(
                entry.authored_color,
                region_color(active[1], len(collection.entries)),
            ),
        )


__all__ = ["RegionalCanvasHoverPresenter", "RegionalMaskColorTarget"]
