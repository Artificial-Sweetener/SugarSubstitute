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

"""Publish coherent immutable state for prompt reorder interaction geometry."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
)

from .reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .reorder_drop_targets import (
    PromptReorderDropLane,
    PromptReorderDropTargetVisual,
)
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
)
from .reorder_state import (
    PromptReorderPreviewTargetIdentity,
    ReorderBaseDragGeometryKey,
)


@dataclass(frozen=True, slots=True)
class PromptReorderInteractionGeometryState:
    """Carry one atomic layout, snapshot, placement, and identity publication."""

    document_view: PromptDocumentView | None = None
    original_layout_view: PromptReorderLayoutView | None = None
    current_layout_view: PromptReorderLayoutView | None = None
    base_drag_layout_view: PromptReorderLayoutView | None = None
    preview_layout_view: PromptReorderLayoutView | None = None
    original_reorder_state: PromptReorderStateView | None = None
    current_reorder_state: PromptReorderStateView | None = None
    base_drag_reorder_state: PromptReorderStateView | None = None
    preview_reorder_state: PromptReorderStateView | None = None
    preview_snapshot: PromptReorderPreviewSnapshot | None = None
    base_drag_snapshot: PromptReorderPreviewSnapshot | None = None
    preview_layout_target_identity: PromptReorderPreviewTargetIdentity | None = None
    preview_geometry_target_identity: PromptReorderPreviewTargetIdentity | None = None
    live_chip_geometry_snapshot: PromptReorderChipGeometrySnapshot | None = None
    preview_chip_geometry_snapshot: PromptReorderChipGeometrySnapshot | None = None
    base_drag_chip_geometry_snapshot: PromptReorderChipGeometrySnapshot | None = None
    placement_snapshot: PromptReorderPlacementSnapshot | None = None
    active_placement: PromptReorderPlacementGeometry | None = None
    drop_target_visuals: tuple[PromptReorderDropTargetVisual, ...] = ()
    drop_target_lanes: tuple[PromptReorderDropLane, ...] = ()
    initial_ordered_indices: tuple[int, ...] = ()
    ordered_segment_indices: tuple[int, ...] = ()
    last_base_drag_geometry_key: ReorderBaseDragGeometryKey | None = None


__all__ = ["PromptReorderInteractionGeometryState"]
