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

"""Own compact-mode geometry for one cube stack presentation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_COMPACT_WIDTH,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_STACK_COMPACT_WIDTH,
    CUBE_STACK_EXPANDED_WIDTH,
)
from substitute.presentation.workflows.cube_item import CubeItem
from substitute.presentation.workflows.cube_stack_geometry_trace import (
    log_cube_stack_transition_frame,
)
from substitute.presentation.workflows.reorderable_tabs_base import (
    ReorderableTabItemBase,
)


class CubeStackPresentationGeometry:
    """Apply all compact presentation geometry through one focused owner."""

    def __init__(
        self,
        *,
        stack: QWidget,
        items: Callable[[], tuple[ReorderableTabItemBase, ...]],
        set_stack_width: Callable[[int], None],
        set_placeholder_compact: Callable[[bool], None],
        set_placeholder_progress: Callable[[float], None],
        sync_indicator: Callable[[], None],
        schedule_indicator_realign: Callable[[], None],
    ) -> None:
        """Store narrow rendering operations supplied by the cube stack view."""

        self._stack = stack
        self._items = items
        self._set_stack_width = set_stack_width
        self._set_placeholder_compact = set_placeholder_compact
        self._set_placeholder_progress = set_placeholder_progress
        self._sync_indicator = sync_indicator
        self._schedule_indicator_realign = schedule_indicator_realign
        self._compact = False
        self._transition_active = False

    @property
    def compact(self) -> bool:
        """Return the committed compact presentation state."""

        return self._compact

    def set_compact(self, compact: bool) -> None:
        """Commit compact state unless that endpoint is already stable."""

        if compact == self._compact and not self._transition_active:
            return
        self.finish_transition(compact)

    def begin_transition(self, target_compact: bool) -> None:
        """Prepare cube items for interpolated compact presentation frames."""

        self._transition_active = True
        for item in self._items():
            if isinstance(item, CubeItem):
                item.beginCompactTransition(target_compact)

    def apply_frame(
        self,
        *,
        stack_width: int,
        item_width: int,
        compact_progress: float,
    ) -> None:
        """Apply one interpolated geometry frame to the stack and its children."""

        log_cube_stack_transition_frame(
            stack=self._stack,
            stack_width=stack_width,
            item_width=item_width,
            compact_progress=compact_progress,
        )
        self._set_stack_width(stack_width)
        for item in self._items():
            item.setFixedWidth(item_width)
            if isinstance(item, CubeItem):
                item.setCompactProgress(compact_progress)
        self._set_placeholder_progress(compact_progress)
        self._sync_indicator()

    def finish_transition(self, target_compact: bool) -> None:
        """Commit the exact endpoint and realign selection presentation."""

        self._transition_active = False
        self._compact = target_compact
        self._set_stack_width(
            CUBE_STACK_COMPACT_WIDTH if target_compact else CUBE_STACK_EXPANDED_WIDTH
        )
        self._set_placeholder_compact(target_compact)
        for item in self._items():
            self.apply_item(item)
        self._schedule_indicator_realign()

    def apply_item(self, item: ReorderableTabItemBase) -> None:
        """Apply committed presentation state to one newly inserted item."""

        width = CUBE_ITEM_COMPACT_WIDTH if self._compact else CUBE_ITEM_EXPANDED_WIDTH
        if isinstance(item, CubeItem):
            item.finishCompactTransition(self._compact)
        item.setFixedWidth(width)


__all__ = ["CubeStackPresentationGeometry"]
