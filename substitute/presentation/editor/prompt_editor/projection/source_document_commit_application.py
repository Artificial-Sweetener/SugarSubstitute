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

from collections.abc import Callable
from typing import Generic, Protocol, TypeVar

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_models import (
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

TProjectionPayload = TypeVar("TProjectionPayload")


class PromptSourceDocumentScrollBar(Protocol):
    """Apply document-wide vertical scroll intent."""

    def setValue(self, value: int) -> None:  # noqa: N802
        """Set the vertical scroll position."""


class PromptSourceDocumentCommitApplication(Generic[TProjectionPayload]):
    """Own prepared-state handling for complete-document commits."""

    def __init__(
        self,
        scroll_bar: PromptSourceDocumentScrollBar,
        *,
        set_cursor_positions: Callable[[int, int], object],
        schedule_geometry_reuse_warm: Callable[[str], None],
        transaction: PromptProjectionSourceChangeTransaction[TProjectionPayload],
    ) -> None:
        """Store explicit scroll, caret, warmup, and transaction collaborators."""

        self._scroll_bar = scroll_bar
        self._set_cursor_positions = set_cursor_positions
        self._schedule_geometry_reuse_warm = schedule_geometry_reuse_warm
        self._transaction = transaction

    def apply(self, commit: PromptEditCommit[TProjectionPayload]) -> None:
        """Apply one complete-document commit and its explicit viewport intent."""

        application_state = self._edit_application_state(commit.prepared_state)
        source_edit = commit.source_edit
        prepared_prompt_state = self._projection_prompt_state(application_state)
        if not commit.source_changed and prepared_prompt_state is None:
            self._set_cursor_positions(
                commit.cursor_state.cursor_position,
                commit.cursor_state.anchor_position,
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
            self._scroll_bar.setValue(0)
        if (
            application_state is not None
            and application_state.schedule_geometry_reuse_warm_reason is not None
        ):
            self._schedule_geometry_reuse_warm(
                application_state.schedule_geometry_reuse_warm_reason
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
    "PromptSourceDocumentScrollBar",
]
