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

"""Own latest-wins source catch-up and transient stale-safe feedback."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)
from substitute.presentation.editor.prompt_editor.core.state.semantic_state import (
    PromptEditorSemanticSnapshot,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_result_event,
    prompt_editor_work_true_event,
)

from .edit_pipeline_contracts import PromptProjectionSourceChangeApplyRequest
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .freshness_controller import (
    PromptProjectionFreshnessBlockers,
    PromptProjectionFreshnessController,
)
from .source_line_chrome import PromptSourceLineChrome
from .transient_edit_overlays import (
    PromptProjectionTransientCaretGeometry,
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
    PromptProjectionTransientInsertionOverlay,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)

PromptDeferredFeedbackEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptDeferredFeedbackContext(Protocol):
    """Expose dynamic geometry queries and repaint effects for deferred feedback."""

    def viewport(self) -> QWidget:
        """Return the active projection viewport."""

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return current modes that can block deferred projection work."""

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


class PromptDeferredFeedbackStrategy:
    """Own deferred scheduling eligibility and transient overlay publication."""

    def __init__(
        self,
        context: PromptDeferredFeedbackContext,
        *,
        editor_state: PromptDeferredFeedbackEditorState,
        freshness: PromptProjectionFreshnessController,
        layout: PromptLayoutEditToFrameCoordinator,
        overlays: PromptProjectionTransientEditOverlayController,
        source_line_chrome: PromptSourceLineChrome,
    ) -> None:
        """Store explicit scheduling, frame, and overlay owners."""

        self._context = context
        self._editor_state = editor_state
        self._freshness = freshness
        self._layout = layout
        self._overlays = overlays
        self._source_line_chrome = source_line_chrome

    @prompt_editor_work_result_event(
        prompt_editor_work_true_event(PromptEditorWorkEvent.PROJECTION_WRAP_DEFERRED)
    )
    def defer_wrap(
        self,
        *,
        previous_document_view: PromptDocumentView,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Schedule one wrap-only source catch-up off the keypress lane."""

        if not self._freshness.can_defer_wrap_reflow_projection_update(
            self._context._projection_freshness_blockers()
        ):
            return False
        self._freshness.schedule_provisional_safe_typing_update(
            snapshot=self._editor_state.edit_semantic,
            previous_snapshot=PromptEditorSemanticSnapshot(
                identity=self._editor_state.projection.identity.semantic,
                document=previous_document_view,
                render_plan=previous_render_plan,
            ),
            source_revision=self._editor_state.source.source_revision,
        )
        return True

    @prompt_editor_work_result_event(
        prompt_editor_work_true_event(
            PromptEditorWorkEvent.PROJECTION_FALLBACK_DEFERRED,
        )
    )
    def try_defer_fallback(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> bool:
        """Schedule safe catch-up and publish provisional edit feedback."""

        if not self.can_defer_fallback(request):
            return False
        if not self.defer_wrap(
            previous_document_view=request.previous_document_view,
            previous_render_plan=request.previous_render_plan,
        ):
            return False
        self._publish_feedback(request)
        return True

    def _publish_feedback(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> None:
        """Publish generalized provisional feedback after strategy fallback."""

        previous_insertion_overlay = self._overlays.insertion_overlay
        caret_geometry = self._fallback_caret_geometry(request)
        insertion_overlay = self._fallback_insertion_overlay(request)
        deletion_overlay = self._fallback_deletion_overlay(request)
        self._overlays.set_overlays(
            caret_geometry=caret_geometry,
            insertion_overlay=insertion_overlay,
            deletion_overlay=deletion_overlay,
        )
        self._context._update_transient_insertion_overlay_paint(
            previous_insertion_overlay,
            insertion_overlay,
        )
        self._context._update_transient_deletion_overlay_paint(
            request.previous_deletion_overlay,
            deletion_overlay,
        )

    def can_defer_fallback(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> bool:
        """Return whether one failed immediate edit may become stale-safe."""

        decision = request.projection_decision
        replacement_text = request.source_edit_replacement_text
        start = request.source_edit_start
        end = request.source_edit_end
        can_defer, _reason = (
            self._freshness.can_defer_immediate_projection_fallback_edit(
                blockers=self._context._projection_freshness_blockers(),
                previous_text=request.previous_source_text,
                next_text=request.text,
                start=start,
                end=end,
                replacement_text=replacement_text,
                projection_deferral_reason=request.projection_deferral_reason,
                insertion_inside_projected_token=bool(
                    decision is not None and decision.insertion_inside_projected_token
                ),
                deletion_intersects_projected_token=bool(
                    decision is not None
                    and decision.deletion_intersects_projected_token
                ),
                transient_insertion_overlay_deferrable=bool(
                    start is not None
                    and end is not None
                    and replacement_text not in {None, ""}
                    and self._can_defer_insertion_overlay(
                        start=start,
                        end=end,
                        replacement_text=replacement_text or "",
                        previous_source_identity=request.previous_source_identity,
                    )
                ),
                typed_character_requires_immediate_projection=(
                    request.typed_character_requires_immediate_projection
                ),
                syntax_sensitive_autocomplete_prefix=(
                    request.syntax_sensitive_prefix_deferrable
                ),
            )
        )
        return can_defer

    def _committed_source_identity(self) -> PromptSourceIdentity:
        """Return committed source identity for fallback overlay estimates."""

        return self._freshness.transient_fallback_committed_source_identity(
            current_source_identity=self._editor_state.source_identity
        )

    def _content_right(self) -> float:
        """Return the document-local right edge used by transient feedback."""

        content_width = self._layout.frame.output.snapshot.content_size.width()
        if content_width > 1.0:
            return content_width
        return float(self._context.viewport().width())

    def _fallback_caret_geometry(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionTransientCaretGeometry | None:
        """Return provisional caret geometry while catch-up is pending."""

        configuration = self._layout.frame.output.configuration
        return self._overlays.fallback_caret_geometry_for_edit(
            start=request.source_edit_start,
            end=request.source_edit_end,
            replacement_text=request.source_edit_replacement_text,
            cursor_state=request.next_cursor_state,
            anchor_state=request.next_anchor_state,
            source_identity=self._editor_state.source_identity,
            committed_source_identity=self._committed_source_identity(),
            current_caret_document_rect=(self._context._current_caret_document_rect()),
            metrics=configuration.metrics,
            content_right=self._content_right(),
            document_margin=configuration.document_margin,
            source_line_content_left_inset=(
                self._source_line_chrome.content_left_inset
            ),
            projection_document=self._editor_state.projection.document,
            caret_navigation=self._layout.frame.geometry.caret,
        )

    def _fallback_insertion_overlay(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionTransientInsertionOverlay | None:
        """Return provisional inserted text while catch-up is pending."""

        configuration = self._layout.frame.output.configuration
        return self._overlays.fallback_insertion_overlay_for_edit(
            start=request.source_edit_start,
            end=request.source_edit_end,
            replacement_text=request.source_edit_replacement_text,
            source_identity=self._editor_state.source_identity,
            committed_source_identity=self._committed_source_identity(),
            current_caret_document_rect=(self._context._current_caret_document_rect()),
            metrics=configuration.metrics,
            content_right=self._content_right(),
            document_margin=configuration.document_margin,
            source_line_content_left_inset=(
                self._source_line_chrome.content_left_inset
            ),
            freshness_is_stale_safe=self._freshness.has_stale_projection_geometry(),
            previous_source_identity=request.previous_source_identity,
        )

    def _fallback_deletion_overlay(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return provisional erase geometry while catch-up is pending."""

        viewport = self._context.viewport()
        return self._overlays.fallback_deletion_overlay_for_edit(
            start=request.source_edit_start,
            end=request.source_edit_end,
            replacement_text=request.source_edit_replacement_text,
            source_identity=self._editor_state.source_identity,
            committed_source_identity=self._committed_source_identity(),
            previous_overlay=request.previous_deletion_overlay,
            content_size=self._layout.frame.output.snapshot.content_size,
            selection_geometry=self._layout.frame.geometry.selection,
            viewport_width=float(viewport.width()),
            viewport_height=float(viewport.height()),
        )

    def _can_defer_insertion_overlay(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        previous_source_identity: PromptSourceIdentity,
    ) -> bool:
        """Return whether insertion feedback fits current committed geometry."""

        return self._overlays.can_defer_insertion_overlay(
            start=start,
            end=end,
            replacement_text=replacement_text,
            live_source_length=len(
                self._editor_state.edit_semantic.document.source_text
            ),
            committed_source_length=len(
                self._editor_state.projection.document.source_text
            ),
            caret_rect=self._context._current_caret_document_rect(),
            content_right=self._content_right(),
            metrics=self._layout.frame.output.configuration.metrics,
            freshness_is_stale_safe=self._freshness.has_stale_projection_geometry(),
            source_identity=previous_source_identity,
        )


__all__ = [
    "PromptDeferredFeedbackContext",
    "PromptDeferredFeedbackStrategy",
]
