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

"""Verify reorder overlay suppression and stale-publication safety."""

from __future__ import annotations


from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.projection.reorder_surface_visual_state import (
    PromptReorderSurfaceVisualPublication,
)
from tests.presentation.editor.prompt_editor.projection.reorder_surface.support import (
    _build_reorder_preview_state,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.support.prompt_editor.projection_engine_support import (
    show_prompt_editor,
    surface_for,
)


def test_projection_surface_excludes_dragged_chip_and_separator_from_preview_region(
    widgets: list[QWidget],
) -> None:
    """Exact drag-proxy snapshots should suppress chip text and its separator."""

    text = "alpha, beta, gamma"
    drop_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    box = show_prompt_editor(
        widgets,
        text=text,
        width=320,
    )
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        text,
        dragged_chip_index=1,
        drop_target=drop_target,
    )

    surface.set_reorder_preview_state(preview_state)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=drop_target,
    )
    preview_chip_geometry = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    paint_snapshots = surface.reorder_preview_chip_projection_paint_snapshots(
        chip_geometry_snapshot=preview_chip_geometry,
        chip_owned_ranges_by_index=(
            preview_state.preview_snapshot.chip_owned_ranges_by_index
        ),
    )
    surface.set_reorder_surface_visual_publication(
        PromptReorderSurfaceVisualPublication(
            mode="preview",
            chips=(),
            suppression_snapshots_by_index={1: paint_snapshots[1]},
        )
    )

    visible_region = surface._preview_visible_region()  # noqa: SLF001
    assert visible_region is not None
    owned_ranges = preview_state.preview_snapshot.chip_owned_ranges_by_index[1]
    assert len(owned_ranges) == 2
    for start, end in owned_ranges:
        fragments = surface.reorder_preview_fragments(start=start, end=end)
        assert fragments
        for fragment in fragments:
            assert visible_region.intersected(
                QRegion(fragment.toAlignedRect())
            ).isEmpty()


def test_projection_surface_excludes_overlay_painted_preview_chips(
    widgets: list[QWidget],
) -> None:
    """Preview drawing should suppress only chips with fresh overlay snapshots."""

    box = show_prompt_editor(
        widgets,
        text="alpha, beta, gamma",
        width=320,
    )
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.set_reorder_preview_state(preview_state)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha, beta, gamma")
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_chip_geometry = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    preview_paint_snapshots = surface.reorder_preview_chip_projection_paint_snapshots(
        chip_geometry_snapshot=preview_chip_geometry,
        chip_owned_ranges_by_index=(
            preview_state.preview_snapshot.chip_owned_ranges_by_index
        ),
    )
    surface.set_reorder_surface_visual_publication(
        PromptReorderSurfaceVisualPublication(
            mode="preview",
            chips=(),
            suppression_snapshots_by_index={2: preview_paint_snapshots[2]},
        )
    )

    visible_region = surface._preview_visible_region()  # noqa: SLF001
    assert visible_region is not None
    suppressed_ranges = preview_state.preview_snapshot.chip_owned_ranges_by_index[2]
    for start, end in suppressed_ranges:
        fragments = surface.reorder_preview_fragments(start=start, end=end)
        assert fragments
        for fragment in fragments:
            assert visible_region.intersected(
                QRegion(fragment.toAlignedRect())
            ).isEmpty()

    unsuppressed_ranges = preview_state.preview_snapshot.chip_owned_ranges_by_index[0]
    assert any(
        not visible_region.intersected(QRegion(fragment.toAlignedRect())).isEmpty()
        for start, end in unsuppressed_ranges
        for fragment in surface.reorder_preview_fragments(start=start, end=end)
    )

    surface.set_reorder_surface_visual_publication(
        PromptReorderSurfaceVisualPublication(
            mode="preview",
            chips=(),
            suppression_snapshots_by_index={},
        )
    )
    restored_region = surface._preview_visible_region()  # noqa: SLF001
    assert restored_region is None


def test_projection_surface_keeps_text_visible_for_stale_overlay_snapshot(
    widgets: list[QWidget],
) -> None:
    """A preview generation race must retain surface-owned projection text."""

    text = "alpha, beta, gamma"
    drop_target = PromptLineDropTarget(row_index=0, insertion_index=0)
    box = show_prompt_editor(widgets, text=text, width=320)
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        text,
        dragged_chip_index=1,
        drop_target=drop_target,
    )
    surface.set_reorder_preview_state(preview_state)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=drop_target,
    )
    preview_chip_geometry = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    paint_snapshots = surface.reorder_preview_chip_projection_paint_snapshots(
        chip_geometry_snapshot=preview_chip_geometry,
        chip_owned_ranges_by_index=(
            preview_state.preview_snapshot.chip_owned_ranges_by_index
        ),
    )
    stale_snapshot = paint_snapshots[2]
    surface.set_reorder_surface_visual_publication(
        PromptReorderSurfaceVisualPublication(
            mode="preview",
            chips=(),
            suppression_snapshots_by_index={2: stale_snapshot},
        )
    )

    refreshed_state = _build_reorder_preview_state(
        text,
        dragged_chip_index=1,
        drop_target=drop_target,
    )
    surface.set_reorder_preview_state(refreshed_state)
    visible_region = surface._preview_visible_region()  # noqa: SLF001

    assert visible_region is not None
    suppressed_ranges = refreshed_state.preview_snapshot.chip_owned_ranges_by_index[2]
    assert any(
        not visible_region.intersected(QRegion(fragment.toAlignedRect())).isEmpty()
        for start, end in suppressed_ranges
        for fragment in surface.reorder_preview_fragments(start=start, end=end)
    )
