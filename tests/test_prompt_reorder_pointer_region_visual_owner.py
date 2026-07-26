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

"""Cover authoritative reorder pointer-region visual synchronization."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.document.views import PromptReorderChipView
from substitute.application.prompt_editor.reorder.views import PromptReorderLayoutView
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_pointer_regions import (
    PromptReorderPointerRegions,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_style import (
    PromptReorderVisualStyle,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_mode import (
    PromptReorderVisualModeOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


class _Geometry:
    """Publish replaceable immutable geometry state."""

    def __init__(self) -> None:
        """Initialize an empty live-mode publication."""

        self.state = PromptReorderInteractionGeometryState()


class _VisualSource:
    """Publish a deterministic visual mapping."""

    def __init__(self, visuals: Mapping[int, PromptChipVisual]) -> None:
        """Store the supplied immutable test mapping."""

        self.visuals_by_index = visuals


class _DragProxy:
    """Count stacking requests without constructing a QWidget proxy."""

    def __init__(self) -> None:
        """Initialize no stacking requests."""

        self.raise_count = 0

    def raise_proxy(self) -> None:
        """Record one stacking request."""

        self.raise_count += 1


def test_pointer_region_visual_owner_positions_live_regions_and_interaction_state() -> (
    None
):
    """One owner should position, expose, and style every live logical region."""

    _ensure_qapp()
    regions = PromptReorderPointerRegions()
    regions.set_segments((_segment(0), _segment(1)))
    gesture = PromptReorderGestureController()
    proxy = _DragProxy()
    owner = _owner(
        regions=regions,
        geometry=_Geometry(),
        gesture=gesture,
        live={0: _visual(10), 1: _visual(90)},
        preview={},
        proxy=proxy,
    )

    owner.sync_geometry()
    gesture.activate_segment(0)
    gesture.set_hovered_segment(0)
    owner.sync_interaction_state()

    assert tuple(regions.regions_by_index) == (0, 1)
    assert regions.regions_by_index[0].rect == QRect(10, 8, 64, 24)
    assert regions.regions_by_index[1].rect == QRect(90, 8, 64, 24)
    assert all(region.visible for region in regions.regions_by_index.values())
    assert regions.regions_by_index[0].active is True
    assert regions.regions_by_index[0].hovered is True
    assert proxy.raise_count == 1


def test_pointer_region_visual_owner_uses_preview_geometry_without_moving_held_region() -> (
    None
):
    """Preview positioning must leave held-chip geometry to the drag proxy."""

    _ensure_qapp()
    regions = PromptReorderPointerRegions()
    regions.set_segments((_segment(0), _segment(1)))
    geometry = _Geometry()
    geometry.state = PromptReorderInteractionGeometryState(
        preview_layout_view=cast(PromptReorderLayoutView, object()),
    )
    gesture = PromptReorderGestureController()
    gesture.begin_pointer_drag(
        segment_index=1,
        global_position=QPoint(120, 20),
    )
    owner = _owner(
        regions=regions,
        geometry=geometry,
        gesture=gesture,
        live={0: _visual(10), 1: _visual(90)},
        preview={0: _visual(30), 1: _visual(130)},
        proxy=_DragProxy(),
    )

    owner.sync_geometry()

    assert regions.regions_by_index[0].rect == QRect(30, 8, 64, 24)
    assert regions.regions_by_index[0].visible is True
    assert regions.regions_by_index[1].rect.isEmpty()


def test_pointer_region_visual_owner_owns_geometry_identity_and_invalidation() -> None:
    """Unchanged geometry should skip all region and stacking work until invalidated."""

    _ensure_qapp()
    regions = PromptReorderPointerRegions()
    regions.set_segments((_segment(0), _segment(1)))
    proxy = _DragProxy()
    owner = _owner(
        regions=regions,
        geometry=_Geometry(),
        gesture=PromptReorderGestureController(),
        live={0: _visual(10), 1: _visual(90)},
        preview={},
        proxy=proxy,
    )

    assert owner.sync_geometry_if_needed(reason="initial") is True
    assert owner.sync_geometry_if_needed(reason="unchanged") is False
    assert proxy.raise_count == 1

    owner.invalidate_geometry()

    assert owner.sync_geometry_if_needed(reason="invalidated") is True
    assert proxy.raise_count == 2


def _owner(
    *,
    regions: PromptReorderPointerRegions,
    geometry: _Geometry,
    gesture: PromptReorderGestureController,
    live: Mapping[int, PromptChipVisual],
    preview: Mapping[int, PromptChipVisual],
    proxy: _DragProxy,
) -> PromptReorderPointerRegionVisualOwner:
    """Return one owner using production diagnostics and visual styling."""

    metrics = PromptReorderInteractionMetricsOwner()
    return PromptReorderPointerRegionVisualOwner(
        regions=regions,
        gesture=gesture,
        visual_mode=PromptReorderVisualModeOwner(
            geometry_state=lambda: geometry.state,
            gesture=gesture,
        ),
        live_visuals=lambda: _VisualSource(live).visuals_by_index,
        preview_visuals=lambda: _VisualSource(preview).visuals_by_index,
        raise_drag_proxy=proxy.raise_proxy,
        metrics=metrics,
        diagnostics=PromptReorderInteractionDiagnosticsOwner(
            telemetry=PromptReorderTelemetry(),
            metrics=metrics,
        ),
        visual_style=PromptReorderVisualStyle.from_current_theme(),
    )


def _segment(index: int) -> PromptReorderChipView:
    """Return one semantic segment for a logical pointer region."""

    start = index * 6
    return PromptReorderChipView(
        index=index,
        partition_index=0,
        text=f"tag{index}",
        serialized_text=f"tag{index}",
        display_text=f"tag{index}",
        display_source_start=start,
        display_source_end=start + 4,
        selection_start=start,
        selection_end=start + 4,
        separator_text_after="",
        has_separator_after=False,
    )


def _visual(left: int) -> PromptChipVisual:
    """Return one deterministic prepared chip visual."""

    hotspot = QRect(left, 8, 64, 24)
    bubble = QRectF(left + 4, 10, 56, 20)
    return PromptChipVisual(
        bubble_rects=(bubble,),
        fragment_union_rect=QRectF(bubble),
        hotspot_rect=hotspot,
        slot_before=QPointF(bubble.left(), bubble.center().y()),
        slot_after=QPointF(bubble.right(), bubble.center().y()),
        marker_height=bubble.height(),
    )


def _ensure_qapp() -> QApplication:
    """Return the shared offscreen Qt application."""

    instance = QApplication.instance()
    if instance is not None:
        return cast(QApplication, instance)
    return QApplication([])
