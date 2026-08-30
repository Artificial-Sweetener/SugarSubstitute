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
from PySide6.QtGui import QFont, QPalette

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.metrics import (
    PromptProjectionMetrics,
    PromptProjectionMetricsFactory,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_layer_owner import (
    PromptTransientEditRenderLayerOwner,
)

from tests.support.prompt_editor.projection_engine_support import ensure_qapp


def _projection_metrics() -> PromptProjectionMetrics:
    """Return projection metrics after ensuring a Qt application exists."""

    ensure_qapp()
    return PromptProjectionMetricsFactory().create(
        base_font=QFont(),
        document_margin=4.0,
        wrap_width=120.0,
    )


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
