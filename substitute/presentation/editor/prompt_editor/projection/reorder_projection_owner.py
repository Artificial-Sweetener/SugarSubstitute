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

"""Own reorder preview projection, geometry, and paint snapshot coordination."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.reorder.views import PromptReorderLayoutView

from ..lora_thumbnail_cache import PromptLoraThumbnailCache
from .applicator import PromptProjectionApplicator
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .frame_state import PromptProjectionEditorState
from .observability import (
    log_reorder_cursor_geometry_query,
    log_reorder_drag_event,
    log_reorder_drag_timing,
    log_reorder_range_geometry_query,
    reorder_drag_started_at,
)
from .prepared_frame import PromptProjectionPreparedFrame
from .reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .reorder_geometry_cache_keys import ReorderGeometrySnapshot
from .reorder_geometry_owner import (
    PromptReorderGeometryEnvironment,
    PromptReorderGeometryOwner,
)
from .reorder_paint_snapshot_cache_owner import PromptReorderPaintSnapshotCacheOwner
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementId,
    PromptReorderPlacementSnapshot,
    placement_for_drag_rect,
)
from .reorder_preview import PromptReorderPreviewState
from .reorder_preview_projection_contracts import PromptReorderPreviewProjectionContext
from .reorder_preview_projection_owner import (
    PromptReorderPreviewProjectionOwner,
)
from .reorder_surface_visual_state import (
    PromptReorderSurfaceVisualContext,
)
from .reorder_surface_presentation_owner import PromptReorderSurfacePresentationOwner
from .reorder_visual_snapshot import PromptReorderProjectionPaintSnapshot
from .theme import semantic_palette_from_theme

_SLOW_REORDER_PROJECTION_LAYOUT_MS = 8.0


class PromptReorderProjectionOwner:
    """Coordinate every reorder projection view over one prepared surface state."""

    def __init__(
        self,
        *,
        surface: QWidget,
        viewport: QWidget,
        applicator: PromptProjectionApplicator,
        thumbnail_cache: PromptLoraThumbnailCache,
        editor_state: PromptProjectionEditorState,
        layout: PromptLayoutEditToFrameCoordinator,
        layout_width: Callable[[], float],
        scroll_offset: Callable[[], float],
        flush_pending_projection: Callable[[str], None],
        synchronize_layout: Callable[[], None],
        publish_render_frame: Callable[[], None],
        request_update: Callable[[], None],
    ) -> None:
        """Bind projection sources and the mounted effects of reorder publication."""

        self._surface = surface
        self._viewport = viewport
        self._editor_state = editor_state
        self._layout = layout
        self._layout_width = layout_width
        self._scroll_offset = scroll_offset
        self._flush_pending_projection = flush_pending_projection
        self._synchronize_layout = synchronize_layout
        self._request_update = request_update
        self._preview = PromptReorderPreviewProjectionOwner(
            projection_applicator=applicator,
            thumbnail_cache=thumbnail_cache,
        )
        self._geometry = PromptReorderGeometryOwner(
            environment=self._geometry_environment,
            preview_projection=self._preview,
        )
        self._paint_snapshots = PromptReorderPaintSnapshotCacheOwner(
            surface=surface,
            viewport=viewport,
            editor_state=editor_state,
            scroll_offset=scroll_offset,
        )
        self._presentation = PromptReorderSurfacePresentationOwner(
            context=self.surface_visual_context,
            preview_visible=lambda: (
                self._preview.preview_state is not None
                and self._preview.preview_frame is not None
            ),
            publish_render_frame=publish_render_frame,
            request_update=request_update,
        )

    @property
    def preview(self) -> PromptReorderPreviewProjectionOwner:
        """Return the preview-frame owner consumed by render synchronization."""

        return self._preview

    @property
    def geometry_owner(self) -> PromptReorderGeometryOwner:
        """Return cached reorder geometry for overlay composition."""

        return self._geometry

    @property
    def presentation(self) -> PromptReorderSurfacePresentationOwner:
        """Return mounted reorder chrome and suppression presentation."""

        return self._presentation

    @property
    def active_frame(self) -> PromptProjectionPreparedFrame:
        """Return the geometry-bearing preview or committed frame."""

        return self._preview.preview_frame or self._layout.frame

    def is_active(self) -> bool:
        """Return whether a reorder preview currently replaces live projection."""

        return self._preview.is_active()

    def set_preview_state(
        self, preview_state: PromptReorderPreviewState | None
    ) -> None:
        """Replace the active preview and synchronize every dependent geometry owner."""

        started_at = reorder_drag_started_at()
        if preview_state is None:
            self._paint_snapshots.clear_preview()
            self._presentation.clear_before_preview_end()
        self._flush_pending_projection("set_reorder_preview_state")
        invalidation = self._preview.set_preview_state(
            preview_state,
            context=PromptReorderPreviewProjectionContext.from_preview_state(
                preview_state,
                source_revision=self._editor_state.source.source_revision,
                layout_width=self._layout_width(),
                viewport_width=self._viewport.width(),
            ),
            font=self._surface.font(),
            palette=self._surface.palette(),
            semantic_palette=semantic_palette_from_theme(),
            live_projection_document=self._editor_state.projection.document,
            live_projection_frame=self._layout.frame,
        )
        if invalidation.clear_all_geometry_reason is not None:
            self.clear_preview_geometry(reason=invalidation.clear_all_geometry_reason)
        if invalidation.clear_base_drag_geometry_reason is not None:
            self.clear_base_drag_geometry(
                reason=invalidation.clear_base_drag_geometry_reason
            )
        self._synchronize_layout()
        self._request_update()
        log_reorder_drag_timing(
            "surface.set_reorder_preview_state",
            started_at=started_at,
            gesture_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_gesture_id
            ),
            event_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_event_id
            ),
            reason=(
                "" if preview_state is None else preview_state.instrumentation_reason
            ),
            has_preview_state=preview_state is not None,
            has_base_drag=(
                False
                if preview_state is None
                else preview_state.base_drag_snapshot is not None
            ),
            dragged_chip_index=(
                None if preview_state is None else preview_state.dragged_chip_index
            ),
            ordered_count=(
                0 if preview_state is None else len(preview_state.ordered_chip_indices)
            ),
        )

    def clear_preview_state(self) -> None:
        """Clear the active preview and resume live projection painting."""

        self.set_preview_state(None)

    def reset_cache_counters(self) -> None:
        """Reset per-gesture projection, geometry, and paint-cache counters."""

        self._geometry.reset_counters()
        self._preview.reset_counters()
        self._paint_snapshots.reset_counters()

    def cache_counters(self) -> dict[str, object]:
        """Return the complete stable cache instrumentation schema."""

        return {
            **self._geometry.counters(),
            **self._preview.counters(),
            **self._paint_snapshots.counters(),
        }

    def clear_preview_geometry(self, *, reason: str) -> None:
        """Invalidate preview and stable drag-base geometry caches."""

        self._geometry.clear_base_drag(reason=reason)
        self._geometry.clear_preview(reason=reason)

    def clear_projection_and_geometry(self, *, reason: str) -> None:
        """Invalidate preview projection and every metric-dependent geometry cache."""

        self._preview.clear_projection_cache(reason=reason)
        self._geometry.clear_live(reason=reason)
        self.clear_preview_geometry(reason=reason)

    def clear_base_drag_geometry(self, *, reason: str) -> None:
        """Invalidate stable drag-base chip and placement geometry."""

        self._geometry.clear_base_drag(reason=reason)

    def clear_preview_chip_geometry(self, *, reason: str) -> None:
        """Invalidate cached preview chip geometry snapshots."""

        self._geometry.clear_preview(reason=reason)

    def clear_for_source_change(self) -> None:
        """Discard reorder state whose source revision no longer exists."""

        if self._preview.preview_state is not None:
            self.clear_projection_and_geometry(reason="source_changed")

    def synchronize_geometry_inputs(self) -> None:
        """Rebuild active preview layout only when mounted geometry inputs changed."""

        if self._preview.preview_state is None:
            return
        layout_width = self._layout_width()
        font = self._surface.font()
        if self._preview.geometry_inputs_match(layout_width=layout_width, font=font):
            return
        invalidation = self._preview.rebuild_geometry_inputs(
            source_revision=self._editor_state.source.source_revision,
            layout_width=layout_width,
            viewport_width=self._viewport.width(),
            font=font,
            palette=self._surface.palette(),
            semantic_palette=semantic_palette_from_theme(),
            live_projection_document=self._editor_state.projection.document,
            live_projection_frame=self._layout.frame,
        )
        if invalidation.clear_base_drag_geometry_reason is not None:
            self.clear_base_drag_geometry(
                reason=invalidation.clear_base_drag_geometry_reason
            )

    def preview_fragments(self, *, start: int, end: int) -> tuple[QRectF, ...]:
        """Return wrapped preview fragments for one raw preview source range."""

        if self._preview.preview_frame is None:
            return ()
        started_at = reorder_drag_started_at()
        self._flush_pending_projection("reorder_preview_fragments")
        fragments = self._preview.preview_fragments(
            start=start,
            end=end,
            viewport_rect=QRectF(self._viewport.rect()),
            scroll_offset=self._scroll_offset(),
        )
        log_reorder_range_geometry_query(
            "surface.reorder_preview_fragments",
            started_at=started_at,
            preview_state=self._preview.preview_state,
            start=start,
            end=end,
            fragment_count=len(fragments),
        )
        return fragments

    def live_chip_geometry_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> PromptReorderChipGeometrySnapshot:
        """Return cached live chip geometry for one reorder layout view."""

        return self._geometry.live_chip_snapshot(
            layout_view=layout_view,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )

    def preview_chip_geometry_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return cached preview chip geometry for one reorder snapshot."""

        return self._geometry.preview_chip_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def live_chip_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned live paint snapshots for visible chips."""

        self._flush_pending_projection("reorder_live_chip_visuals")
        return self._paint_snapshots.live_snapshots(
            projection_frame=self._layout.frame,
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
        )

    def preview_chip_paint_snapshots(
        self,
        *,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
        chip_indices: frozenset[int] | None = None,
    ) -> dict[int, PromptReorderProjectionPaintSnapshot]:
        """Return projection-owned preview paint snapshots for visible chips."""

        preview_frame = self._preview.preview_frame
        if preview_frame is None:
            return {}
        self._flush_pending_projection("reorder_preview_chip_visuals")
        return self._paint_snapshots.preview_snapshots(
            projection_frame=preview_frame,
            chip_geometry_snapshot=chip_geometry_snapshot,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            preview_generation=self.preview_generation(),
            chip_indices=chip_indices,
        )

    def preview_generation(self) -> int | None:
        """Return the active preview identity used by visual snapshots."""

        preview_state = self._preview.preview_state
        if preview_state is None:
            return None
        return id(preview_state.preview_snapshot)

    def preview_cursor_rect(self, position: int) -> QRectF:
        """Return the preview caret rectangle for one source position."""

        if (
            self._preview.preview_frame is None
            or self._preview.preview_document is None
        ):
            return QRectF()
        started_at = reorder_drag_started_at()
        self._flush_pending_projection("reorder_preview_cursor_rect")
        cursor_rect = self._preview.preview_cursor_rect(
            position=position,
            scroll_offset=self._scroll_offset(),
        )
        log_reorder_cursor_geometry_query(
            "surface.reorder_preview_cursor_rect",
            started_at=started_at,
            preview_state=self._preview.preview_state,
            position=position,
            cursor_rect=cursor_rect,
        )
        return cursor_rect

    def base_drag_fragments(self, *, start: int, end: int) -> tuple[QRectF, ...]:
        """Return wrapped fragments from the stable drag-base frame."""

        if self._preview.base_drag_frame is None:
            return ()
        started_at = reorder_drag_started_at()
        fragments = self._preview.base_drag_fragments(
            start=start,
            end=end,
            viewport_rect=QRectF(self._viewport.rect()),
            scroll_offset=self._scroll_offset(),
        )
        log_reorder_range_geometry_query(
            "surface.reorder_base_drag_fragments",
            started_at=started_at,
            preview_state=self._preview.preview_state,
            start=start,
            end=end,
            fragment_count=len(fragments),
        )
        return fragments

    def base_drag_chip_geometry_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return cached chip geometry from the stable drag-base frame."""

        return self._geometry.base_drag_chip_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def base_drag_cursor_rect(self, position: int) -> QRectF:
        """Return the stable drag-base caret rectangle for one source position."""

        if (
            self._preview.base_drag_frame is None
            or self._preview.base_drag_document is None
        ):
            return QRectF()
        started_at = reorder_drag_started_at()
        cursor_rect = self._preview.base_drag_cursor_rect(
            position=position,
            scroll_offset=self._scroll_offset(),
        )
        log_reorder_cursor_geometry_query(
            "surface.reorder_base_drag_cursor_rect",
            started_at=started_at,
            preview_state=self._preview.preview_state,
            position=position,
            cursor_rect=cursor_rect,
        )
        return cursor_rect

    def base_drag_placement_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderPlacementSnapshot:
        """Return cached placements from the stable drag-base frame."""

        return self._geometry.base_drag_placement_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
        )

    def live_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> PromptReorderPlacementSnapshot:
        """Return cached placements for the committed projection frame."""

        return self._geometry.live_placement_snapshot(
            layout_view=layout_view,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
        )

    def placement_at_rect(
        self,
        drag_rect: QRectF,
        *,
        snapshot: PromptReorderPlacementSnapshot,
        active_placement_id: PromptReorderPlacementId | None,
    ) -> PromptReorderPlacementGeometry | None:
        """Return the projection-owned placement selected by one drag rectangle."""

        preview_state = self._preview.preview_state
        started_at = reorder_drag_started_at()
        placement = placement_for_drag_rect(
            snapshot,
            drag_rect,
            active_placement_id=active_placement_id,
            gesture_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_gesture_id
            ),
            event_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_event_id
            ),
        )
        elapsed_ms = log_reorder_drag_timing(
            "surface.reorder_placement_at_rect",
            started_at=started_at,
            gesture_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_gesture_id
            ),
            event_id=(
                None
                if preview_state is None
                else preview_state.instrumentation_event_id
            ),
            placement_count=len(snapshot.placements),
            selected=placement is not None,
        )
        if elapsed_ms >= _SLOW_REORDER_PROJECTION_LAYOUT_MS:
            log_reorder_drag_event(
                "slow.placement_hit_test",
                gesture_id=(
                    None
                    if preview_state is None
                    else preview_state.instrumentation_gesture_id
                ),
                event_id=(
                    None
                    if preview_state is None
                    else preview_state.instrumentation_event_id
                ),
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
                placement_count=len(snapshot.placements),
                selected=placement is not None,
            )
        return placement

    def surface_visual_context(self) -> PromptReorderSurfaceVisualContext:
        """Return the exact projection identity receiving reorder visuals."""

        return PromptReorderSurfaceVisualContext(
            source_revision=self._editor_state.source.source_revision,
            viewport_rect=self._viewport.rect(),
            scroll_offset=int(round(self._scroll_offset())),
            preview_generation=self.preview_generation(),
        )

    def _geometry_environment(self, reason: str) -> PromptReorderGeometryEnvironment:
        """Publish one coherent live frame and viewport geometry environment."""

        if reason:
            self._flush_pending_projection(reason)
        return PromptReorderGeometryEnvironment(
            live_source_text=self._editor_state.projection_semantic.document.source_text,
            live_frame=self._layout.frame,
            viewport_rect=QRectF(self._viewport.rect()),
            scroll_offset=self._scroll_offset(),
            layout_width=self._layout_width(),
        )


__all__ = ["PromptReorderProjectionOwner"]
