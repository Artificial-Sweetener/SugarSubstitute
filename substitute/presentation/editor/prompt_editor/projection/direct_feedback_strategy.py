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

"""Publish bounded single-character feedback without generalized fallback work."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)

from .edit_pipeline_contracts import PromptProjectionSourceChangeApplyRequest
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .freshness_controller import PromptProjectionFreshnessController
from .transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)

PromptDirectFeedbackEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptDirectFeedbackContext(Protocol):
    """Expose current caret geometry and bounded feedback repaint effects."""

    def _current_caret_document_rect(self) -> QRectF:
        """Return the committed document-local caret rectangle."""

    def _update_transient_insertion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientInsertionOverlay | None,
        next_overlay: PromptProjectionTransientInsertionOverlay | None,
    ) -> None:
        """Repaint changed transient insertion feedback."""

    def _update_transient_deletion_overlay_paint(
        self,
        previous_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_overlay: PromptProjectionTransientDeletionOverlay | None,
    ) -> None:
        """Repaint changed transient deletion feedback."""


class PromptDirectFeedbackStrategy:
    """Own the allocation-bounded feedback path for approved plain typing."""

    def __init__(
        self,
        context: PromptDirectFeedbackContext,
        *,
        editor_state: PromptDirectFeedbackEditorState,
        freshness: PromptProjectionFreshnessController,
        layout: PromptLayoutEditToFrameCoordinator,
        overlays: PromptProjectionTransientEditOverlayController,
    ) -> None:
        """Store explicit state, freshness, geometry, and overlay owners."""

        self._context = context
        self._editor_state = editor_state
        self._freshness = freshness
        self._layout = layout
        self._overlays = overlays

    def try_defer_direct(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> bool:
        """Publish already-approved single-character feedback."""

        if not request.direct_deferred_feedback_allowed:
            return False
        start = request.source_edit_start
        end = request.source_edit_end
        replacement_text = request.source_edit_replacement_text
        assert start is not None
        assert end is not None
        assert replacement_text is not None
        source_identity = self._editor_state.source_identity
        committed_source_identity = (
            self._freshness.transient_fallback_committed_source_identity(
                current_source_identity=source_identity
            )
        )
        caret_rect = self._context._current_caret_document_rect()
        caret_geometry = self._overlays.single_character_edit_caret_geometry(
            start=start,
            end=end,
            replacement_text=replacement_text,
            cursor_position=request.next_cursor_state.source_position,
            anchor_position=request.next_anchor_state.source_position,
            source_identity=source_identity,
            committed_source_identity=committed_source_identity,
            current_caret_document_rect=caret_rect,
            metrics=self._layout.frame.output.configuration.metrics,
            projection_document=self._editor_state.projection.document,
            caret_navigation=self._layout.frame.geometry.caret,
        )
        insertion_overlay = self._overlays.single_character_insertion_overlay(
            start=start,
            replacement_text=replacement_text,
            source_identity=source_identity,
            committed_source_identity=committed_source_identity,
            current_caret_document_rect=caret_rect,
            freshness_is_stale_safe=self._freshness.has_stale_projection_geometry(),
            previous_source_identity=request.previous_source_identity,
        )
        previous_insertion_overlay = self._overlays.insertion_overlay
        self._overlays.set_overlays(
            caret_geometry=caret_geometry,
            insertion_overlay=insertion_overlay,
            deletion_overlay=None,
        )
        self._context._update_transient_insertion_overlay_paint(
            previous_insertion_overlay,
            insertion_overlay,
        )
        self._context._update_transient_deletion_overlay_paint(
            request.previous_deletion_overlay,
            None,
        )
        return True


__all__ = [
    "PromptDirectFeedbackContext",
    "PromptDirectFeedbackStrategy",
]
