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

"""Verify reorder placement and geometry-cache behavior."""

from __future__ import annotations


from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from tests.presentation.editor.prompt_editor.projection.reorder_surface.support import (
    _build_reorder_preview_state,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)


def test_projection_surface_reorder_placement_uses_chip_visual_vertical_affordance(
    widgets: list[QWidget],
) -> None:
    """Placement hit testing should not misclassify a chip-center drag as a blank row."""

    app = ensure_qapp()
    text = "1girl,\n\numbrella,"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=360,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            text,
            dragged_chip_index=1,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        )
    )
    process_events(app)
    snapshot = surface.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )

    placement = surface.reorder_placement_at_rect(
        QRectF(16.0, 8.0, 126.0, 26.0),
        snapshot=snapshot,
        active_placement_id=None,
    )

    assert placement is not None
    assert placement.target == PromptLineDropTarget(row_index=0, insertion_index=1)


def test_projection_surface_reorder_base_drag_geometry_reuses_stable_cache(
    widgets: list[QWidget],
) -> None:
    """Base-drag chip and placement geometry should reuse stable cached snapshots."""

    app = ensure_qapp()
    text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            text,
            dragged_chip_index=1,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        )
    )
    process_events(app)

    first_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    second_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    first_placement_snapshot = surface.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    second_placement_snapshot = surface.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )

    assert second_chip_snapshot is first_chip_snapshot
    assert second_placement_snapshot is first_placement_snapshot


def test_projection_surface_reorder_base_drag_geometry_cache_invalidates_on_resize(
    widgets: list[QWidget],
) -> None:
    """Viewport changes should invalidate stable base-drag geometry caches."""

    app = ensure_qapp()
    text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            text,
            dragged_chip_index=1,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        )
    )
    process_events(app)
    first_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )

    box.resize(420, box.height())
    process_events(app)
    resized_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )

    assert resized_chip_snapshot is not first_chip_snapshot


def test_projection_surface_reorder_preview_chip_geometry_reuses_target_cache(
    widgets: list[QWidget],
) -> None:
    """Repeated preview geometry for the same target should hit preview cache."""

    app = ensure_qapp()
    text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    preview_state = _build_reorder_preview_state(
        text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    surface.set_reorder_preview_state(preview_state)
    process_events(app)

    first_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    second_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )

    assert second_snapshot is first_snapshot


def test_projection_surface_reorder_preview_chip_geometry_reports_chip_reuse(
    widgets: list[QWidget],
) -> None:
    """Preview geometry summaries should expose chip-level reuse, not only misses."""

    app = ensure_qapp()
    text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=text, width=360)
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    preview_state = _build_reorder_preview_state(
        text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )
    surface.set_reorder_preview_state(preview_state)
    process_events(app)
    surface.reset_reorder_geometry_cache_counters()

    first_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    second_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    counters = surface.reorder_geometry_cache_counters()

    assert second_snapshot is first_snapshot
    assert counters["preview_chip_geometry_reused_chip_count"] == len(
        first_snapshot.geometries_by_chip_index
    )
    assert counters["preview_chip_geometry_rebuilt_chip_count"] == len(
        first_snapshot.geometries_by_chip_index
    )


def test_projection_surface_reorder_placement_exposes_wrapped_visual_line_targets(
    widgets: list[QWidget],
) -> None:
    """A wrapped logical row should expose projection-owned targets on lower visual rows."""

    app = ensure_qapp()
    text = "alpha, beta, gamma, delta, epsilon, zeta"
    box = show_prompt_editor(
        widgets,
        text=text,
        width=190,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=5,
    )
    base_drag_snapshot = document_service.build_reorder_preview_snapshot(
        document_view,
        base_drag_layout_view,
    )
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            text,
            dragged_chip_index=5,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        )
    )
    process_events(app)
    snapshot = surface.reorder_base_drag_placement_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    lower_line_placement = next(
        placement
        for placement in snapshot.placements
        if isinstance(placement.target, PromptLineDropTarget)
        and placement.placement_id.visual_line_index > 0
    )

    selected = surface.reorder_placement_at_rect(
        lower_line_placement.hit_rect,
        snapshot=snapshot,
        active_placement_id=None,
    )

    assert selected == lower_line_placement
