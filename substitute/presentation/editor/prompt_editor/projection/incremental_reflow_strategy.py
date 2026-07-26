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

"""Execute incremental and bounded canonical source-edit reflow strategies."""

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
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_result_event,
)

from .applicator import PromptProjectionApplicator
from .canonical_edit_reflow import PromptProjectionCanonicalEditReflow
from .edit_pipeline_contracts import PromptProjectionSourceChangeApplyRequest
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .incremental_edit_contracts import (
    PromptProjectionIncrementalEdit,
    PromptProjectionPlainTextApplyResult,
    PromptProjectionPlainTextApplyStatus,
)
from .incremental_layout_editor import PromptIncrementalLayoutEditor
from .projection_build_context import PromptProjectionBuildContext

PromptIncrementalReflowEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


def _incremental_apply_work_event(
    result: PromptProjectionPlainTextApplyResult,
) -> PromptEditorWorkEvent:
    """Classify one incremental projection attempt for structural measurement."""

    if result.status in {
        PromptProjectionPlainTextApplyStatus.APPLIED,
        PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW,
    }:
        return PromptEditorWorkEvent.PROJECTION_INCREMENTAL_APPLIED
    if result.status is PromptProjectionPlainTextApplyStatus.DEFERRED_WRAP_REFLOW:
        return PromptEditorWorkEvent.PROJECTION_INCREMENTAL_DEFERRED
    return PromptEditorWorkEvent.PROJECTION_INCREMENTAL_REJECTED


class PromptIncrementalReflowStrategy:
    """Own local projection construction and edit-to-frame reflow attempts."""

    def __init__(
        self,
        context: PromptProjectionBuildContext,
        *,
        applicator: PromptProjectionApplicator,
        editor_state: PromptIncrementalReflowEditorState,
        layout: PromptLayoutEditToFrameCoordinator,
    ) -> None:
        """Store explicit mechanism owners and a narrow dynamic context."""

        self._context = context
        self._applicator = applicator
        self._editor_state = editor_state
        self._layout = layout
        self._incremental_editor = PromptIncrementalLayoutEditor()
        self._canonical_reflow = PromptProjectionCanonicalEditReflow(applicator)

    @prompt_editor_work_result_event(_incremental_apply_work_event)
    def try_incremental(
        self,
        *,
        previous_text: str,
        next_text: str,
        start: int,
        end: int,
        replacement_text: str,
    ) -> PromptProjectionPlainTextApplyResult:
        """Try one supported local edit and retain canonical recovery work."""

        if self._applicator.source_edit_requires_canonical_rebuild(
            previous_text,
            next_text,
            start=start,
            end=end,
        ):
            return PromptProjectionPlainTextApplyResult(
                status=PromptProjectionPlainTextApplyStatus.REJECTED,
                rejection_reason="projection_topology_requires_canonical_rebuild",
            )
        context = self._context
        result = self._incremental_editor.try_apply_plain_text_layout_edit(
            PromptProjectionIncrementalEdit(
                start=start,
                end=end,
                replacement_text=replacement_text,
                previous_source_text=previous_text,
                next_source_text=next_text,
            ),
            layout=self._layout,
            previous_document=self._editor_state.projection.document,
            document_view=self._editor_state.edit_semantic.document,
            render_plan=self._editor_state.edit_semantic.render_plan,
            display_mode=context._display_mode,
            session=context._session,
            active_span_range=None,
            decoration_accent_ranges=context._decoration_accent_ranges(),
            scene_error_keys=context._scene_error_keys,
        )
        if (
            result.status is PromptProjectionPlainTextApplyStatus.REJECTED
            and result.projection_document is not None
        ):
            return self._apply_prebuilt_reflow(
                result.projection_document,
                start=start,
                end=end,
                replacement_text=replacement_text,
                rejection_reason=result.rejection_reason,
            )
        return result

    def try_canonical(
        self,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionPlainTextApplyResult | None:
        """Try bounded canonical construction and edit-to-frame recovery."""

        start = request.source_edit_start
        end = request.source_edit_end
        previous_text = request.previous_source_text
        if start is None or end is None or previous_text is None:
            return None
        context = self._context
        projection_document = self._canonical_reflow.try_build_document(
            previous_document=self._editor_state.projection.document,
            previous_source_text=previous_text,
            document_view=request.next_document_view,
            render_plan=request.next_render_plan,
            start=start,
            end=end,
            replacement_text=request.source_edit_replacement_text or "",
            blockers=context._projection_freshness_blockers(),
            session=context._session,
            decoration_accent_ranges=context._decoration_accent_ranges(),
            scene_error_keys=context._scene_error_keys,
        )
        if projection_document is None:
            return None
        return self._apply_prebuilt_reflow(
            projection_document,
            start=start,
            end=end,
            replacement_text=request.source_edit_replacement_text or "",
        )

    def apply_prebuilt(
        self,
        result: PromptProjectionPlainTextApplyResult,
        request: PromptProjectionSourceChangeApplyRequest,
    ) -> PromptProjectionPlainTextApplyResult | None:
        """Apply a canonical document retained by a rejected speculative edit."""

        projection_document = result.projection_document
        start = request.source_edit_start
        end = request.source_edit_end
        if projection_document is None or start is None or end is None:
            return None
        return self._apply_prebuilt_reflow(
            projection_document,
            start=start,
            end=end,
            replacement_text=request.source_edit_replacement_text or "",
        )

    def _apply_prebuilt_reflow(
        self,
        projection_document: PromptProjectionDocument,
        *,
        start: int,
        end: int,
        replacement_text: str,
        rejection_reason: str = "",
    ) -> PromptProjectionPlainTextApplyResult:
        """Apply one already-validated canonical document to the active frame."""

        damage = self._layout.set_projection_after_source_edit(
            projection_document,
            prompt_document_view=self._editor_state.edit_semantic.document,
            edit_start=start,
            edit_end=end,
            replacement_text=replacement_text,
        )
        return PromptProjectionPlainTextApplyResult(
            status=PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW,
            projection_document=projection_document,
            layout_result=damage,
            rejection_reason=rejection_reason,
        )


__all__ = [
    "PromptIncrementalReflowStrategy",
]
