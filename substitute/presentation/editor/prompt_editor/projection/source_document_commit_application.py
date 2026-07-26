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

"""Prepare and apply complete-document source commits."""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from PySide6.QtWidgets import QScrollBar

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.commands.contracts import (
    PromptEditApplicationState,
)
from substitute.presentation.editor.prompt_editor.core.editing.commit import (
    PromptEditCommit,
)

from .semantic_remap import PromptProjectionOptimisticPromptState
from .source_change_transaction import PromptProjectionSourceChangeTransaction
from .source_commit_ports import PromptSourceChangeCaretSink

TProjectionPayload = TypeVar("TProjectionPayload")


class PromptSourceDocumentCommitEffectSink(Protocol):
    """Expose document-wide viewport effects outside source state."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the active vertical scrollbar."""

    def _schedule_projection_geometry_reuse_warm(self, *, reason: str) -> None:
        """Schedule geometry reuse warmup."""


class PromptSourceDocumentCommitApplication(Generic[TProjectionPayload]):
    """Own prepared-state handling for complete-document commits."""

    def __init__(
        self,
        effect_sink: PromptSourceDocumentCommitEffectSink,
        caret_sink: PromptSourceChangeCaretSink,
        *,
        transaction: PromptProjectionSourceChangeTransaction[TProjectionPayload],
    ) -> None:
        """Store explicit document-effect, caret, and transaction owners."""

        self._effect_sink = effect_sink
        self._caret_sink = caret_sink
        self._transaction = transaction

    def apply(self, commit: PromptEditCommit[TProjectionPayload]) -> None:
        """Apply one complete-document commit and its explicit viewport intent."""

        application_state = self._edit_application_state(commit.prepared_state)
        source_edit = commit.source_edit
        prepared_prompt_state = self._projection_prompt_state(application_state)
        if not commit.source_changed and prepared_prompt_state is None:
            self._caret_sink.set_cursor_positions(
                cursor_position=commit.cursor_state.cursor_position,
                anchor_position=commit.cursor_state.anchor_position,
            )
        else:
            self._transaction.apply(
                commit,
                emit_text_changed=commit.source_changed,
                optimistic_prompt_state=prepared_prompt_state,
                source_edit_start=None if source_edit is None else source_edit.start,
                source_edit_end=None if source_edit is None else source_edit.end,
                source_edit_replacement_text=(
                    None if source_edit is None else source_edit.replacement_text
                ),
                previous_source_text=commit.previous_snapshot.source_text,
                origin=commit.origin,
            )
        if application_state is not None and application_state.reset_scroll_to_top:
            self._effect_sink.verticalScrollBar().setValue(0)
        if (
            application_state is not None
            and application_state.schedule_geometry_reuse_warm_reason is not None
        ):
            self._effect_sink._schedule_projection_geometry_reuse_warm(
                reason=application_state.schedule_geometry_reuse_warm_reason
            )

    @staticmethod
    def _edit_application_state(
        value: object | None,
    ) -> PromptEditApplicationState | None:
        """Narrow optional presentation state attached to a document commit."""

        return value if isinstance(value, PromptEditApplicationState) else None

    @staticmethod
    def _projection_prompt_state(
        application_state: PromptEditApplicationState | None,
    ) -> PromptProjectionOptimisticPromptState | None:
        """Return projection-typed semantic state from prepared presentation data."""

        if application_state is None:
            return None
        document_view = application_state.document_view
        render_plan = application_state.render_plan
        if not isinstance(document_view, PromptDocumentView):
            return None
        if not isinstance(render_plan, PromptSyntaxRenderPlan):
            return None
        return document_view, render_plan


__all__ = [
    "PromptSourceDocumentCommitApplication",
    "PromptSourceDocumentCommitEffectSink",
]
