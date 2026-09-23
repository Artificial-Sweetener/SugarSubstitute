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

"""Own mounted reorder chrome and projection-suppression presentation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QRegion

from .reorder_surface_visual_state import (
    PromptReorderSurfaceVisualContext,
    PromptReorderSurfaceVisualPublication,
    PromptReorderSurfaceVisualStateOwner,
    empty_reorder_surface_visual_publication,
)
from .reorder_visual_snapshot import PromptReorderProjectionPaintSnapshot


class PromptReorderSurfacePresentationOwner:
    """Publish reorder visuals and derive their current visible region."""

    def __init__(
        self,
        *,
        context: Callable[[], PromptReorderSurfaceVisualContext],
        preview_visible: Callable[[], bool],
        publish_render_frame: Callable[[], None],
        request_update: Callable[[], None],
    ) -> None:
        """Bind visual state to the exact mounted projection context."""

        self._context = context
        self._preview_visible = preview_visible
        self._publish_render_frame = publish_render_frame
        self._request_update = request_update
        self._visual_state = PromptReorderSurfaceVisualStateOwner()

    @property
    def visual_state(self) -> PromptReorderSurfaceVisualStateOwner:
        """Return atomic chrome and content-suppression state."""

        return self._visual_state

    def publish(self, publication: PromptReorderSurfaceVisualPublication) -> None:
        """Publish one prepared visual frame and refresh mounted presentation."""

        if not self._visual_state.publish(publication, context=self._context()):
            return
        self._publish_render_frame()
        self._request_update()

    def clear_before_preview_end(self) -> None:
        """Clear preview visuals while their receiving context is still current."""

        self._visual_state.publish(
            empty_reorder_surface_visual_publication(),
            context=self._context(),
        )

    def preview_visible_region(self) -> QRegion | None:
        """Return viewport content not suppressed by current preview snapshots."""

        if not self._preview_visible():
            return None
        snapshots = self._visual_state.state.suppression_snapshots_by_index
        if not snapshots:
            return None
        context = self._context()
        visible_region = QRegion(context.viewport_rect)
        for chip_index, snapshot in snapshots.items():
            if not self._snapshot_is_fresh(
                snapshot,
                chip_index=chip_index,
                context=context,
            ):
                continue
            for fragment_rect in snapshot.viewport_rects:
                visible_region = visible_region.subtracted(
                    QRegion(fragment_rect.toAlignedRect())
                )
        return visible_region

    @staticmethod
    def _snapshot_is_fresh(
        snapshot: PromptReorderProjectionPaintSnapshot,
        *,
        chip_index: int,
        context: PromptReorderSurfaceVisualContext,
    ) -> bool:
        """Return whether one suppression snapshot matches its receiving frame."""

        key = snapshot.key
        return not (
            key.source_revision != context.source_revision
            or key.viewport_rect != context.viewport_rect
            or key.scroll_offset != context.scroll_offset
            or key.preview_generation != context.preview_generation
            or key.segment_index != chip_index
            or key.mode != "preview"
        )


__all__ = ["PromptReorderSurfacePresentationOwner"]
