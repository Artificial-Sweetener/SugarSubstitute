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

"""Verify atomic held-drag intent and landing-shadow context ownership."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QPointF, QRect, QRectF, QSize

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_held_drag_context import (
    PromptReorderHeldDragContextOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_models import (
    PromptReorderHeldShadowCaptureInput,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_regions import (
    PromptReorderPointerRegion,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


class _Geometry:
    """Expose empty immutable base-drag geometry."""

    def __init__(self) -> None:
        """Initialize lifecycle counting."""

        self.clear_count = 0
        self.preserve_preview = False

    @property
    def state(self) -> PromptReorderInteractionGeometryState:
        """Return an empty geometry publication."""

        return PromptReorderInteractionGeometryState()

    def clear_drag_context(self, *, preserve_preview: bool = False) -> None:
        """Record complete base-drag cleanup."""

        self.clear_count += 1
        self.preserve_preview = preserve_preview


class _LiveVisuals:
    """Expose one fallback visual and no projection geometry."""

    def __init__(self, visual: PromptChipVisual) -> None:
        """Store one visual publication."""

        self._visual = visual

    @property
    def visuals_by_index(self) -> Mapping[int, PromptChipVisual]:
        """Return one prepared visual."""

        return {3: self._visual}

    @property
    def chip_geometry(self) -> PromptReorderChipGeometrySnapshot | None:
        """Return no projection geometry for the focused fallback test."""

        return None


class _Regions:
    """Expose a replaceable logical region mapping."""

    def __init__(self, region: PromptReorderPointerRegion | None) -> None:
        """Store the optional materialized region."""

        self._region = region

    @property
    def regions_by_index(self) -> Mapping[int, PromptReorderPointerRegion]:
        """Return the current region mapping."""

        return {} if self._region is None else {3: self._region}


class _Proxy:
    """Expose deterministic prepared proxy dimensions."""

    @property
    def size(self) -> QSize:
        """Return the current proxy size."""

        return QSize(70, 28)

    @property
    def size_hint(self) -> QSize:
        """Return the preferred proxy size."""

        return QSize(74, 30)


class _Landing:
    """Record retained held-shadow capture inputs."""

    def __init__(self) -> None:
        """Initialize no captures."""

        self.captures: list[PromptReorderHeldShadowCaptureInput] = []
        self.clear_count = 0

    def capture_held_shadow(
        self,
        capture: PromptReorderHeldShadowCaptureInput,
    ) -> None:
        """Record one capture."""

        self.captures.append(capture)

    def clear_held_shadow(self) -> None:
        """Record retained-shadow cleanup."""

        self.clear_count += 1


class _LandingPreview:
    """Record cache cleanup coupled to held-shadow disposal."""

    def __init__(self) -> None:
        """Initialize no cleanup observations."""

        self.clear_count = 0

    def clear_held_shadow(self) -> None:
        """Record landing-paint cache invalidation."""

        self.clear_count += 1


def test_held_drag_context_prefers_materialized_region_and_captures_shadow() -> None:
    """Drag start must publish matching intent and landing-shadow geometry."""

    gesture = PromptReorderGestureController()
    visual = _visual()
    region = PromptReorderPointerRegion(_segment())
    region.set_geometry(QRect(20, 10, 64, 24))
    landing = _Landing()
    preview = _LandingPreview()
    owner = _owner(
        gesture=gesture,
        visual=visual,
        region=region,
        landing_session=landing,
        landing_preview=preview,
    )

    owner.capture(
        3,
        local_pointer=QPointF(36.0, 18.0),
        gesture_id=7,
        event_id=9,
    )

    assert gesture.state.drag_intent_size is not None
    assert gesture.state.drag_intent_size.toSize() == QSize(64, 24)
    assert gesture.state.drag_grab_offset == QPointF(16.0, 8.0)
    capture = landing.captures[0]
    assert capture.chip_size == QSize(64, 24)
    assert capture.proxy_size == QSize(70, 28)
    assert capture.proxy_size_hint == QSize(74, 30)
    assert capture.live_visual is visual
    assert capture.gesture_id == 7
    assert capture.event_id == 9


def test_held_drag_context_uses_visual_fallback_and_clears_atomically() -> None:
    """Missing viewport region must use prepared visual geometry and clear cleanly."""

    gesture = PromptReorderGestureController()
    visual = _visual()
    geometry = _Geometry()
    landing = _Landing()
    preview = _LandingPreview()
    owner = _owner(
        gesture=gesture,
        visual=visual,
        region=None,
        landing_session=landing,
        landing_preview=preview,
        geometry=geometry,
    )

    owner.capture(
        3,
        local_pointer=QPointF(44.0, 22.0),
        gesture_id=None,
        event_id=None,
    )
    assert gesture.state.drag_intent_size is not None
    assert gesture.state.drag_intent_size.toSize() == visual.hotspot_rect.size()

    owner.clear()

    assert gesture.state.drag_intent_size is None
    assert gesture.state.drag_grab_offset is None
    assert geometry.clear_count == 1
    assert landing.clear_count == 1
    assert preview.clear_count == 1


def test_held_drag_context_completion_retains_committed_preview_geometry() -> None:
    """Successful drops must retire drag facts through the preserving transition."""

    gesture = PromptReorderGestureController()
    geometry = _Geometry()
    landing = _Landing()
    preview = _LandingPreview()
    owner = _owner(
        gesture=gesture,
        visual=_visual(),
        region=None,
        landing_session=landing,
        landing_preview=preview,
        geometry=geometry,
    )

    owner.clear(preserve_preview=True)

    assert geometry.clear_count == 1
    assert geometry.preserve_preview is True
    assert landing.clear_count == 1
    assert preview.clear_count == 1


def _owner(
    *,
    gesture: PromptReorderGestureController,
    visual: PromptChipVisual,
    region: PromptReorderPointerRegion | None,
    landing_session: _Landing,
    landing_preview: _LandingPreview,
    geometry: _Geometry | None = None,
) -> PromptReorderHeldDragContextOwner:
    """Return one held-drag context owner with focused fakes."""

    geometry = _Geometry() if geometry is None else geometry
    live_visuals = _LiveVisuals(visual)
    regions = _Regions(region)
    drag_proxy = _Proxy()
    return PromptReorderHeldDragContextOwner(
        gesture=gesture,
        geometry_state=lambda: geometry.state,
        clear_geometry=lambda preserve_preview: geometry.clear_drag_context(
            preserve_preview=preserve_preview
        ),
        live_visual_facts=lambda: (
            live_visuals.visuals_by_index,
            live_visuals.chip_geometry,
        ),
        regions_by_index=lambda: regions.regions_by_index,
        proxy_sizes=lambda: (drag_proxy.size, drag_proxy.size_hint),
        capture_held_shadow=landing_session.capture_held_shadow,
        clear_held_shadow=landing_session.clear_held_shadow,
        clear_landing_paint=landing_preview.clear_held_shadow,
    )


def _segment() -> PromptReorderChipView:
    """Return one semantic held segment."""

    return PromptReorderChipView(
        index=3,
        partition_index=0,
        text="alpha",
        serialized_text="alpha",
        display_text="alpha",
        display_source_start=0,
        display_source_end=5,
        selection_start=0,
        selection_end=5,
        separator_text_after="",
        has_separator_after=False,
    )


def _visual() -> PromptChipVisual:
    """Return one deterministic fallback held visual."""

    hotspot = QRect(12, 6, 68, 26)
    bubble = QRectF(16.0, 8.0, 60.0, 22.0)
    return PromptChipVisual(
        bubble_rects=(bubble,),
        fragment_union_rect=QRectF(bubble),
        hotspot_rect=hotspot,
        slot_before=QPointF(bubble.left(), bubble.center().y()),
        slot_after=QPointF(bubble.right(), bubble.center().y()),
        marker_height=bubble.height(),
    )
