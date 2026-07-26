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

"""Execute one prepared source edit through the projection pipeline."""

from __future__ import annotations

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)

from ..layout.checkpoints import PromptProjectionLayoutCheckpoint
from .edit_pipeline import PromptEditPipeline
from .edit_pipeline_contracts import PromptProjectionSourceChangeApplyRequest
from .edit_strategy import source_edit_kind
from .freshness_controller import (
    ProjectionFreshness,
    PromptProjectionFreshnessController,
)
from .observability import log_projection_timing, projection_observability_started_at
from .source_commit_ports import (
    PromptSourceChangeCaretSink,
    PromptSourceChangeEffectSink,
)
from .source_edit_projection_policy import PromptSourceEditProjectionDecision
from .transient_edit_overlays import (
    PromptProjectionTransientDeletionOverlay,
    PromptProjectionTransientEditOverlayController,
)

PromptSourceProjectionEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptSourceProjectionApplication:
    """Own pipeline request execution and its source-caret publication."""

    def __init__(
        self,
        effect_sink: PromptSourceChangeEffectSink,
        caret_sink: PromptSourceChangeCaretSink,
        *,
        editor_state: PromptSourceProjectionEditorState,
        freshness: PromptProjectionFreshnessController,
        pipeline: PromptEditPipeline,
        overlays: PromptProjectionTransientEditOverlayController,
    ) -> None:
        """Store explicit projection state, pipeline, and caret owners."""

        self._effect_sink = effect_sink
        self._caret_sink = caret_sink
        self._editor_state = editor_state
        self._freshness = freshness
        self._pipeline = pipeline
        self._overlays = overlays

    def apply(
        self,
        *,
        text: str,
        previous_source_text: str | None,
        previous_source_identity: PromptSourceIdentity,
        source_edit_start: int | None,
        source_edit_end: int | None,
        source_edit_replacement_text: str | None,
        previous_projection_freshness: ProjectionFreshness,
        previous_document_view: PromptDocumentView,
        previous_render_plan: PromptSyntaxRenderPlan,
        previous_deletion_overlay: PromptProjectionTransientDeletionOverlay | None,
        next_cursor_state: PromptProjectionCaretState,
        next_anchor_state: PromptProjectionCaretState,
        can_preserve_diagnostic_fragment_cache: bool,
        projection_deferral_reason: str,
        authoritative_semantic_current_before_edit: bool,
        region_structure_requires_rebuild: bool = False,
        restore_checkpoint: PromptProjectionLayoutCheckpoint | None = None,
        projection_decision: PromptSourceEditProjectionDecision | None = None,
    ) -> None:
        """Apply one prepared edit through the authoritative projection pipeline."""

        projection_started_at = projection_observability_started_at()
        previous_projection_semantic = self._editor_state.projection_semantic
        previous_projection = self._editor_state.projection
        wrap_reflow_deferrable = bool(
            projection_decision is not None
            and projection_decision.wrap_reflow_deferrable
            and (
                projection_decision.can_defer_projection
                or authoritative_semantic_current_before_edit
                or previous_projection_freshness is ProjectionFreshness.STALE_SAFE
            )
        )
        deferred_plain_edit_extendable = bool(
            projection_decision is not None
            and source_edit_start is not None
            and source_edit_end is not None
            and wrap_reflow_deferrable
            and self._freshness.can_extend_deferred_plain_source_edit(
                previous_projection_freshness=previous_projection_freshness,
                start=source_edit_start,
                end=source_edit_end,
                replacement_text=source_edit_replacement_text or "",
                typed_character_requires_immediate_projection=(
                    projection_decision.typed_character_requires_projection
                ),
                syntax_sensitive_autocomplete_prefix=(
                    projection_decision.syntax_sensitive_prefix_deferrable
                ),
            )
        )
        try:
            outcome = self._pipeline.apply(
                PromptProjectionSourceChangeApplyRequest(
                    text=text,
                    previous_source_text=previous_source_text,
                    previous_source_identity=previous_source_identity,
                    source_edit_start=source_edit_start,
                    source_edit_end=source_edit_end,
                    source_edit_replacement_text=source_edit_replacement_text,
                    previous_projection_freshness=previous_projection_freshness,
                    previous_document_view=previous_document_view,
                    previous_render_plan=previous_render_plan,
                    next_document_view=self._editor_state.edit_semantic.document,
                    next_render_plan=self._editor_state.edit_semantic.render_plan,
                    previous_deletion_overlay=previous_deletion_overlay,
                    next_cursor_state=next_cursor_state,
                    next_anchor_state=next_anchor_state,
                    can_preserve_diagnostic_fragment_cache=(
                        can_preserve_diagnostic_fragment_cache
                    ),
                    projection_deferral_reason=projection_deferral_reason,
                    region_structure_requires_rebuild=(
                        region_structure_requires_rebuild
                    ),
                    edit_kind=source_edit_kind(
                        start=source_edit_start,
                        end=source_edit_end,
                        previous_source_text=previous_source_text,
                        replacement_text=source_edit_replacement_text,
                    ),
                    deferred_plain_edit_extendable=deferred_plain_edit_extendable,
                    wrap_reflow_deferrable=wrap_reflow_deferrable,
                    projection_decision=projection_decision,
                    restore_checkpoint=restore_checkpoint,
                    restore_checkpoint_blockers=(
                        None
                        if restore_checkpoint is None
                        else self._effect_sink._projection_freshness_blockers()
                    ),
                )
            )
        except Exception:
            self._editor_state.restore_projection(previous_projection)
            self._editor_state.restore_projection_semantic(previous_projection_semantic)
            raise
        if outcome.wrap_reflow_deferred:
            self._editor_state.restore_projection(previous_projection)
            self._editor_state.restore_projection_semantic(previous_projection_semantic)
        if not outcome.direct_feedback_applied:
            log_projection_timing(
                "source_change.immediate_projection",
                started_at=projection_started_at,
                text_length=len(text),
                apply_path=outcome.apply_path.value,
                fast_projection_applied=outcome.fast_projection_applied,
                wrap_reflow_deferred=outcome.wrap_reflow_deferred,
            )
        if outcome.direct_feedback_applied:
            self._apply_direct_deferred_caret_states(
                cursor_state=next_cursor_state,
                anchor_state=next_anchor_state,
            )
        elif outcome.wrap_reflow_deferred:
            self._caret_sink._set_deferred_source_caret_states(
                cursor_state=next_cursor_state,
                anchor_state=next_anchor_state,
            )
        else:
            self._caret_sink._set_caret_states(
                cursor_state=next_cursor_state,
                anchor_state=next_anchor_state,
                collapse_expanded_token=not outcome.fast_projection_applied,
                preserve_unmapped_source_positions=True,
                reason=(
                    "fast_source_replace"
                    if outcome.fast_projection_applied
                    else "immediate_source_replace"
                ),
            )

    def valid_transient_deletion_overlay(
        self,
    ) -> PromptProjectionTransientDeletionOverlay | None:
        """Return the current valid transient deletion overlay."""

        return self._overlays.valid_deletion_overlay(
            freshness_is_stale_safe=self._freshness.has_stale_projection_geometry(),
            source_identity=self._editor_state.source_identity,
        )

    def _apply_direct_deferred_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Publish caret state paired with direct transient edit feedback."""

        self._caret_sink._cursor_state = cursor_state
        self._caret_sink._anchor_state = anchor_state
        self._caret_sink._sync_editing_session_to_caret_states()
        self._caret_sink._caret_rect_override = None
        self._caret_sink._ensure_caret_visible()
        self._caret_sink._restart_caret_blink_cycle()


__all__ = ["PromptSourceProjectionApplication"]
