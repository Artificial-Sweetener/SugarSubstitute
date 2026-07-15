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

"""Define display-only projection state for prompt segment reorder previews."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionSnapshot:
    """Carry one projection snapshot used for reorder paint or geometry queries."""

    document_view: PromptDocumentView
    render_plan: PromptSyntaxRenderPlan
    chip_rendered_ranges_by_index: dict[int, tuple[int, int]]
    chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]]
    gap_ranges_by_index: dict[int, tuple[int, int]]


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewState:
    """Carry display-only reorder preview projection inputs for reorder mode."""

    preview_snapshot: PromptReorderProjectionSnapshot
    base_drag_snapshot: PromptReorderProjectionSnapshot | None
    ordered_chip_indices: tuple[int, ...]
    dragged_chip_index: int | None
    preview_layout_key: Hashable | None = None
    base_drag_layout_key: Hashable | None = None
    active_drop_target_identity: Hashable | None = None
    instrumentation_gesture_id: int | None = None
    instrumentation_event_id: int | None = None
    instrumentation_reason: str = ""


__all__ = [
    "PromptReorderPreviewState",
    "PromptReorderProjectionSnapshot",
]
