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

"""Apply source-local projection documents to the active layout frame."""

from __future__ import annotations

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)

from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .incremental_edit_contracts import (
    PromptProjectionIncrementalEdit,
    PromptProjectionPlainTextApplyResult,
    PromptProjectionPlainTextApplyStatus,
)
from .plain_text_document_editor import PromptPlainTextDocumentEditor
from .session import PromptProjectionSession


class PromptIncrementalLayoutEditor:
    """Coordinate one accepted source-local document edit with layout."""

    def __init__(
        self,
        document_editor: PromptPlainTextDocumentEditor | None = None,
    ) -> None:
        """Store the source-local document owner."""

        self._document_editor = document_editor or PromptPlainTextDocumentEditor()

    def try_apply_plain_text_layout_edit(
        self,
        edit: PromptProjectionIncrementalEdit,
        *,
        layout: PromptLayoutEditToFrameCoordinator,
        previous_document: PromptProjectionDocument,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        display_mode: PromptProjectionDisplayMode,
        session: PromptProjectionSession,
        active_span_range: tuple[int, int] | None,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
    ) -> PromptProjectionPlainTextApplyResult:
        """Apply a supported plain-text document edit to layout."""

        document_result = self._document_editor.try_build_plain_text_edit(
            edit,
            previous_document=previous_document,
            document_view=document_view,
            render_plan=render_plan,
            display_mode=display_mode,
            session=session,
            active_span_range=active_span_range,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
        )
        if document_result is None:
            return PromptProjectionPlainTextApplyResult(
                status=PromptProjectionPlainTextApplyStatus.REJECTED,
                rejection_reason=self._document_editor.last_rejection_reason,
            )

        if edit.replacement_text == "\n" or (
            edit.replacement_text == ""
            and edit.previous_source_text[edit.start : edit.end] == "\n"
        ):
            frame_result = layout.try_apply_hard_line_break_edit(
                document_result.projection_document,
                prompt_document_view=document_view,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
                first_dirty_projection_position=(
                    document_result.first_dirty_projection_position
                ),
            )
        else:
            frame_result = layout.try_apply_same_line_plain_text_edit(
                document_result.projection_document,
                prompt_document_view=document_view,
                edit_start=edit.start,
                edit_end=edit.end,
                replacement_text=edit.replacement_text,
                first_dirty_projection_position=(
                    document_result.first_dirty_projection_position
                ),
                editable_token_id=document_result.edited_token_id,
                projection_edit_start=document_result.projection_edit_start,
                projection_edit_end=document_result.projection_edit_end,
                projection_replacement_text=(
                    document_result.projection_replacement_text
                ),
            )
        if frame_result.damage is None:
            rejection_reason = frame_result.rejection_reason
            if rejection_reason in {"edit_would_wrap", "word_wrap_boundary"}:
                return PromptProjectionPlainTextApplyResult(
                    status=PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW,
                    projection_document=document_result.projection_document,
                    rejection_reason=rejection_reason,
                )
            return PromptProjectionPlainTextApplyResult(
                status=PromptProjectionPlainTextApplyStatus.REJECTED,
                projection_document=document_result.projection_document,
                rejection_reason=rejection_reason,
            )

        return PromptProjectionPlainTextApplyResult(
            status=PromptProjectionPlainTextApplyStatus.APPLIED,
            projection_document=document_result.projection_document,
            layout_result=frame_result.damage,
        )


__all__ = ["PromptIncrementalLayoutEditor"]
