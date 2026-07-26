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

"""Define immutable facts consumed by reorder preview projection."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderStateView,
)


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewBuildFacts:
    """Carry one coherent input generation for preview projection."""

    preview_layout_view: PromptReorderLayoutView | None
    base_drag_layout_view: PromptReorderLayoutView | None
    preview_reorder_state: PromptReorderStateView | None
    base_drag_reorder_state: PromptReorderStateView | None
    ordered_chip_indices: tuple[int, ...]
    dragged_segment_index: int | None
    drop_target: PromptReorderDropTarget | None


__all__ = ["PromptReorderPreviewBuildFacts"]
