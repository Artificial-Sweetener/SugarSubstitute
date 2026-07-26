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

"""Execute bounded trailing document and layout transitions."""

from __future__ import annotations

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
from substitute.shared.diagnostics.prompt_editor_work import PromptEditorWorkEvent
from substitute.shared.diagnostics.prompt_editor_work import (
    prompt_editor_work_result_event,
)

from .applicator import PromptProjectionApplicator
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .render_plan_ranges import projection_affecting_render_plan_ranges
from .trailing_document_editor import PromptTrailingDocumentEditor


PromptTrailingEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


def _applied_trailing_event(
    result: PromptProjectionDocument | None,
) -> PromptEditorWorkEvent | None:
    """Record the configured event only for an accepted transition."""

    return (
        PromptEditorWorkEvent.PROJECTION_FAST_INSERT_APPLIED
        if result is not None
        else None
    )


def _applied_trailing_newline_event(
    result: PromptProjectionDocument | None,
) -> PromptEditorWorkEvent | None:
    """Record the newline event only for an accepted transition."""

    return (
        PromptEditorWorkEvent.PROJECTION_FAST_NEWLINE_APPLIED
        if result is not None
        else None
    )


def _applied_trailing_delete_event(
    result: PromptProjectionDocument | None,
) -> PromptEditorWorkEvent | None:
    """Record the deletion event only for an accepted transition."""

    return (
        PromptEditorWorkEvent.PROJECTION_FAST_DELETE_APPLIED
        if result is not None
        else None
    )


class PromptTrailingEditStrategy:
    """Own trailing edit eligibility, document construction, and frame transition."""

    def __init__(
        self,
        *,
        applicator: PromptProjectionApplicator,
        editor_state: PromptTrailingEditorState,
        layout: PromptLayoutEditToFrameCoordinator,
    ) -> None:
        """Store concrete lower-level owners used by trailing transitions."""

        self._applicator = applicator
        self._editor_state = editor_state
        self._layout = layout
        self._document_editor = PromptTrailingDocumentEditor()

    def can_apply_prompt_state_insert(
        self,
        render_plan: PromptSyntaxRenderPlan,
        *,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Return whether semantic catch-up may reuse trailing insert geometry."""

        if (
            render_plan.document_semantics_identity
            != previous_render_plan.document_semantics_identity
        ):
            return False
        render_ranges = projection_affecting_render_plan_ranges(render_plan)
        previous_render_ranges = projection_affecting_render_plan_ranges(
            previous_render_plan
        )
        if (
            render_plan.syntax_spans == previous_render_plan.syntax_spans
            and render_ranges == previous_render_ranges
        ):
            return True
        return len(render_ranges) <= len(self._editor_state.projection.document.tokens)

    @prompt_editor_work_result_event(_applied_trailing_event)
    def try_plain_insert(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
    ) -> PromptProjectionDocument | None:
        """Try one trailing plain-text insertion through the trailing engine."""

        previous_document = self._editor_state.projection.document
        previous_text = previous_document.source_text
        if self._applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            document_view.source_text,
            start=len(previous_text),
            end=len(previous_text),
        ):
            return None
        next_document = self._document_editor.plain_insert(
            previous_document=previous_document,
            next_text=document_view.source_text,
            render_plan=render_plan,
        )
        if next_document is None or not self._layout.try_apply_trailing_plain_insert(
            next_document,
            prompt_document_view=document_view,
        ):
            return None
        return next_document

    @prompt_editor_work_result_event(_applied_trailing_newline_event)
    def try_newline_insert(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        previous_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Try one trailing hard-line insertion through the trailing engine."""

        if self._applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            document_view.source_text,
            start=start,
            end=end,
        ):
            return None
        next_document = self._document_editor.newline_insert(
            previous_document=self._editor_state.projection.document,
            previous_text=previous_text,
            next_text=document_view.source_text,
            start=start,
            end=end,
            render_plan=render_plan,
        )
        if next_document is None or not self._layout.try_apply_trailing_newline_insert(
            next_document,
            prompt_document_view=document_view,
        ):
            return None
        return next_document

    @prompt_editor_work_result_event(_applied_trailing_delete_event)
    def try_plain_delete(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Try one trailing plain-text deletion through the trailing engine."""

        if self._applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            next_text,
            start=start,
            end=end,
        ):
            return None
        previous_document = self._editor_state.projection.document
        next_document = self._document_editor.plain_delete(
            previous_document=previous_document,
            previous_text=previous_text,
            next_text=next_text,
            start=start,
            end=end,
        )
        if next_document is None:
            return None
        if not self._layout.try_apply_trailing_plain_delete(
            next_document,
            prompt_document_view=self._editor_state.edit_semantic.document,
        ):
            return None
        return next_document

    @prompt_editor_work_result_event(_applied_trailing_newline_event)
    def try_newline_delete(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
    ) -> PromptProjectionDocument | None:
        """Try one trailing hard-line deletion through the trailing engine."""

        if self._applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            next_text,
            start=start,
            end=end,
        ):
            return None
        next_document = self._document_editor.newline_delete(
            previous_document=self._editor_state.projection.document,
            previous_text=previous_text,
            next_text=next_text,
            start=start,
            end=end,
        )
        if next_document is None or not self._layout.try_apply_trailing_newline_delete(
            next_document,
            prompt_document_view=self._editor_state.edit_semantic.document,
        ):
            return None
        return next_document


__all__ = ["PromptTrailingEditStrategy"]
