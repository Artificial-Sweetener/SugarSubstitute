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

"""Test transient edit geometry and repaint publication ownership."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.projection.metrics import (
    PromptProjectionMetricsFactory,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)
from substitute.presentation.editor.prompt_editor.projection.transient_edit_presentation_owner import (
    PromptTransientEditPresentationOwner,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp


class _ViewportRecorder:
    """Record exact viewport update requests without mounting a widget."""

    def __init__(self) -> None:
        """Create an empty update log."""

        self.updates: list[QRect] = []

    def update(self, rect: QRect) -> None:
        """Record one requested repaint rectangle."""

        self.updates.append(QRect(rect))


def test_presentation_owner_publishes_and_repaints_exact_overlay_damage() -> None:
    """Insertion and deletion updates should publish before exact repaint damage."""

    ensure_qapp()
    overlays = PromptProjectionTransientEditOverlayController()
    metrics = PromptProjectionMetricsFactory().create(
        base_font=QFont(),
        document_margin=4.0,
        wrap_width=160.0,
    )
    viewport = _ViewportRecorder()
    publications: list[None] = []
    owner = PromptTransientEditPresentationOwner(
        overlays=overlays,
        metrics=lambda: metrics,
        scroll_offset=lambda: 6.0,
        viewport=cast(QWidget, viewport),
        publish_render_frame=lambda: publications.append(None),
    )
    identity = PromptSourceIdentity(source_revision=3)
    insertion = PromptProjectionTransientInsertionOverlay(
        source_identity=identity,
        committed_source_identity=PromptSourceIdentity(source_revision=2),
        source_start=4,
        text="xy",
        document_rect=QRectF(10.0, 20.0, 1.0, 14.0),
    )
    deletion = PromptProjectionTransientDeletionOverlay(
        source_identity=identity,
        committed_source_identity=PromptSourceIdentity(source_revision=2),
        source_start=2,
        source_end=3,
        document_rects=(QRectF(2.0, 20.0, 8.0, 14.0),),
    )
    insertion_damage = overlays.insertion_overlay_repaint_rect(
        previous_overlay=None,
        next_overlay=insertion,
        metrics=metrics,
        scroll_offset=6.0,
    )
    deletion_damage = overlays.deletion_overlay_repaint_rect(
        previous_overlay=None,
        next_overlay=deletion,
        scroll_offset=6.0,
    )
    assert insertion_damage is not None
    assert deletion_damage is not None

    owner.update_insertion_overlay_paint(None, insertion)
    owner.update_deletion_overlay_paint(None, deletion)

    assert len(publications) == 2
    assert viewport.updates == [
        insertion_damage.toAlignedRect(),
        deletion_damage.toAlignedRect(),
    ]
    assert owner.insertion_overlay_viewport_rect(insertion).top() == 14.0
    assert owner.insertion_overlay_document_rect(insertion).top() == 20.0
    assert owner.deletion_overlay_viewport_rects(deletion)[0].top() == 14.0
    assert owner.deletion_overlay_erase_rects(deletion)
