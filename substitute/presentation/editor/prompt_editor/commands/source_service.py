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

"""Own local and host-facing prompt source replacement commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)

from ..core.editing.source_commands import (
    PromptSourceEditOrigin,
    PromptSourceNormalizer,
)
from ..core.state.revisions import PromptSourceIdentity
from .contracts import (
    PromptCommandResult,
    PromptCommandSourceRange,
    PromptCommandTextReplacement,
    PromptEditApplicationState,
)
from .execution import PromptEditExecution

TPayload = TypeVar("TPayload")


class PromptSourceCommandService(Generic[TPayload]):
    """Commit source replacement requests through one editing execution owner."""

    def __init__(
        self,
        *,
        execution: PromptEditExecution[TPayload],
        normalizer: PromptSourceNormalizer,
        exact_source_enabled: Callable[[], bool],
    ) -> None:
        """Store source command policy and its authoritative execution owner."""

        self._execution = execution
        self._normalizer = normalizer
        self._exact_source_enabled = exact_source_enabled

    @property
    def execution(self) -> PromptEditExecution[TPayload]:
        """Return the editing execution owner used by feature command services."""

        return self._execution

    def source_identity(self) -> PromptSourceIdentity:
        """Return the live source identity for prepared feature requests."""

        return self._execution.session.source_identity

    def normalized_paste_text(self, text: str) -> str:
        """Return the exact source text a literal paste would commit."""

        if self._exact_source_enabled():
            return text
        return self._normalizer.normalize_for_storage(text).text

    def set_plain_text(self, text: str) -> None:
        """Replace source with normalized text and reset the viewport origin."""

        self._replace_document_source(
            text,
            cursor_position=len(text),
            anchor_position=len(text),
            exact_source=False,
            record_undo=True,
            clear_history=False,
            reason="set_plain_text",
            prepared_state=PromptEditApplicationState(reset_scroll_to_top=True),
        )

    def set_source_text(self, text: str) -> None:
        """Replace source exactly and reset the viewport origin."""

        self._replace_document_source(
            text,
            cursor_position=len(text),
            anchor_position=len(text),
            exact_source=True,
            record_undo=True,
            clear_history=False,
            reason="set_source_text",
            prepared_state=PromptEditApplicationState(reset_scroll_to_top=True),
        )

    def replace_baseline_text(self, text: str, *, exact_source: bool = False) -> None:
        """Replace loaded source and make it the new undo baseline."""

        self._replace_document_source(
            text,
            cursor_position=len(text),
            anchor_position=len(text),
            exact_source=exact_source,
            record_undo=False,
            clear_history=True,
            reason="replace_baseline_text",
            prepared_state=PromptEditApplicationState(reset_scroll_to_top=True),
        )

    def replace_document_text(self, text: str) -> None:
        """Replace document text while preserving current selection bounds."""

        self.replace_document_text_with_prompt_state(
            text,
            document_view=None,
            render_plan=None,
        )

    def replace_document_text_with_prompt_state(
        self,
        text: str,
        *,
        document_view: PromptDocumentView | None,
        render_plan: PromptSyntaxRenderPlan | None,
    ) -> None:
        """Replace document text with optional already-built semantic state."""

        reason = (
            "replace_document_text"
            if document_view is None or render_plan is None
            else "replace_document_text_with_prompt_state"
        )
        session = self._execution.session
        application_state = PromptEditApplicationState(
            document_view=document_view,
            render_plan=render_plan,
            schedule_geometry_reuse_warm_reason=(
                "replace_document_text_with_prompt_state"
            ),
        )
        self._execution.finish_pending_key_edit_block(reason=reason)
        self._execution.begin_edit_block()
        try:
            self._execution.replace_document(
                text=text,
                cursor_position=min(session.cursor_position, len(text)),
                anchor_position=min(session.anchor_position, len(text)),
                normalizer=self._normalizer,
                exact_source=self._exact_source_enabled(),
                record_undo=False,
                clear_history=False,
                prepared_state=application_state,
            )
        finally:
            self._execution.end_edit_block()

    def execute_source_replacement(
        self,
        replacement: PromptCommandTextReplacement,
        *,
        command_name: str,
        finish_pending_key_edits: bool = False,
    ) -> PromptCommandResult[TPayload]:
        """Commit one prepared replacement with an explicit coalescing boundary."""

        if finish_pending_key_edits:
            self._execution.finish_pending_key_edit_block(reason=command_name)
        commit = self._execution.replace_range(
            start=replacement.source_range.start,
            end=replacement.source_range.end,
            replacement_text=replacement.replacement_text,
            normalizer=self._normalizer,
            origin=replacement.origin,
            exact_source=replacement.exact_source,
            record_undo=replacement.record_undo,
            cursor_position=replacement.cursor_position,
            anchor_position=replacement.anchor_position,
        )
        return PromptCommandResult.from_edit_commit(command_name, commit)

    def replace_source_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str = "replace_source_range",
        record_undo: bool = True,
        finish_pending_key_edits: bool = False,
    ) -> PromptCommandResult[TPayload]:
        """Commit one viewport-local source range replacement."""

        return self.execute_source_replacement(
            PromptCommandTextReplacement(
                source_range=PromptCommandSourceRange(start=start, end=end),
                replacement_text=replacement_text,
                origin=origin,
                exact_source=self._exact_source_enabled(),
                record_undo=record_undo,
            ),
            command_name=command_name,
            finish_pending_key_edits=finish_pending_key_edits,
        )

    def _replace_document_source(
        self,
        text: str,
        *,
        cursor_position: int,
        anchor_position: int,
        exact_source: bool,
        record_undo: bool,
        clear_history: bool,
        reason: str,
        prepared_state: PromptEditApplicationState,
    ) -> None:
        """Commit one complete source replacement with explicit history policy."""

        self._execution.finish_pending_key_edit_block(reason=reason)
        self._execution.replace_document(
            text=text,
            cursor_position=cursor_position,
            anchor_position=anchor_position,
            normalizer=self._normalizer,
            exact_source=exact_source,
            record_undo=record_undo,
            clear_history=clear_history,
            prepared_state=prepared_state,
        )


__all__ = ["PromptSourceCommandService"]
