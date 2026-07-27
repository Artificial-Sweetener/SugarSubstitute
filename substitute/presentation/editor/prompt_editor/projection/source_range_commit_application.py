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

"""Prepare and apply committed source-range edits."""

from __future__ import annotations

from typing import Generic, TypeVar

from substitute.presentation.editor.prompt_editor.core.editing.commit import (
    PromptEditCommit,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)

from .semantic_remap import PromptProjectionSemanticRemapper
from .session import PromptProjectionSession
from .source_change_transaction import PromptProjectionSourceChangeTransaction
from .source_commit_ports import PromptSourceChangeCaretSink
from .source_edit_projection_facts import PromptSourceEditProjectionFactResolver

TProjectionPayload = TypeVar("TProjectionPayload")

PromptSourceRangeEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptSourceRangeCommitApplication(Generic[TProjectionPayload]):
    """Own range-edit semantic preparation before source publication."""

    def __init__(
        self,
        caret_sink: PromptSourceChangeCaretSink,
        *,
        editor_state: PromptSourceRangeEditorState,
        projection_facts: PromptSourceEditProjectionFactResolver,
        semantic_remapper: PromptProjectionSemanticRemapper,
        session: PromptProjectionSession,
        transaction: PromptProjectionSourceChangeTransaction[TProjectionPayload],
    ) -> None:
        """Store explicit caret, semantic, fact, session, and transaction owners."""

        self._caret_sink = caret_sink
        self._editor_state = editor_state
        self._projection_facts = projection_facts
        self._semantic_remapper = semantic_remapper
        self._session = session
        self._transaction = transaction

    @prompt_editor_work_event(PromptEditorWorkEvent.SURFACE_SOURCE_APPLY)
    def apply(
        self,
        commit: PromptEditCommit[TProjectionPayload],
    ) -> None:
        """Prepare one bounded range commit and publish it exactly once."""

        previous_text = commit.previous_snapshot.source_text
        if not commit.source_changed:
            self._caret_sink.set_cursor_positions(
                cursor_position=commit.cursor_state.cursor_position,
                anchor_position=commit.cursor_state.anchor_position,
            )
            return
        source_edit = commit.source_edit
        if source_edit is None:
            raise RuntimeError("Changed prompt source is missing its applied edit.")
        requested_start = commit.requested_start
        requested_end = commit.requested_end
        requested_replacement_text = commit.requested_replacement_text
        updated_text = (
            previous_text[:requested_start]
            + requested_replacement_text
            + previous_text[requested_end:]
        )
        start = source_edit.start
        end = source_edit.end
        replacement_text = source_edit.replacement_text
        region_structure_requires_rebuild = (
            self._semantic_remapper.region_structure_edit_requires_rebuild(
                current_document_view=self._editor_state.edit_semantic.document,
                previous_text=previous_text,
                next_text=commit.next_snapshot.source_text,
                start=start,
                end=end,
            )
        )
        projection_decision = self._projection_facts.resolve(
            start=start,
            end=end,
            replaced_text=previous_text[start:end],
            replacement_text=replacement_text,
            origin=commit.origin,
            previous_source_text=previous_text,
            updated_text=updated_text,
            normalized_text=commit.next_snapshot.source_text,
            region_structure_requires_rebuild=region_structure_requires_rebuild,
            cursor_state=self._caret_sink._cursor_state,
        )
        deferral_reason = projection_decision.deferral_reason
        optimistic_prompt_state = (
            self._semantic_remapper.optimistic_prompt_state_for_edit(
                current_document_view=self._editor_state.edit_semantic.document,
                current_render_plan=self._editor_state.edit_semantic.render_plan,
                previous_text=previous_text,
                next_text=commit.next_snapshot.source_text,
                start=start,
                end=end,
                replacement_text=replacement_text,
                region_structure_requires_rebuild=region_structure_requires_rebuild,
            )
            if not projection_decision.can_defer_projection
            and self._semantic_remapper.should_use_optimistic_prompt_state_for_immediate_edit(
                deferral_reason=deferral_reason,
            )
            else None
        )
        if optimistic_prompt_state is not None:
            self._session.expanded_source_range = (
                self._semantic_remapper.remap_expanded_source_range_for_edit(
                    self._session.expanded_source_range,
                    start=start,
                    end=end,
                    delta=len(replacement_text) - (end - start),
                )
            )
        self._transaction.apply(
            commit,
            emit_text_changed=True,
            optimistic_prompt_state=optimistic_prompt_state,
            source_edit_start=start,
            source_edit_end=end,
            source_edit_replacement_text=replacement_text,
            previous_source_text=previous_text,
            projection_deferral_reason=deferral_reason,
            origin=commit.origin,
            region_structure_requires_rebuild=region_structure_requires_rebuild,
            projection_decision=projection_decision,
        )


__all__ = ["PromptSourceRangeCommitApplication"]
