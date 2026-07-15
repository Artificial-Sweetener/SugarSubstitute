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

"""Guard transient source-edit overlay ownership and geometry."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QFont, QRegion

from substitute.presentation.editor.prompt_editor.projection.layout_engine import (
    PromptProjectionLayout,
)
from substitute.presentation.editor.prompt_editor.projection.metrics import (
    PromptProjectionMetrics,
    PromptProjectionMetricsFactory,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientCaretGeometry,
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)

from tests.prompt_projection_test_helpers import ensure_qapp


class _OverlayLayout:
    """Provide deterministic layout geometry for overlay controller tests."""

    document_margin = 8.0

    def __init__(self) -> None:
        """Create an empty fake layout."""

        self.requested_ranges: list[tuple[int, int]] = []

    def content_size(self) -> QSizeF:
        """Return stable document content bounds."""

        return QSizeF(120.0, 80.0)

    def source_range_fragments(
        self,
        source_start: int,
        source_end: int,
        *,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return one source fragment per requested single-character range."""

        _ = viewport_rect
        _ = scroll_offset
        self.requested_ranges.append((source_start, source_end))
        if (source_start, source_end) == (3, 4):
            return (QRectF(15.0, 10.0, 5.0, 10.0),)
        if (source_start, source_end) == (4, 5):
            return (QRectF(20.0, 10.0, 5.0, 10.0),)
        return ()


def _projection_metrics() -> PromptProjectionMetrics:
    """Return projection metrics after ensuring a Qt application exists."""

    ensure_qapp()
    return PromptProjectionMetricsFactory().create(
        base_font=QFont(),
        document_margin=4.0,
        wrap_width=120.0,
    )


def test_transient_edit_overlays_validate_against_live_source_state() -> None:
    """Transient overlay state should expire on freshness or source mismatch."""

    controller = PromptProjectionTransientEditOverlayController()
    caret_geometry = PromptProjectionTransientCaretGeometry(
        source_revision=3,
        cursor_position=4,
        anchor_position=4,
        document_rect=QRectF(1.0, 2.0, 3.0, 4.0),
        committed_source_revision=2,
    )
    insertion_overlay = PromptProjectionTransientInsertionOverlay(
        source_revision=3,
        committed_source_revision=2,
        source_start=10,
        text="x",
        document_rect=QRectF(10.0, 6.0, 1.0, 14.0),
    )
    deletion_overlay = PromptProjectionTransientDeletionOverlay(
        source_revision=3,
        committed_source_revision=2,
        source_start=9,
        source_end=10,
        document_rects=(QRectF(9.0, 6.0, 6.0, 14.0),),
    )

    controller.set_overlays(
        caret_geometry=caret_geometry,
        insertion_overlay=insertion_overlay,
        deletion_overlay=deletion_overlay,
    )

    assert (
        controller.valid_caret_geometry(
            freshness_is_stale_safe=True,
            source_revision=3,
            cursor_position=4,
            anchor_position=4,
        )
        == caret_geometry
    )
    assert (
        controller.valid_insertion_overlay(
            freshness_is_stale_safe=True,
            source_revision=3,
        )
        == insertion_overlay
    )
    assert (
        controller.valid_deletion_overlay(
            freshness_is_stale_safe=True,
            source_revision=3,
        )
        == deletion_overlay
    )
    assert (
        controller.valid_caret_geometry(
            freshness_is_stale_safe=False,
            source_revision=3,
            cursor_position=4,
            anchor_position=4,
        )
        is None
    )
    assert (
        controller.valid_insertion_overlay(
            freshness_is_stale_safe=True,
            source_revision=4,
        )
        is None
    )

    controller.clear()

    assert controller.caret_geometry is None
    assert controller.insertion_overlay is None
    assert controller.deletion_overlay is None


def test_transient_edit_overlays_extend_and_trim_pending_insertions() -> None:
    """Insertion overlays should merge adjacent typing and trim overlay deletes."""

    controller = PromptProjectionTransientEditOverlayController()
    first_overlay = controller.single_character_insertion_overlay(
        start=10,
        replacement_text="x",
        source_revision=3,
        committed_source_revision=2,
        current_caret_document_rect=QRectF(30.0, 6.0, 1.0, 14.0),
        freshness_is_stale_safe=True,
        current_source_revision=2,
    )
    assert first_overlay is not None
    controller.set_overlays(
        caret_geometry=None,
        insertion_overlay=first_overlay,
        deletion_overlay=None,
    )

    next_overlay = controller.single_character_insertion_overlay(
        start=11,
        replacement_text="y",
        source_revision=4,
        committed_source_revision=2,
        current_caret_document_rect=QRectF(31.0, 6.0, 1.0, 14.0),
        freshness_is_stale_safe=True,
        current_source_revision=3,
    )
    assert next_overlay is not None
    assert next_overlay.source_start == 10
    assert next_overlay.text == "xy"

    controller.set_overlays(
        caret_geometry=None,
        insertion_overlay=next_overlay,
        deletion_overlay=None,
    )

    assert controller.deletion_targets_insertion_overlay(
        start=10,
        end=11,
        freshness_is_stale_safe=True,
        source_revision=4,
    )
    trimmed_overlay = controller.insertion_overlay_after_deletion(
        start=10,
        end=11,
        source_revision=5,
        freshness_is_stale_safe=True,
        current_source_revision=4,
    )

    assert trimmed_overlay is not None
    assert trimmed_overlay.source_revision == 5
    assert trimmed_overlay.source_start == 10
    assert trimmed_overlay.text == "y"


def test_transient_edit_overlays_merge_delete_geometry_and_repaint_bounds() -> None:
    """Deletion overlays should merge adjacent ranges and expose repaint geometry."""

    controller = PromptProjectionTransientEditOverlayController()
    layout = _OverlayLayout()
    typed_layout = cast(PromptProjectionLayout, layout)

    first_overlay = controller.deletion_overlay_for_single_character_range(
        start=4,
        end=5,
        source_revision=3,
        committed_source_revision=2,
        previous_overlay=None,
        layout=typed_layout,
        viewport_width=100.0,
        viewport_height=60.0,
    )
    assert first_overlay is not None
    second_overlay = controller.deletion_overlay_for_single_character_range(
        start=3,
        end=4,
        source_revision=4,
        committed_source_revision=2,
        previous_overlay=first_overlay,
        layout=typed_layout,
        viewport_width=100.0,
        viewport_height=60.0,
    )

    assert second_overlay is not None
    assert second_overlay.source_start == 3
    assert second_overlay.source_end == 5
    assert layout.requested_ranges == [(4, 5), (3, 4)]

    erase_rects = controller.deletion_overlay_erase_rects(
        second_overlay,
        scroll_offset=2.0,
    )
    assert len(erase_rects) == 1
    assert erase_rects[0].top() == 6.0
    assert erase_rects[0].bottom() == 20.0

    repaint_rect = controller.deletion_overlay_repaint_rect(
        previous_overlay=first_overlay,
        next_overlay=second_overlay,
        scroll_offset=2.0,
    )
    assert repaint_rect is not None
    assert repaint_rect.contains(erase_rects[0])

    visible_region = controller.deletion_visible_region(
        second_overlay,
        viewport_region=QRegion(0, 0, 100, 40),
        scroll_offset=2.0,
    )
    assert visible_region is not None
    assert not visible_region.contains(erase_rects[0].toAlignedRect())


def test_transient_edit_overlays_gate_single_character_insertion_by_width() -> None:
    """Insertion deferral should reject text that exceeds the content edge."""

    controller = PromptProjectionTransientEditOverlayController()
    metrics = _projection_metrics()

    assert controller.can_defer_insertion_overlay(
        start=3,
        end=3,
        replacement_text="x",
        live_source_length=4,
        committed_source_length=3,
        caret_rect=QRectF(20.0, 5.0, 1.0, 14.0),
        content_right=80.0,
        metrics=metrics,
        freshness_is_stale_safe=True,
        source_revision=1,
    )
    assert not controller.can_defer_insertion_overlay(
        start=3,
        end=3,
        replacement_text="x",
        live_source_length=4,
        committed_source_length=3,
        caret_rect=QRectF(79.0, 5.0, 1.0, 14.0),
        content_right=80.0,
        metrics=metrics,
        freshness_is_stale_safe=True,
        source_revision=1,
    )
