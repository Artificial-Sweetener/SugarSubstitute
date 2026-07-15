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

"""Define typed reorder displacement intents emitted by input adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QPoint

from substitute.application.prompt_editor import PromptReorderDropTarget


ReorderDisplacementInputSource = Literal["pointer", "keyboard"]


@dataclass(frozen=True, slots=True)
class ReorderDisplacementIntent:
    """Describe one visual displacement target selected by an input adapter."""

    source: ReorderDisplacementInputSource
    held_segment_index: int
    target: PromptReorderDropTarget | None
    pointer_global_pos: QPoint | None
    reason: str


__all__ = ["ReorderDisplacementInputSource", "ReorderDisplacementIntent"]
