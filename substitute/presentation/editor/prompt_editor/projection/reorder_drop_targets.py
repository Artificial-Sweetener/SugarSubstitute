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

"""Define immutable prompt reorder drop-target geometry values."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
)


@dataclass(frozen=True, slots=True)
class PromptReorderDropTargetVisual:
    """Describe one prepared drag destination and its hit-test rectangle."""

    target: PromptReorderDropTarget
    hit_rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptReorderRowDropLane:
    """Describe one populated-row hit lane and its stable insertion slots."""

    row_index: int
    visual_row_index: int
    hit_rect: QRectF
    slot_visuals: tuple[PromptReorderDropTargetVisual, ...]


@dataclass(frozen=True, slots=True)
class PromptReorderBlankLineDropLane:
    """Describe one blank-line lane selected by vertical intent alone."""

    target: PromptGapBlankLineDropTarget
    hit_rect: QRectF


type PromptReorderDropLane = PromptReorderRowDropLane | PromptReorderBlankLineDropLane


def lane_matches_target(
    lane: PromptReorderDropLane,
    target: PromptReorderDropTarget | None,
) -> bool:
    """Return whether one prepared lane owns the supplied typed target."""

    if target is None:
        return False
    if isinstance(lane, PromptReorderBlankLineDropLane):
        return lane.target == target
    if not isinstance(target, PromptLineDropTarget):
        return False
    return any(visual.target == target for visual in lane.slot_visuals)


__all__ = [
    "PromptReorderBlankLineDropLane",
    "PromptReorderDropLane",
    "PromptReorderDropTargetVisual",
    "PromptReorderRowDropLane",
    "lane_matches_target",
]
