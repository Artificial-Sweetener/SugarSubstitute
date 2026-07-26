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

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPalette, QRegion

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
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
from substitute.presentation.editor.prompt_editor.projection.transient_edit_layer_owner import (
    PromptTransientEditRenderLayerOwner,
)

from tests.prompt_projection_layout_test_helpers import projection_layout_for
from tests.prompt_projection_test_helpers import ensure_qapp


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
        source_identity=PromptSourceIdentity(source_revision=3),
        cursor_position=4,
        anchor_position=4,
        document_rect=QRectF(1.0, 2.0, 3.0, 4.0),
        committed_source_identity=PromptSourceIdentity(source_revision=2),
    )
    insertion_overlay = PromptProjectionTransientInsertionOverlay(
        source_identity=PromptSourceIdentity(source_revision=3),
        committed_source_identity=PromptSourceIdentity(source_revision=2),
        source_start=10,
        text="x",
        document_rect=QRectF(10.0, 6.0, 1.0, 14.0),
    )
    deletion_overlay = PromptProjectionTransientDeletionOverlay(
        source_identity=PromptSourceIdentity(source_revision=3),
        committed_source_identity=PromptSourceIdentity(source_revision=2),
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
            source_identity=PromptSourceIdentity(source_revision=3),
            cursor_position=4,
            anchor_position=4,
        )
        == caret_geometry
    )
    assert (
        controller.valid_insertion_overlay(
            freshness_is_stale_safe=True,
            source_identity=PromptSourceIdentity(source_revision=3),
        )
        == insertion_overlay
    )
    assert (
        controller.valid_deletion_overlay(
            freshness_is_stale_safe=True,
            source_identity=PromptSourceIdentity(source_revision=3),
        )
        == deletion_overlay
    )
    assert (
        controller.valid_caret_geometry(
            freshness_is_stale_safe=False,
            source_identity=PromptSourceIdentity(source_revision=3),
            cursor_position=4,
            anchor_position=4,
        )
        is None
    )
    assert (
        controller.valid_insertion_overlay(
            freshness_is_stale_safe=True,
            source_identity=PromptSourceIdentity(source_revision=4),
        )
        is None
    )

    controller.clear()

    assert controller.caret_geometry is None
    assert controller.insertion_overlay is None
    assert controller.deletion_overlay is None


def test_transient_edit_layer_publishes_complete_commands_before_paint() -> None:
    """Transient insertion and deletion state should become one prepared layer."""

    controller = PromptProjectionTransientEditOverlayController()
    source_identity = PromptSourceIdentity(source_revision=3)
    controller.set_overlays(
        caret_geometry=None,
        insertion_overlay=PromptProjectionTransientInsertionOverlay(
            source_identity=source_identity,
            committed_source_identity=PromptSourceIdentity(source_revision=2),
            source_start=4,
            text="x",
            document_rect=QRectF(20.0, 8.0, 1.0, 14.0),
        ),
        deletion_overlay=PromptProjectionTransientDeletionOverlay(
            source_identity=source_identity,
            committed_source_identity=PromptSourceIdentity(source_revision=2),
            source_start=2,
            source_end=3,
            document_rects=(QRectF(10.0, 8.0, 6.0, 14.0),),
        ),
    )
    owner = PromptTransientEditRenderLayerOwner()

    assert owner.prepare(
        overlays=controller,
        freshness_is_stale_safe=True,
        source_identity=source_identity,
        metrics=_projection_metrics(),
        viewport_rect=QRectF(0.0, 0.0, 100.0, 40.0),
        scroll_offset=2.0,
        font=QFont(),
        palette=QPalette(),
    )
    assert owner.layer.insertion is not None
    assert owner.layer.insertion.text == "x"
    assert owner.layer.deletion is not None
    assert owner.layer.deletion.rects
    assert owner.layer.content_visible_region is not None


def test_transient_edit_overlays_extend_and_trim_pending_insertions() -> None:
    """Insertion overlays should merge adjacent typing and trim overlay deletes."""

    controller = PromptProjectionTransientEditOverlayController()
    first_overlay = controller.single_character_insertion_overlay(
        start=10,
        replacement_text="x",
        source_identity=PromptSourceIdentity(source_revision=3),
        committed_source_identity=PromptSourceIdentity(source_revision=2),
        current_caret_document_rect=QRectF(30.0, 6.0, 1.0, 14.0),
        freshness_is_stale_safe=True,
        previous_source_identity=PromptSourceIdentity(source_revision=2),
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
        source_identity=PromptSourceIdentity(source_revision=4),
        committed_source_identity=PromptSourceIdentity(source_revision=2),
        current_caret_document_rect=QRectF(31.0, 6.0, 1.0, 14.0),
        freshness_is_stale_safe=True,
        previous_source_identity=PromptSourceIdentity(source_revision=3),
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
        source_identity=PromptSourceIdentity(source_revision=4),
    )
    trimmed_overlay = controller.insertion_overlay_after_deletion(
        start=10,
        end=11,
        source_identity=PromptSourceIdentity(source_revision=5),
        freshness_is_stale_safe=True,
        current_source_identity=PromptSourceIdentity(source_revision=4),
    )

    assert trimmed_overlay is not None
    assert trimmed_overlay.source_identity.source_revision == 5
    assert trimmed_overlay.source_start == 10
    assert trimmed_overlay.text == "y"


def test_transient_fallback_extends_the_existing_contiguous_insertion() -> None:
    """Fallback feedback must preserve all text since the committed projection."""

    controller = PromptProjectionTransientEditOverlayController()
    committed_identity = PromptSourceIdentity(source_revision=2, source_length=10)
    first_overlay = PromptProjectionTransientInsertionOverlay(
        source_identity=PromptSourceIdentity(source_revision=3, source_length=11),
        committed_source_identity=committed_identity,
        source_start=10,
        text="j",
        document_rect=QRectF(30.0, 6.0, 1.0, 14.0),
    )
    controller.set_overlays(
        caret_geometry=None,
        insertion_overlay=first_overlay,
        deletion_overlay=None,
    )

    extended = controller.fallback_insertion_overlay_for_edit(
        start=11,
        end=11,
        replacement_text="f",
        source_identity=PromptSourceIdentity(source_revision=4, source_length=12),
        committed_source_identity=committed_identity,
        current_caret_document_rect=QRectF(36.0, 6.0, 1.0, 14.0),
        metrics=_projection_metrics(),
        content_right=120.0,
        document_margin=4.0,
        source_line_content_left_inset=0.0,
        freshness_is_stale_safe=True,
        previous_source_identity=first_overlay.source_identity,
    )

    assert extended is not None
    assert extended.source_start == 10
    assert extended.text == "jf"
    assert extended.document_rect == first_overlay.document_rect


def test_transient_edit_overlays_merge_delete_geometry_and_repaint_bounds() -> None:
    """Deletion overlays should merge adjacent ranges and expose repaint geometry."""

    controller = PromptProjectionTransientEditOverlayController()
    layout, _projection = projection_layout_for("abcdef", text_width=100.0)

    first_overlay = controller.deletion_overlay_for_single_character_range(
        start=4,
        end=5,
        source_identity=PromptSourceIdentity(source_revision=3),
        committed_source_identity=PromptSourceIdentity(source_revision=2),
        previous_overlay=None,
        content_size=layout.frame.output.snapshot.content_size,
        selection_geometry=layout.frame.geometry.selection,
        viewport_width=100.0,
        viewport_height=60.0,
    )
    assert first_overlay is not None
    second_overlay = controller.deletion_overlay_for_single_character_range(
        start=3,
        end=4,
        source_identity=PromptSourceIdentity(source_revision=4),
        committed_source_identity=PromptSourceIdentity(source_revision=2),
        previous_overlay=first_overlay,
        content_size=layout.frame.output.snapshot.content_size,
        selection_geometry=layout.frame.geometry.selection,
        viewport_width=100.0,
        viewport_height=60.0,
    )

    assert second_overlay is not None
    assert second_overlay.source_start == 3
    assert second_overlay.source_end == 5
    assert len(second_overlay.document_rects) == 2

    erase_rects = controller.deletion_overlay_erase_rects(
        second_overlay,
        scroll_offset=2.0,
    )
    assert len(erase_rects) == 1
    assert erase_rects[0].top() == (
        min(rect.top() for rect in second_overlay.document_rects) - 4.0
    )
    assert erase_rects[0].bottom() == (
        max(rect.bottom() for rect in second_overlay.document_rects)
    )

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
        source_identity=PromptSourceIdentity(source_revision=1),
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
        source_identity=PromptSourceIdentity(source_revision=1),
    )
