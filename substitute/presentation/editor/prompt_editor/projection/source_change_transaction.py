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

"""Apply one committed source change through semantic, mirror, and frame owners."""

from __future__ import annotations

from typing import Generic, TypeVar

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.editing.literal_parentheses import (
    PromptParenthesisTransitionKind,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.editing.commit import (
    PromptEditCommit,
)
from substitute.presentation.editor.prompt_editor.core.editing.source_commands import (
    PromptSourceEditOrigin,
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

from .freshness_controller import PromptProjectionFreshnessController
from .observability import log_projection_timing, projection_observability_started_at
from .semantic_remap import (
    PromptProjectionOptimisticPromptState,
    PromptProjectionSemanticRemapper,
)
from .session import PromptProjectionSession
from .source_commit_ports import (
    PromptSourceChangeEffectSink,
    PromptSourceReplacementPointerSink,
)
from .source_document import PromptProjectionSourceDocument
from .source_edit_projection_policy import PromptSourceEditProjectionDecision
from .source_projection_application import PromptSourceProjectionApplication

TProjectionPayload = TypeVar("TProjectionPayload")

PromptSourceChangeEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptProjectionSourceChangeTransaction(Generic[TProjectionPayload]):
    """Own the atomic source-to-semantic-to-frame publication transaction."""

    def __init__(
        self,
        effect_sink: PromptSourceChangeEffectSink,
        pointer_sink: PromptSourceReplacementPointerSink,
        *,
        editor_state: PromptSourceChangeEditorState,
        freshness: PromptProjectionFreshnessController,
        projection_application: PromptSourceProjectionApplication,
        semantic_remapper: PromptProjectionSemanticRemapper,
        session: PromptProjectionSession,
        source_document: PromptProjectionSourceDocument,
    ) -> None:
        """Store explicit state owners and focused surface effect sinks."""

        self._effect_sink = effect_sink
        self._pointer_sink = pointer_sink
        self._editor_state = editor_state
        self._freshness = freshness
        self._projection_application = projection_application
        self._semantic_remapper = semantic_remapper
        self._session = session
        self._source_document = source_document

    def apply(
        self,
        commit: PromptEditCommit[TProjectionPayload],
        *,
        emit_text_changed: bool,
        optimistic_prompt_state: PromptProjectionOptimisticPromptState | None = None,
        source_edit_start: int | None = None,
        source_edit_end: int | None = None,
        source_edit_replacement_text: str | None = None,
        previous_source_text: str | None = None,
        refresh_caret_after_prompt_state: bool = False,
        projection_deferral_reason: str = "",
        origin: PromptSourceEditOrigin = PromptSourceEditOrigin.PROGRAMMATIC,
        region_structure_requires_rebuild: bool | None = None,
        projection_decision: PromptSourceEditProjectionDecision | None = None,
    ) -> None:
        """Apply one prepared source commit through all authoritative owners."""

        effect_sink = self._effect_sink
        text = commit.next_snapshot.source_text
        cursor_position = commit.cursor_state.cursor_position
        anchor_position = commit.cursor_state.anchor_position
        previous_document_view = self._editor_state.edit_semantic.document
        previous_render_plan = self._editor_state.edit_semantic.render_plan
        previous_source_identity = self._editor_state.source_identity
        previous_projection_freshness = self._freshness.freshness
        authoritative_semantic_current_before_edit = (
            self._editor_state.semantic.identity.source
            is self._editor_state.source_identity
        )
        previous_deletion_overlay = (
            self._projection_application.valid_transient_deletion_overlay()
        )
        deferrable_projection = bool(
            projection_decision is not None and projection_decision.can_defer_projection
        )
        if self._session.autocomplete_preview is not None:
            effect_sink.clear_autocomplete_preview_state()
        can_preserve_diagnostic_fragment_cache = (
            previous_source_text is not None
            and source_edit_start is not None
            and source_edit_end is not None
            and source_edit_replacement_text is not None
            and source_edit_end - source_edit_start <= 1
            and len(source_edit_replacement_text) <= 1
        )
        effect_sink._mark_source_text_changed(
            deferrable_projection=deferrable_projection,
            source_snapshot=commit.next_snapshot,
            clear_diagnostic_fragment_cache=(
                not can_preserve_diagnostic_fragment_cache
            ),
        )
        if emit_text_changed and refresh_caret_after_prompt_state:
            effect_sink._caret_visibility_prompt_state_revision = (
                self._editor_state.source.source_revision
            )
        document_view_started_at = projection_observability_started_at()
        if optimistic_prompt_state is None:
            optimistic_prompt_state = (
                self._semantic_remapper.optimistic_prompt_state_for_source_edit(
                    current_document_view=self._editor_state.edit_semantic.document,
                    current_render_plan=self._editor_state.edit_semantic.render_plan,
                    previous_text=previous_source_text,
                    next_text=text,
                    start=source_edit_start,
                    end=source_edit_end,
                    replacement_text=source_edit_replacement_text,
                    region_structure_requires_rebuild=(
                        region_structure_requires_rebuild
                    ),
                )
            )
        if optimistic_prompt_state is None:
            next_document_view = PromptDocumentView(
                source_text=text,
                segments=(),
                emphasis_spans=(),
                wildcard_spans=(),
                lora_spans=(),
                syntax_spans=(),
                region_structure=PromptRegionStructureView.empty(len(text)),
                has_trailing_comma=False,
            )
            next_render_plan = PromptSyntaxRenderPlan(
                syntax_spans=(),
                renderer_views=(),
                document_semantics_identity=(
                    self._editor_state.edit_semantic.render_plan.document_semantics_identity
                ),
            )
        else:
            next_document_view, next_render_plan = optimistic_prompt_state
        next_projection_semantic = self._editor_state.prepare_semantic(
            next_document_view,
            next_render_plan,
            source_identity=self._editor_state.source_identity,
        )
        self._editor_state.stage_edit_semantic(next_projection_semantic)
        self._remap_diagnostics_for_source_edit(
            start=source_edit_start,
            end=source_edit_end,
            replacement_text=source_edit_replacement_text,
        )
        next_cursor_state = PromptProjectionCaretState(
            source_position=max(0, min(cursor_position, len(text)))
        )
        next_anchor_state = PromptProjectionCaretState(
            source_position=max(0, min(anchor_position, len(text)))
        )
        if any(
            transition.kind
            is PromptParenthesisTransitionKind.ESCAPED_LITERAL_TO_EMPHASIS
            for transition in commit.transitions
        ):
            self._session.set_pending_auto_exact_weight_edit(
                source_text=text,
                cursor_position=next_cursor_state.source_position,
            )
        if origin is PromptSourceEditOrigin.TYPED:
            authored_depth = max(
                (
                    transition.nesting_depth
                    for transition in commit.transitions
                    if transition.kind
                    is PromptParenthesisTransitionKind.IMPLICIT_EMPHASIS
                ),
                default=0,
            )
            if authored_depth >= 2:
                effect_sink.notify_implicit_parenthesis_authored(authored_depth)
        self._pointer_sink.clear_pointer_state_for_source_replacement()
        log_projection_timing(
            "source_change.prepare_document_view",
            started_at=document_view_started_at,
            text_length=len(text),
            emit_text_changed=emit_text_changed,
        )
        qtext_document_started_at = projection_observability_started_at()
        self._source_document.sync_default_font(effect_sink.font())
        self._source_document.replace_with_range_fallback(
            next_text=text,
            previous_text=previous_source_text,
            start=source_edit_start,
            end=source_edit_end,
            replacement_text=source_edit_replacement_text,
        )
        log_projection_timing(
            "source_change.qtext_document",
            started_at=qtext_document_started_at,
            text_length=len(text),
        )
        self._projection_application.apply(
            text=text,
            previous_source_text=previous_source_text,
            previous_source_identity=previous_source_identity,
            source_edit_start=source_edit_start,
            source_edit_end=source_edit_end,
            source_edit_replacement_text=source_edit_replacement_text,
            previous_projection_freshness=previous_projection_freshness,
            previous_document_view=previous_document_view,
            previous_render_plan=previous_render_plan,
            previous_deletion_overlay=previous_deletion_overlay,
            next_cursor_state=next_cursor_state,
            next_anchor_state=next_anchor_state,
            can_preserve_diagnostic_fragment_cache=(
                can_preserve_diagnostic_fragment_cache
            ),
            projection_deferral_reason=projection_deferral_reason,
            authoritative_semantic_current_before_edit=(
                authoritative_semantic_current_before_edit
            ),
            region_structure_requires_rebuild=bool(region_structure_requires_rebuild),
            projection_decision=projection_decision,
        )
        if source_edit_start is not None and source_edit_end is not None:
            effect_sink._mark_source_edit_horizontal_movement_origin()
        if emit_text_changed:
            effect_sink.textChanged.emit()
        effect_sink.cursorPositionChanged.emit()

    def _remap_diagnostics_for_source_edit(
        self,
        *,
        start: int | None,
        end: int | None,
        replacement_text: str | None,
    ) -> None:
        """Keep visible diagnostic ranges aligned with one local source edit."""

        if start is None or end is None or replacement_text is None:
            return
        if not self._session.diagnostics:
            return
        next_diagnostics = self._semantic_remapper.remap_diagnostics_for_edit(
            self._session.diagnostics,
            start=start,
            end=end,
            replacement_text=replacement_text,
        )
        if next_diagnostics == self._session.diagnostics:
            return
        self._session.set_diagnostics(next_diagnostics)


__all__ = [
    "PromptProjectionSourceChangeTransaction",
]
