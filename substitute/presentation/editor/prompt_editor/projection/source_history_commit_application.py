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

"""Restore committed history source, semantic, caret, and projection state."""

from __future__ import annotations

from typing import Generic, TypeVar

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.editing.commit import (
    PromptEditCommit,
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
from .session import PromptProjectionSession
from .source_commit_ports import (
    PromptSourceChangeCaretSink,
    PromptSourceChangeEffectSink,
)
from .source_document import PromptProjectionSourceDocument
from .source_projection_application import PromptSourceProjectionApplication
from .source_text_edit import single_source_text_edit
from .undo_payload import PromptProjectionUndoPayload

TProjectionPayload = TypeVar("TProjectionPayload")

PromptSourceHistoryEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptSourceHistoryCommitApplication(Generic[TProjectionPayload]):
    """Own complete source-side restoration for history commits."""

    def __init__(
        self,
        effect_sink: PromptSourceChangeEffectSink,
        caret_sink: PromptSourceChangeCaretSink,
        *,
        editor_state: PromptSourceHistoryEditorState,
        freshness: PromptProjectionFreshnessController,
        projection_application: PromptSourceProjectionApplication,
        session: PromptProjectionSession,
        source_document: PromptProjectionSourceDocument,
    ) -> None:
        """Store explicit restoration state and publication owners."""

        self._effect_sink = effect_sink
        self._caret_sink = caret_sink
        self._editor_state = editor_state
        self._freshness = freshness
        self._projection_application = projection_application
        self._session = session
        self._source_document = source_document

    def apply(self, commit: PromptEditCommit[TProjectionPayload]) -> None:
        """Restore one complete source, selection, semantic, and frame snapshot."""

        state = commit.restored_undo_snapshot
        if state is None:
            raise RuntimeError("History commit is missing its restored undo snapshot.")
        payload = (
            state.restoration_payload
            if isinstance(state.restoration_payload, PromptProjectionUndoPayload)
            else None
        )
        previous_source_text = self._editor_state.projection.document.source_text
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
        source_edit = single_source_text_edit(previous_source_text, state.source_text)
        self._editor_state.publish_source(commit.next_snapshot)
        if (
            payload is not None
            and payload.document_view.source_text == state.source_text
        ):
            next_document_view = payload.document_view
            next_render_plan = payload.render_plan
        else:
            next_document_view = PromptDocumentView(
                source_text=state.source_text,
                segments=(),
                emphasis_spans=(),
                wildcard_spans=(),
                lora_spans=(),
                syntax_spans=(),
                region_structure=PromptRegionStructureView.empty(
                    len(state.source_text)
                ),
                has_trailing_comma=False,
            )
            next_render_plan = PromptSyntaxRenderPlan(
                syntax_spans=(),
                renderer_views=(),
                document_semantics_identity=(
                    self._editor_state.edit_semantic.render_plan.document_semantics_identity
                ),
            )
        next_projection_semantic = self._editor_state.prepare_semantic(
            next_document_view,
            next_render_plan,
            source_identity=self._editor_state.source_identity,
        )
        self._editor_state.stage_edit_semantic(next_projection_semantic)
        if payload is not None:
            self._caret_sink._cursor_state = payload.cursor_state
            self._caret_sink._anchor_state = payload.anchor_state
            self._caret_sink._sync_editing_session_to_caret_states()
            self._session.expanded_source_range = payload.expanded_source_range
        else:
            self._caret_sink._cursor_state = PromptProjectionCaretState(
                source_position=commit.cursor_state.cursor_position
            )
            self._caret_sink._anchor_state = PromptProjectionCaretState(
                source_position=commit.cursor_state.anchor_position
            )
            self._caret_sink._sync_editing_session_to_caret_states()
            self._session.expanded_source_range = None
        self._caret_sink._preferred_x = None
        self._caret_sink._caret_rect_override = None
        self._source_document.sync_default_font(self._effect_sink.font())
        self._source_document.replace_text(state.source_text)
        self._effect_sink._mark_source_text_changed(
            deferrable_projection=False,
            source_snapshot=commit.next_snapshot,
        )
        self._projection_application.apply(
            text=state.source_text,
            previous_source_text=previous_source_text,
            previous_source_identity=previous_source_identity,
            source_edit_start=None if source_edit is None else source_edit.start,
            source_edit_end=None if source_edit is None else source_edit.end,
            source_edit_replacement_text=(
                None if source_edit is None else source_edit.replacement_text
            ),
            previous_projection_freshness=previous_projection_freshness,
            previous_document_view=previous_document_view,
            previous_render_plan=previous_render_plan,
            previous_deletion_overlay=previous_deletion_overlay,
            next_cursor_state=self._caret_sink._cursor_state,
            next_anchor_state=self._caret_sink._anchor_state,
            can_preserve_diagnostic_fragment_cache=False,
            projection_deferral_reason="history_restore",
            authoritative_semantic_current_before_edit=(
                authoritative_semantic_current_before_edit
            ),
            restore_checkpoint=None if payload is None else payload.layout_checkpoint,
        )
        self._caret_sink._ensure_caret_visible()
        self._caret_sink._restart_caret_blink_cycle()
        self._effect_sink.textChanged.emit()
        self._effect_sink.cursorPositionChanged.emit()


__all__ = ["PromptSourceHistoryCommitApplication"]
