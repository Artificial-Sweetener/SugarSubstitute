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

"""Own cold-path visual lifecycle transitions for one reorder overlay."""

from __future__ import annotations

from collections.abc import Callable
from .reorder_animation_presentation import PromptReorderAnimationPresentationOwner
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_pointer_region_visual_owner import PromptReorderPointerRegionVisualOwner
from .reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_raster_publication import PromptReorderRasterPublicationOwner
from .reorder_refresh_identity import PromptReorderRefreshIdentityOwner
from .reorder_render_publication_owner import PromptReorderRenderPublicationOwner
from .reorder_visual_style import PromptReorderVisualStyle
from .reorder_theme_refresh import PromptReorderThemeRefreshRequest


class PromptReorderOverlayVisualLifecycleOwner:
    """Own theme, snapshot, raster, hide, and close visual lifecycle policy."""

    def __init__(
        self,
        *,
        visual_style: PromptReorderVisualStyle,
        animation: PromptReorderAnimationPresentationOwner,
        preview_paint_snapshots: PromptReorderPreviewPaintSnapshotOwner,
        preview_visuals: PromptReorderPreviewVisualOwner,
        raster: PromptReorderRasterPublicationOwner,
        live_visuals: PromptReorderLiveVisualOwner,
        refresh_identity: PromptReorderRefreshIdentityOwner,
        render: PromptReorderRenderPublicationOwner,
        pointer_regions: PromptReorderPointerRegionVisualOwner,
        drag_proxy: PromptReorderDragProxyVisualOwner,
        refresh_geometry: Callable[[str], None],
    ) -> None:
        """Store the visual owners participating in cold lifecycle transitions."""

        self._visual_style = visual_style
        self._animation = animation
        self._preview_paint_snapshots = preview_paint_snapshots
        self._preview_visuals = preview_visuals
        self._raster = raster
        self._live_visuals = live_visuals
        self._refresh_identity = refresh_identity
        self._render = render
        self._pointer_regions = pointer_regions
        self._drag_proxy = drag_proxy
        self._refresh_geometry = refresh_geometry
        self._applying_theme = False

    @property
    def visual_style(self) -> PromptReorderVisualStyle:
        """Return the immutable style used by the current visual generation."""

        return self._visual_style

    def clear_snapshots(self, *, reason: str) -> None:
        """Clear all cached visual state before one replacement generation."""

        self._animation.settle(reason=f"{reason}_snapshot_clear")
        self._preview_paint_snapshots.clear()
        self._preview_visuals.clear()
        self._raster.clear()
        self._live_visuals.invalidate()
        self._refresh_identity.invalidate_refresh()
        self._animation.bump_raster_generation()
        self._render.clear()

    def apply_current_theme_style(self) -> None:
        """Replace only the palette-derived style used by later prepared frames."""

        if self._applying_theme:
            return
        self._applying_theme = True
        try:
            visual_style = PromptReorderVisualStyle.from_current_theme()
            self._visual_style = visual_style
            self._pointer_regions.set_visual_style(visual_style)
            self._render.set_visual_style(visual_style)
        finally:
            self._applying_theme = False

    def refresh_theme(self, request: PromptReorderThemeRefreshRequest) -> None:
        """Replace style-dependent visual state after one Qt theme or font event."""

        if self._applying_theme:
            return
        self._applying_theme = True
        try:
            self._animation.settle(reason="theme_or_font_change")
            self.clear_snapshots(reason="theme_or_font_change")
            self._drag_proxy.refresh_font()
            visual_style = PromptReorderVisualStyle.from_current_theme()
            self._visual_style = visual_style
            self._pointer_regions.set_visual_style(visual_style)
            self._render.set_visual_style(visual_style)
            segment = request.dragged_segment
            if request.has_document and segment is not None:
                self._drag_proxy.ensure_segment_render_state(
                    segment=segment,
                    source_revision=request.source_revision,
                    visual_style=visual_style,
                    interaction=request.gesture,
                    gesture_id=request.gesture_id,
                    event_id=request.event_id,
                )
            if request.has_document:
                self._refresh_geometry("theme_change")
        finally:
            self._applying_theme = False

    def hide(self) -> None:
        """Settle and clear visible reorder chrome before Qt hides the shell."""

        self._animation.settle(reason="overlay_hide")
        self.clear_snapshots(reason="overlay_hide")

    def close(self) -> None:
        """Settle visual state and dispose the drag proxy before Qt teardown."""

        self._animation.settle(reason="overlay_close")
        self.clear_snapshots(reason="overlay_close")
        self._drag_proxy.close()

    def publish_warmed_rasters(self, *, overlay_visible: bool) -> None:
        """Publish an idle raster batch only while the overlay remains visible."""

        if overlay_visible:
            self._render.sync(reason="raster_warm_batch")


__all__ = [
    "PromptReorderOverlayVisualLifecycleOwner",
    "PromptReorderThemeRefreshRequest",
]
