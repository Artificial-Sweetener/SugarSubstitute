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

"""Own bounded reorder refresh identity and its session-scoped cache."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QRect

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.application.prompt_editor.reorder.views import PromptReorderDropTarget

from ..projection.reorder_interaction_geometry_identity import (
    reorder_layout_view_key,
    reorder_preview_snapshot_key,
)
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_state import (
    PromptReorderOverlayPositionGeometryKey,
    PromptReorderOverlayRefreshGeometryKey,
    reorder_live_visual_geometry_key_from_fingerprint,
    reorder_overlay_refresh_geometry_key_from_fingerprint,
    reorder_source_fingerprint,
)

_EMPTY_SOURCE_FINGERPRINT = reorder_source_fingerprint("")


def reorder_refresh_event_name(
    *,
    live_changed: bool,
    preview_changed: bool,
    proxy_changed: bool,
) -> str:
    """Return the most specific event for completed refresh work."""

    if live_changed and preview_changed:
        return "overlay.refresh_geometry.full"
    if preview_changed:
        return "overlay.refresh_geometry.preview_only"
    if live_changed:
        return "overlay.refresh_geometry.live_only"
    if proxy_changed:
        return "overlay.refresh_geometry.proxy_only"
    return "overlay.refresh_geometry.skip_unchanged"


class PromptReorderRefreshIdentityOwner:
    """Cache session source identity and authoritative refresh comparisons."""

    def __init__(self) -> None:
        """Initialize an empty session with no published geometry identity."""

        self._source_fingerprint = _EMPTY_SOURCE_FINGERPRINT
        self._last_position_key: PromptReorderOverlayPositionGeometryKey | None = None
        self._last_refresh_key: PromptReorderOverlayRefreshGeometryKey | None = None

    @property
    def previous_refresh_key(self) -> PromptReorderOverlayRefreshGeometryKey | None:
        """Return the last completely published refresh identity."""

        return self._last_refresh_key

    def begin_session(self, source_text: str) -> None:
        """Fingerprint source once and invalidate every prior session identity."""

        self._source_fingerprint = reorder_source_fingerprint(source_text)
        self._last_position_key = None
        self._last_refresh_key = None

    def invalidate_refresh(self) -> None:
        """Force broad refresh work without discarding position identity."""

        self._last_refresh_key = None

    def position_changed(
        self,
        position_key: PromptReorderOverlayPositionGeometryKey,
    ) -> bool:
        """Return whether positioning differs from the last complete publication."""

        return position_key != self._last_position_key

    def build_refresh_key(
        self,
        *,
        position_key: PromptReorderOverlayPositionGeometryKey,
        segments_by_index: Mapping[int, PromptReorderChipView],
        content_rect: QRect,
        geometry_state: PromptReorderInteractionGeometryState,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
    ) -> PromptReorderOverlayRefreshGeometryKey:
        """Build one refresh key without rescanning session source text."""

        live_geometry_key = reorder_live_visual_geometry_key_from_fingerprint(
            source_fingerprint=self._source_fingerprint,
            segment_ranges=tuple(
                sorted(
                    (
                        segment.index,
                        segment.selection_start,
                        segment.selection_end,
                    )
                    for segment in segments_by_index.values()
                )
            ),
            content_left=content_rect.left(),
            content_top=content_rect.top(),
            content_width=content_rect.width(),
            scroll_offset=position_key.scroll_offset,
        )
        return reorder_overlay_refresh_geometry_key_from_fingerprint(
            position_key=position_key,
            source_fingerprint=self._source_fingerprint,
            live_geometry_key=live_geometry_key,
            current_layout_key=reorder_layout_view_key(
                geometry_state.current_layout_view
            ),
            preview_layout_key=reorder_layout_view_key(
                geometry_state.preview_layout_view
            ),
            base_drag_layout_key=reorder_layout_view_key(
                geometry_state.base_drag_layout_view
            ),
            preview_snapshot_key=reorder_preview_snapshot_key(
                geometry_state.preview_snapshot
            ),
            base_drag_snapshot_key=reorder_preview_snapshot_key(
                geometry_state.base_drag_snapshot
            ),
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
        )

    def record_publication(
        self,
        *,
        position_key: PromptReorderOverlayPositionGeometryKey,
        refresh_key: PromptReorderOverlayRefreshGeometryKey,
    ) -> None:
        """Publish position and broad refresh identities atomically."""

        self._last_position_key = position_key
        self._last_refresh_key = refresh_key
