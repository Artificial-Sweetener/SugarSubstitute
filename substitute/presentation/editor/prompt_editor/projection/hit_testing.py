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

"""Own projection hit testing over prepared layout geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF

from .model import PromptProjectionCaretState

if TYPE_CHECKING:
    from .layout_engine import PromptProjectionLayout


@dataclass(frozen=True, slots=True)
class PromptProjectionCaretHit:
    """Describe one pointer-selected caret state and its document rect."""

    state: PromptProjectionCaretState
    document_rect: QRectF


@dataclass(frozen=True, slots=True)
class PromptProjectionDragSelectionTarget:
    """Describe one wrapped-line drag-selection endpoint resolved by the layout."""

    state: PromptProjectionCaretState
    line_index: int | None


@dataclass(frozen=True, slots=True)
class PromptProjectionHitTester:
    """Route pointer positions through snapshot-backed projection hit testing."""

    layout: PromptProjectionLayout

    def hit_test(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretState:
        """Return the logical caret state implied by one viewport-local point."""

        return self.layout._hit_test_from_geometry(  # noqa: SLF001
            viewport_position,
            scroll_offset=scroll_offset,
            preferred_line_index=preferred_line_index,
        )

    def caret_hit_test(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretHit:
        """Return the logical and visual caret target for one pointer point."""

        return self.layout._caret_hit_test_from_geometry(  # noqa: SLF001
            viewport_position,
            scroll_offset=scroll_offset,
            preferred_line_index=preferred_line_index,
        )

    def resolve_drag_selection_endpoint(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        anchor_line_index: int | None = None,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionDragSelectionTarget:
        """Resolve one drag-selection endpoint using wrapped-line row progression."""

        return self.layout._resolve_drag_selection_endpoint_from_geometry(  # noqa: SLF001
            viewport_position,
            scroll_offset=scroll_offset,
            anchor_line_index=anchor_line_index,
            preferred_line_index=preferred_line_index,
        )


__all__ = [
    "PromptProjectionCaretHit",
    "PromptProjectionDragSelectionTarget",
    "PromptProjectionHitTester",
]
