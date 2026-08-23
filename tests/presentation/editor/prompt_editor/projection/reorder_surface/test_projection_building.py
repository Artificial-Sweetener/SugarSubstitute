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

"""Verify reorder preview projection construction and queries."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.geometry.selection import (
    PromptSelectionGeometry,
)
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


def test_projection_surface_switches_to_reorder_preview_text_and_exposes_preview_queries(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preview state should replace live paint ownership without mutating the live document."""

    prompt_text = "alpha, beta, gamma"
    box = show_prompt_editor(
        widgets,
        text=prompt_text,
        width=320,
    )
    surface = surface_for(box)
    document_service = PromptDocumentService()
    document_view = document_service.build_document_view(prompt_text)
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_view,
        dragged_segment_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    base_drag_layout_view = document_service.build_base_drag_layout_view(
        document_view,
        dragged_segment_index=1,
    )
    preview_state = _build_reorder_preview_state(
        prompt_text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    surface.set_reorder_preview_state(preview_state)

    preview_document = surface._reorder_preview_projection.preview_document  # noqa: SLF001
    assert preview_document is not None
    assert preview_document.source_text == "beta, alpha, gamma"
    assert surface.projection_document().source_text == "alpha, beta, gamma"
    counters = surface.reorder_geometry_cache_counters()
    assert counters["preview_projection_full_layout_count"] == 0
    assert counters["preview_projection_incremental_layout_count"] == 2
    beta_range = preview_state.preview_snapshot.chip_rendered_ranges_by_index[1]
    assert surface.reorder_preview_fragments(
        start=beta_range[0],
        end=beta_range[1],
    )
    preview_chip_snapshot = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    assert preview_chip_snapshot.geometries_by_chip_index[1].chip_index == 1
    preview_paint_snapshots = surface.reorder_preview_chip_projection_paint_snapshots(
        chip_geometry_snapshot=preview_chip_snapshot,
        chip_owned_ranges_by_index=(
            preview_state.preview_snapshot.chip_owned_ranges_by_index
        ),
    )
    beta_paint_snapshot = preview_paint_snapshots[1]
    assert beta_paint_snapshot.key.segment_index == 1
    assert beta_paint_snapshot.key.mode == "preview"
    assert (
        beta_paint_snapshot.source_ranges
        == (preview_state.preview_snapshot.chip_owned_ranges_by_index[1])
    )
    assert beta_paint_snapshot.text_fragments
    preview_frame = surface._reorder_preview_projection.preview_frame  # noqa: SLF001
    assert preview_frame is not None
    preview_selection_geometry = preview_frame.geometry.selection
    source_range_fragments = PromptSelectionGeometry.source_range_fragments

    def fail_redundant_fragment_lookup(
        selection_geometry: PromptSelectionGeometry,
        start: int,
        end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Fail if fresh paint snapshots are ignored for suppression geometry."""

        if selection_geometry is preview_selection_geometry:
            raise AssertionError("fresh preview paint snapshots should own suppression")
        return source_range_fragments(
            selection_geometry,
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    monkeypatch.setattr(
        PromptSelectionGeometry,
        "source_range_fragments",
        fail_redundant_fragment_lookup,
    )
    surface.set_reorder_surface_visual_publication(
        PromptReorderSurfaceVisualPublication(
            mode="preview",
            chips=(),
            suppression_snapshots_by_index={
                index: preview_paint_snapshots[index] for index in (0, 2)
            },
        )
    )
    assert surface._preview_visible_region() is not None  # noqa: SLF001
    assert surface.reorder_preview_cursor_rect(beta_range[0]).isEmpty() is False
    base_drag_snapshot = preview_state.base_drag_snapshot
    assert base_drag_snapshot is not None
    base_range = base_drag_snapshot.chip_rendered_ranges_by_index[0]
    assert surface.reorder_base_drag_fragments(
        start=base_range[0],
        end=base_range[1],
    )
    base_chip_snapshot = surface.reorder_base_drag_chip_geometry_snapshot(
        snapshot=base_drag_snapshot,
        layout_view=base_drag_layout_view,
    )
    assert base_chip_snapshot.geometries_by_chip_index[0].chip_index == 0
    assert surface.reorder_base_drag_cursor_rect(base_range[0]).isEmpty() is False


def test_projection_surface_keeps_reused_reorder_layouts_at_editor_width(
    widgets: list[QWidget],
) -> None:
    """Preview and base-drag layouts should retain the editor's prepared width."""

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

    preview_frame = surface._reorder_preview_projection.preview_frame  # noqa: SLF001
    base_drag_frame = (  # noqa: SLF001
        surface._reorder_preview_projection.base_drag_frame
    )
    assert preview_frame is not None
    assert base_drag_frame is not None
    assert preview_frame.output.configuration.text_width > 16.0
    assert base_drag_frame.output.configuration.text_width > 16.0


def test_reorder_base_drag_rebuilds_suffix_with_resolvable_semantics(
    widgets: list[QWidget],
) -> None:
    """Base-drag reuse must not retain stale run IDs after blank paragraphs."""

    prompt_text = (
        "alpha, beta, gamma,\n\n"
        "delta, epsilon, zeta,\n\n"
        "eta, theta, iota,\n\n"
        "kappa, lambda, mu,\n\n"
        "ordinary text before decoration, (blue:1.35) ribbon, nu, xi, omicron,"
    )
    box = show_prompt_editor(widgets, text=prompt_text, width=760)
    surface = surface_for(box)
    preview_state = _build_reorder_preview_state(
        prompt_text,
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=2, insertion_index=1),
    )
    base_drag_snapshot = preview_state.base_drag_snapshot
    assert base_drag_snapshot is not None
    surface.set_reorder_preview_state(
        replace(
            preview_state,
            preview_snapshot=base_drag_snapshot,
            preview_layout_key=preview_state.base_drag_layout_key,
            active_drop_target_identity=None,
        )
    )

    preview_frame = surface._reorder_preview_projection.preview_frame  # noqa: SLF001
    assert preview_frame is not None
    unresolved_fragments = tuple(
        fragment
        for line in preview_frame.output.snapshot.lines
        for fragment in line.fragments
        if preview_frame.paint_input.effective_run(fragment.run_id) is None
        or (
            fragment.token_id is not None
            and preview_frame.paint_input.effective_token(fragment.token_id) is None
        )
    )
    assert unresolved_fragments == ()
    preview_document = (  # noqa: SLF001
        surface._reorder_preview_projection.preview_document
    )
    assert preview_document is not None
    assert "ordinary text before decoration" in preview_document.source_text
    incremental_layout_count = surface.reorder_geometry_cache_counters()[
        "preview_projection_incremental_layout_count"
    ]
    assert isinstance(incremental_layout_count, int)
    assert incremental_layout_count >= 1
