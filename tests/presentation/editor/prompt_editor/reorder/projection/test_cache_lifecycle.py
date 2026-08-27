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

"""Verify prompt reorder preview-projection cache lifecycle."""

from __future__ import annotations

from dataclasses import replace


from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.projection.theme import (
    semantic_palette_from_theme,
)

from .support import (
    _service,
    _context,
    _counter,
    _build_reorder_preview_state,
)


def test_reorder_projection_service_reuses_active_preview_projection(
    app: QApplication,
) -> None:
    """Setting the same preview state twice should reuse active projection layouts."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    context = _context()

    service.set_preview_state(
        preview_state,
        context=context,
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    service.set_preview_state(
        preview_state,
        context=context,
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )

    counters = service.counters()
    assert counters["projection_snapshot_rebuild_count"] == 2
    assert counters["preview_projection_full_layout_count"] == 1
    assert counters["preview_projection_incremental_layout_count"] == 1
    assert counters["preview_projection_exact_layout_reuse_count"] == 0
    assert counters["preview_projection_active_cache_hit_count"] == 1


def test_reorder_projection_service_reuses_identical_base_layout(
    app: QApplication,
) -> None:
    """An unchanged base snapshot should share the immutable preview layout."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state = replace(
        preview_state,
        base_drag_snapshot=preview_state.preview_snapshot,
    )

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )

    counters = service.counters()
    assert counters["projection_snapshot_rebuild_count"] == 1
    assert counters["preview_projection_full_layout_count"] == 1
    assert counters["preview_projection_incremental_layout_count"] == 0
    assert counters["preview_projection_exact_layout_reuse_count"] == 1
    assert service.base_drag_document is service.preview_document
    assert service.base_drag_frame is service.preview_frame


def test_reorder_projection_service_clears_preview_only_state(
    app: QApplication,
) -> None:
    """Clearing preview state should clear active preview and base-drag layouts."""

    _ = app
    service = _service()
    preview_state = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )

    service.set_preview_state(
        preview_state,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    invalidation = service.set_preview_state(
        None,
        context=_context(),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )

    assert invalidation.clear_all_geometry_reason == "reorder_preview_clear"
    assert service.preview_state is None
    assert service.preview_document is None
    assert service.preview_frame is None
    assert service.base_drag_document is None
    assert service.base_drag_frame is None
    assert not service.is_active()


def test_reorder_projection_service_incremental_target_preserves_lru_revisit(
    app: QApplication,
) -> None:
    """Target changes reflow locally while cached targets remain reusable."""

    _ = app
    service = _service()
    preview_state_a = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=0),
    )
    preview_state_b = _build_reorder_preview_state(
        "alpha, beta, gamma",
        dragged_chip_index=1,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=2),
    )

    service.set_preview_state(
        preview_state_a,
        context=_context(active_drop_target_identity=("line", 0, 0)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_first_target = service.counters()
    service.set_preview_state(
        preview_state_b,
        context=_context(active_drop_target_identity=("line", 0, 2)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    before_revisit = service.counters()
    assert (
        before_revisit["preview_projection_full_layout_count"]
        == (after_first_target["preview_projection_full_layout_count"])
    )
    assert _counter(
        before_revisit,
        "preview_projection_incremental_layout_count",
    ) == (
        _counter(
            after_first_target,
            "preview_projection_incremental_layout_count",
        )
        + 1
    )
    service.set_preview_state(
        preview_state_a,
        context=_context(active_drop_target_identity=("line", 0, 0)),
        font=QFont(),
        palette=QPalette(),
        semantic_palette=semantic_palette_from_theme(),
    )
    after_revisit = service.counters()

    assert (
        after_revisit["projection_snapshot_rebuild_count"]
        == (before_revisit["projection_snapshot_rebuild_count"])
    )
    assert (
        after_revisit["preview_projection_full_layout_count"]
        == (before_revisit["preview_projection_full_layout_count"])
    )
    assert _counter(after_revisit, "preview_projection_lru_cache_hit_count") == (
        _counter(before_revisit, "preview_projection_lru_cache_hit_count") + 1
    )
