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

"""Verify reorder visual frame publication and lifecycle."""

from __future__ import annotations


import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.projection.reorder_surface_chrome import (
    PromptReorderSurfaceChromeChip,
    PromptReorderSurfaceChromeStyle,
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


def test_projection_surface_publishes_combined_reorder_visual_once(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chrome and suppression should produce one surface render-frame publish."""

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
    preview_layout_view = document_service.build_preview_drop_layout_view(
        document_service.build_document_view(text),
        dragged_segment_index=1,
        drop_target=drop_target,
    )
    geometry = surface.reorder_preview_chip_geometry_snapshot(
        snapshot=preview_state.preview_snapshot,
        layout_view=preview_layout_view,
    )
    paint_snapshots = surface.reorder_preview_chip_projection_paint_snapshots(
        chip_geometry_snapshot=geometry,
        chip_owned_ranges_by_index=(
            preview_state.preview_snapshot.chip_owned_ranges_by_index
        ),
    )
    publication = PromptReorderSurfaceVisualPublication(
        mode="preview",
        chips=(
            PromptReorderSurfaceChromeChip(
                segment_index=0,
                geometry=geometry.geometries_by_chip_index[0],
                style=PromptReorderSurfaceChromeStyle(
                    fill_color=QColor(10, 20, 30),
                    border_color=QColor(40, 50, 60),
                ),
            ),
        ),
        suppression_snapshots_by_index={2: paint_snapshots[2]},
    )
    publish_count = 0
    publish_render_frame = surface._publish_render_frame  # noqa: SLF001

    def count_publish() -> None:
        """Count surface frame publication while preserving production behavior."""

        nonlocal publish_count
        publish_count += 1
        publish_render_frame()

    monkeypatch.setattr(surface, "_publish_render_frame", count_publish)

    surface.set_reorder_surface_visual_publication(publication)
    assert publish_count == 1
    assert surface._reorder_surface_visual_state.state.revision == 1  # noqa: SLF001
    surface.set_reorder_surface_visual_publication(publication)
    assert publish_count == 1
    assert surface._reorder_surface_visual_state.state.revision == 1  # noqa: SLF001


def test_unchanged_reorder_preview_publication_reuses_the_exact_render_frame(
    widgets: list[QWidget],
) -> None:
    """Stable preview context should not allocate replacement render frames."""

    prompt_text = "alpha, beta, gamma"
    box = show_prompt_editor(widgets, text=prompt_text, width=320)
    surface = surface_for(box)
    surface.set_reorder_preview_state(
        _build_reorder_preview_state(
            prompt_text,
            dragged_chip_index=1,
            drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        )
    )
    owner = surface._render_frame_owner  # noqa: SLF001
    initial_frame = owner.frame

    surface._publish_render_frame()  # noqa: SLF001
    first_repeat = owner.frame
    surface._publish_render_frame()  # noqa: SLF001

    assert first_repeat is initial_frame
    assert owner.frame is initial_frame


def test_projection_surface_clears_reorder_preview_state_back_to_live_rendering(
    widgets: list[QWidget],
) -> None:
    """Clearing preview state should restore the live surface queries and layout state."""

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
    surface.clear_reorder_preview_state()

    assert surface._reorder_preview_projection.preview_document is None  # noqa: SLF001
    assert surface._reorder_preview_projection.preview_frame is None  # noqa: SLF001
    assert surface.reorder_preview_fragments(start=0, end=1) == ()
    assert surface.reorder_preview_cursor_rect(0).isEmpty() is True
