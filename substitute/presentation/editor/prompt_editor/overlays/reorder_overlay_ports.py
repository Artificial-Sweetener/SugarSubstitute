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

"""Define typed ports consumed by the reorder overlay shell."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QScrollBar, QWidget

from ..projection.reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from ..projection.reorder_visual_snapshot import PromptReorderProjectionPaintSnapshot
from ..projection.reorder_surface_visual_state import (
    PromptReorderSurfaceVisualPublication,
)
from .reorder_view import PromptReorderView


class PromptReorderViewFactory(Protocol):
    """Create the passive reorder view hosted by the overlay shell."""

    def __call__(self, parent: QWidget) -> PromptReorderView:
        """Return one passive reorder view under the supplied parent."""


class PromptReorderEditor(Protocol):
    """Describe editor APIs consumed by the concrete reorder overlay shell."""

    def document(self) -> QTextDocument:
        """Return the editor document used for text metrics."""

    def viewport(self) -> QWidget:
        """Return the viewport that owns the overlay."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the editor-visible vertical scrollbar."""

    def setFocus(self) -> None:
        """Keep real keyboard focus on the host editor during reorder gestures."""

    def reset_reorder_geometry_cache_counters(self) -> None:
        """Reset deterministic projection geometry counters for focused tests."""

    def reorder_geometry_cache_counters(self) -> dict[str, object]:
        """Return deterministic projection geometry counters."""

    def reorder_live_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned live paint snapshots for visible reorder chips."""

    def reorder_preview_chip_projection_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        chip_indices: frozenset[int] | None = None,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned preview paint snapshots for visible reorder chips."""

    def set_reorder_surface_visual_publication(
        self,
        publication: PromptReorderSurfaceVisualPublication,
    ) -> None:
        """Publish reorder chrome and suppression as one prepared frame."""


__all__ = [
    "PromptReorderEditor",
    "PromptReorderViewFactory",
]
