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

"""Own viewport-driven reorder geometry refresh and frame publication."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRect

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import reorder_drag_started_at
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from ..projection.reorder_state import (
    PromptReorderOverlayRefreshGeometryKey,
    ReorderLiveVisualGeometryKey,
    reorder_overlay_refresh_is_height_only_change,
)
from .reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from .reorder_preview_geometry_refresh_owner import (
    PromptReorderPreviewGeometryRefreshOwner,
)
from .reorder_preview_layout_transition_owner import (
    PromptReorderPreviewLayoutTransitionOwner,
)
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_refresh_identity import (
    PromptReorderRefreshIdentityOwner,
    reorder_refresh_event_name,
)
from .reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from .reorder_viewport_geometry import PromptReorderViewportGeometryOwner
from .reorder_visual_session import PromptReorderVisualSessionOwner

_SLOW_LIVE_VISUALS_MS = 8.0


class PromptReorderViewportFrameRefreshOwner:
    """Route viewport invalidation into the minimum complete reorder frame."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        visual_session: PromptReorderVisualSessionOwner,
        viewport: PromptReorderViewportGeometryOwner,
        refresh_identity: PromptReorderRefreshIdentityOwner,
        live_visuals: PromptReorderLiveVisualOwner,
        preview_visuals: PromptReorderPreviewVisualOwner,
        preview_geometry: PromptReorderPreviewGeometryRefreshOwner,
        preview_layout: PromptReorderPreviewLayoutTransitionOwner,
        pointer_region_visuals: PromptReorderPointerRegionVisualOwner,
        drag_proxy: PromptReorderDragProxyVisualOwner,
        animation: PromptReorderAnimationPresentationOwner,
        render: PromptReorderRenderPublicationOwner,
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        overlay_geometry: Callable[[], QRect],
        set_overlay_geometry: Callable[[QRect], None],
    ) -> None:
        """Bind geometry publications and exact overlay-rectangle adapters."""

        self._geometry = geometry
        self._gesture = gesture
        self._visual_session = visual_session
        self._viewport = viewport
        self._refresh_identity = refresh_identity
        self._live_visuals = live_visuals
        self._preview_visuals = preview_visuals
        self._preview_geometry = preview_geometry
        self._preview_layout = preview_layout
        self._pointer_region_visuals = pointer_region_visuals
        self._drag_proxy = drag_proxy
        self._animation = animation
        self._render = render
        self._metrics = metrics
        self._diagnostics = diagnostics
        self._overlay_geometry = overlay_geometry
        self._set_overlay_geometry = set_overlay_geometry

    def refresh(self, *, reason: str) -> None:
        """Route one invalidation reason to minimal prepared-frame work."""

        started_at = reorder_drag_started_at()
        work_unit_id = self._metrics.next_work_unit()
        self._metrics.record_refresh_work_unit()
        previous_key = self._refresh_identity.previous_refresh_key
        previous_geometry = QRect(self._overlay_geometry())
        previous_content_rect = self._viewport.published_content_rect
        self._set_overlay_geometry(self._viewport.viewport_rect())
        viewport = self._viewport.capture()
        overlay_rect_changed = (
            previous_geometry != self._overlay_geometry()
            or previous_content_rect != viewport.content_rect
        )
        next_key = self._refresh_identity.build_refresh_key(
            position_key=viewport.position_key,
            segments_by_index=self._visual_session.segments_by_index,
            content_rect=viewport.content_rect,
            geometry_state=self._geometry.state,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
        )
        drag_active = self._gesture.state.dragged_segment_index is not None
        key_changed = previous_key != next_key
        preview_snapshot_changed = (
            previous_key is None
            or previous_key.preview_snapshot_key != next_key.preview_snapshot_key
            or previous_key.preview_layout_key != next_key.preview_layout_key
            or previous_key.active_target != next_key.active_target
        )
        height_only_geometry_change = (
            previous_key is not None
            and reorder_overlay_refresh_is_height_only_change(previous_key, next_key)
        )
        if (
            key_changed
            and not preview_snapshot_changed
            and not height_only_geometry_change
        ):
            self._animation.settle(reason=f"geometry_refresh:{reason}")
        self._log_request(
            reason=reason,
            work_unit_id=work_unit_id,
            drag_active=drag_active,
            key_changed=key_changed,
            preview_snapshot_changed=preview_snapshot_changed,
            previous_key=previous_key,
            next_key=next_key,
        )
        if previous_key == next_key and self._live_visuals.visuals_by_index:
            self._record_unchanged(
                started_at=started_at,
                work_unit_id=work_unit_id,
                reason=reason,
                drag_active=drag_active,
                overlay_rect_changed=overlay_rect_changed,
            )
            return
        if self._metrics.pointer_loop_active:
            self._diagnostics.record_pointer_unexpected_work(
                "full_refresh",
                reason=reason,
            )
        live_changed = self._refresh_live_geometry(
            geometry_key=next_key.live_geometry_key,
            reason=reason,
        )
        preview_changed = self._refresh_preview_geometry(
            reason=reason,
            preserve_animation=height_only_geometry_change,
        )
        chip_geometry_changed = self._pointer_region_visuals.sync_geometry_if_needed(
            reason=reason
        )
        proxy_changed = self._sync_drag_proxy_geometry(reason=reason)
        self._refresh_identity.record_publication(
            position_key=viewport.position_key,
            refresh_key=next_key,
        )
        if (
            key_changed
            or live_changed
            or preview_changed
            or chip_geometry_changed
            or proxy_changed
        ):
            self._render.sync(reason=reason)
            if self._metrics.pointer_loop_active:
                self._diagnostics.record_pointer_unexpected_work(
                    "paint_request",
                    reason=reason,
                )
        content_rect = viewport.content_rect
        self._diagnostics.log_timing(
            reorder_refresh_event_name(
                live_changed=live_changed,
                preview_changed=preview_changed,
                proxy_changed=proxy_changed,
            ),
            started_at=started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            content_width=content_rect.width(),
            content_height=content_rect.height(),
            visual_count=len(self._live_visuals.visuals_by_index),
            preview_visual_count=len(self._preview_visuals.visuals_by_index),
            lane_count=len(self._geometry.state.drop_target_lanes),
            live_changed=live_changed,
            preview_changed=preview_changed,
            chip_geometry_changed=chip_geometry_changed,
            proxy_changed=proxy_changed,
        )
        self._diagnostics.log_timing(
            "overlay.refresh_geometry",
            started_at=started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            skipped=False,
            content_width=content_rect.width(),
            content_height=content_rect.height(),
            visual_count=len(self._live_visuals.visuals_by_index),
            preview_visual_count=len(self._preview_visuals.visuals_by_index),
            lane_count=len(self._geometry.state.drop_target_lanes),
        )

    def needs_position_refresh(self, *, reason: str) -> bool:
        """Return whether viewport positioning changed since publication."""

        work_unit_id = self._metrics.next_work_unit()
        next_key = self._viewport.position_geometry_key()
        changed = self._refresh_identity.position_changed(next_key)
        drag_active = self._gesture.state.dragged_segment_index is not None
        self._diagnostics.log_event(
            "overlay.position_refresh.requested",
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            position_key_changed=changed,
            viewport_width=next_key.viewport_width,
            viewport_height=next_key.viewport_height,
            scroll_offset=next_key.scroll_offset,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
        )
        self._metrics.record_position_refresh(changed=changed)
        self._diagnostics.log_event(
            (
                "overlay.position_refresh.ran"
                if changed
                else "overlay.position_refresh.skip_unchanged"
            ),
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            position_key_changed=changed,
        )
        return changed

    def sync_overlay_rect(self) -> bool:
        """Align the passive overlay with one coherent viewport capture."""

        previous_geometry = QRect(self._overlay_geometry())
        previous_content_rect = self._viewport.published_content_rect
        self._set_overlay_geometry(self._viewport.viewport_rect())
        viewport = self._viewport.capture()
        return (
            previous_geometry != self._overlay_geometry()
            or previous_content_rect != viewport.content_rect
        )

    def _refresh_live_geometry(
        self,
        *,
        geometry_key: ReorderLiveVisualGeometryKey,
        reason: str,
    ) -> bool:
        """Refresh live chip geometry only when its identity changed."""

        return self._live_visuals.prepare(
            geometry_key=geometry_key,
            segments_by_index=self._visual_session.segments_by_index,
            reason=reason,
        ).rebuilt

    def _refresh_preview_geometry(
        self,
        *,
        reason: str,
        preserve_animation: bool,
    ) -> bool:
        """Refresh preview geometry while preserving valid height-only animation."""

        if not preserve_animation:
            self._animation.settle(reason=f"{reason}_preview_geometry_refresh")
        self._preview_layout.update()
        rebuilt = self._preview_geometry.refresh()
        if rebuilt and self._metrics.pointer_loop_active:
            self._diagnostics.record_pointer_unexpected_work(
                "preview_rebuild",
                reason=reason,
            )
        return rebuilt

    def _sync_drag_proxy_geometry(self, *, reason: str) -> bool:
        """Move the proxy from the retained pointer without preview work."""

        position = self._gesture.state.last_drag_global_position
        if position is None:
            return False
        changed = self._drag_proxy.sync_position_if_needed(
            position,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
        )
        self._diagnostics.log_event(
            "overlay.refresh_geometry.proxy_only",
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            reason=reason,
            proxy_changed=changed,
        )
        return changed

    def _log_request(
        self,
        *,
        reason: str,
        work_unit_id: int,
        drag_active: bool,
        key_changed: bool,
        preview_snapshot_changed: bool,
        previous_key: PromptReorderOverlayRefreshGeometryKey | None,
        next_key: PromptReorderOverlayRefreshGeometryKey,
    ) -> None:
        """Record bounded refresh classification from authoritative identities."""

        state = self._geometry.state
        self._diagnostics.log_event(
            "overlay.refresh_geometry.requested",
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            has_preview_snapshot=state.preview_snapshot is not None,
            has_base_drag_snapshot=state.base_drag_snapshot is not None,
            geometry_key_changed=key_changed,
            preview_key_changed=preview_snapshot_changed,
            live_key_changed=(
                previous_key is None
                or previous_key.live_geometry_key != next_key.live_geometry_key
            ),
            viewport_width=next_key.viewport_width,
            viewport_height=next_key.viewport_height,
            scroll_offset=next_key.scroll_offset,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
        )

    def _record_unchanged(
        self,
        *,
        started_at: float,
        work_unit_id: int,
        reason: str,
        drag_active: bool,
        overlay_rect_changed: bool,
    ) -> None:
        """Record one no-rebuild refresh and its position-only proxy work."""

        self._metrics.record_skipped_refresh()
        proxy_changed = (
            self._sync_drag_proxy_geometry(reason=reason)
            if overlay_rect_changed
            else False
        )
        content_rect = self._viewport.published_content_rect
        elapsed_ms = self._diagnostics.log_timing(
            "overlay.refresh_geometry.skip_unchanged",
            started_at=started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            drag_active=drag_active,
            content_width=content_rect.width(),
            content_height=content_rect.height(),
            visual_count=len(self._live_visuals.visuals_by_index),
            preview_visual_count=len(self._preview_visuals.visuals_by_index),
            lane_count=len(self._geometry.state.drop_target_lanes),
            overlay_rect_changed=overlay_rect_changed,
            proxy_changed=proxy_changed,
        )
        if elapsed_ms >= _SLOW_LIVE_VISUALS_MS:
            self._diagnostics.log_event(
                "budget.position_refresh_exceeded",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                work_unit_id=work_unit_id,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_LIVE_VISUALS_MS:.3f}",
                reason=reason,
                skipped=True,
            )
        self._diagnostics.log_timing(
            "overlay.refresh_geometry",
            started_at=started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            work_unit_id=work_unit_id,
            reason=reason,
            skipped=True,
            skipped_elapsed_ms=f"{elapsed_ms:.3f}",
        )
