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

"""Verify complete presentation-session activation ownership for reorder overlays."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_autoscroll import (
    PromptReorderAutoscrollOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drag_proxy_visual_owner import (
    PromptReorderDragProxyVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_drop_commit_diagnostics import (
    PromptReorderDropCommitDiagnostics,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_held_drag_context import (
    PromptReorderHeldDragContextOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_paint import (
    PromptReorderLandingPaintOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_session import (
    PromptReorderLandingSessionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_live_visual_owner import (
    PromptReorderLiveVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_overlay_session_activation import (
    PromptReorderOverlaySessionActivationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_overlay_visual_lifecycle import (
    PromptReorderOverlayVisualLifecycleOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_regions import (
    PromptReorderPointerInput,
    PromptReorderPointerRegions,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_visual_owner import (
    PromptReorderPreviewVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_raster_publication import (
    PromptReorderRasterPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_refresh_identity import (
    PromptReorderRefreshIdentityOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_viewport_frame_refresh import (
    PromptReorderViewportFrameRefreshOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_session import (
    PromptReorderVisualSessionOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)


@dataclass
class _ActivationRecorder:
    """Record every command issued by the activation transaction."""

    calls: list[str] = field(default_factory=list)

    def begin_session(self, source_text: str | None = None) -> None:
        """Record either metric or source-identity session initialization."""

        if source_text is None:
            self.calls.append("metrics.begin")
        else:
            self.calls.append(f"identity.begin:{source_text}")

    def cancel(self, *, reason: str) -> None:
        """Record animation cancellation."""

        self.calls.append(f"animation.cancel:{reason}")

    def clear_snapshots(self, *, reason: str) -> None:
        """Record complete visual generation invalidation."""

        self.calls.append(f"visual.clear:{reason}")

    def hide(self) -> None:
        """Record drag-proxy hiding."""

        self.calls.append("drag_proxy.hide")

    def stop(self) -> None:
        """Record autoscroll shutdown."""

        self.calls.append("autoscroll.stop")

    def clear_pending_invalidation(self) -> None:
        """Record removal of coalesced autoscroll work."""

        self.calls.append("autoscroll.clear_pending")

    def reset(self) -> None:
        """Record pointer input reset."""

        self.calls.append("pointer_input.reset")

    def clear(self) -> None:
        """Record stale visual, region, or diagnostics disposal."""

        self.calls.append("clear")

    def clear_pointer_region_state(self) -> None:
        """Record animation pointer-region release."""

        self.calls.append("animation.clear_regions")

    def clear_held_shadow(self) -> None:
        """Record stale landing feedback removal."""

        self.calls.append("landing.clear_held")

    def invalidate(self) -> None:
        """Record live visual invalidation."""

        self.calls.append("live.invalidate")

    def invalidate_entries(self) -> None:
        """Record stale raster invalidation."""

        self.calls.append("raster.invalidate")

    def set_session(self, *args: object, **kwargs: object) -> None:
        """Record atomic geometry-session replacement."""

        _ = args, kwargs
        self.calls.append("geometry.set_session")

    def clear_preview_target_identity(self) -> None:
        """Record preview-target identity clearing."""

        self.calls.append("geometry.clear_preview_identity")

    def reset_all(self) -> None:
        """Record gesture state reset."""

        self.calls.append("gesture.reset")

    def activate_segment(self, segment_index: int) -> None:
        """Record requested active-chip adoption."""

        self.calls.append(f"gesture.activate:{segment_index}")

    def reset_session_state(self) -> None:
        """Record landing visual session reset."""

        self.calls.append("landing.reset")

    def reset_drag_state(self) -> None:
        """Record replacement of the prior landing paint-cache generation."""

        self.calls.append("landing_preview.reset")

    def invalidate_geometry(self) -> None:
        """Record deferred pointer-region geometry replacement."""

        self.calls.append("pointer_regions.invalidate")

    def set_segments(self, _segments: object) -> None:
        """Record semantic pointer-region replacement."""

        self.calls.append("pointer_regions.set")

    def refresh(self, *, reason: str) -> None:
        """Record first viewport geometry publication."""

        self.calls.append(f"viewport.refresh:{reason}")

    def log_timing(self, _event: str, **_fields: object) -> None:
        """Record the preserved activation timing event."""

        self.calls.append("diagnostics.timing")


def test_activation_owner_replaces_complete_visual_session_in_stable_order() -> None:
    """Activation clears old presentation state before publishing one new session."""

    document_service = PromptDocumentService()
    document = document_service.build_document_view("alpha, beta")
    session = document_service.build_reorder_session_view(document)
    recorder = _ActivationRecorder()
    visual_session = PromptReorderVisualSessionOwner()
    owner = PromptReorderOverlaySessionActivationOwner(
        interaction_metrics=cast(PromptReorderInteractionMetricsOwner, recorder),
        animation=cast(PromptReorderAnimationPresentationOwner, recorder),
        visual_lifecycle=cast(PromptReorderOverlayVisualLifecycleOwner, recorder),
        drag_proxy=cast(PromptReorderDragProxyVisualOwner, recorder),
        autoscroll=cast(PromptReorderAutoscrollOwner, recorder),
        pointer_input=cast(PromptReorderPointerInput, recorder),
        pointer_regions=cast(PromptReorderPointerRegions, recorder),
        preview_visuals=cast(PromptReorderPreviewVisualOwner, recorder),
        landing_session=cast(PromptReorderLandingSessionOwner, recorder),
        landing_preview=cast(PromptReorderLandingPaintOwner, recorder),
        live_visuals=cast(PromptReorderLiveVisualOwner, recorder),
        raster=cast(PromptReorderRasterPublicationOwner, recorder),
        held_drag_context=cast(PromptReorderHeldDragContextOwner, recorder),
        drop_diagnostics=cast(PromptReorderDropCommitDiagnostics, recorder),
        visual_session=visual_session,
        geometry=cast(PromptReorderInteractionGeometry, recorder),
        refresh_identity=cast(PromptReorderRefreshIdentityOwner, recorder),
        gesture=cast(PromptReorderGestureController, recorder),
        pointer_region_visuals=cast(PromptReorderPointerRegionVisualOwner, recorder),
        viewport_refresh=cast(PromptReorderViewportFrameRefreshOwner, recorder),
        diagnostics=cast(PromptReorderInteractionDiagnosticsOwner, recorder),
        lower_view=lambda: recorder.calls.append("view.lower"),
    )

    owner.activate(
        document,
        session.layout_view,
        session.reorder_state,
        chips=session.chips,
        active_chip_index=1,
        source_identity=None,
    )

    assert recorder.calls == [
        "metrics.begin",
        "animation.cancel:set_chips",
        "visual.clear:set_chips",
        "drag_proxy.hide",
        "autoscroll.stop",
        "autoscroll.clear_pending",
        "animation.cancel:delete_existing_chips",
        "pointer_input.reset",
        "clear",
        "animation.clear_regions",
        "clear",
        "landing.clear_held",
        "landing.clear_held",
        "clear",
        "raster.invalidate",
        "clear",
        "clear",
        "geometry.set_session",
        "identity.begin:alpha, beta",
        "geometry.clear_preview_identity",
        "live.invalidate",
        "gesture.reset",
        "gesture.activate:1",
        "landing.reset",
        "landing_preview.reset",
        "pointer_regions.invalidate",
        "pointer_regions.set",
        "pointer_input.reset",
        "view.lower",
        "viewport.refresh:set_chips",
        "diagnostics.timing",
    ]
    assert visual_session.publication.ordered_indices == (0, 1)
