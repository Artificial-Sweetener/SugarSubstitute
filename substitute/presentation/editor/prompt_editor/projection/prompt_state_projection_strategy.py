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

"""Apply prepared prompt-state snapshots through focused local strategies."""

from __future__ import annotations

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)

from .edit_publication import PromptEditPublication
from .incremental_reflow_strategy import PromptIncrementalReflowStrategy
from .incremental_edit_contracts import PromptProjectionPlainTextApplyStatus
from .render_plan_ranges import render_plan_ranges_match_after_source_edit
from .semantic_transition_strategy import PromptSemanticTransitionStrategy
from .source_text_edit import single_source_text_edit
from .trailing_edit_strategy import PromptTrailingEditStrategy


class PromptStateProjectionStrategy:
    """Own local strategy selection for one prepared semantic snapshot."""

    def __init__(
        self,
        semantic_transition: PromptSemanticTransitionStrategy,
        *,
        trailing_strategy: PromptTrailingEditStrategy,
        reflow_strategy: PromptIncrementalReflowStrategy,
        publication: PromptEditPublication,
    ) -> None:
        """Store focused mechanisms used by prepared prompt-state catch-up."""

        self._semantic_transition = semantic_transition
        self._trailing_strategy = trailing_strategy
        self._reflow_strategy = reflow_strategy
        self._publication = publication

    def try_trailing_insert(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Apply semantic catch-up through the shared trailing strategy."""

        if not self._trailing_strategy.can_apply_prompt_state_insert(
            render_plan,
            previous_render_plan=previous_render_plan,
        ):
            return False
        projection_document = self._trailing_strategy.try_plain_insert(
            document_view=document_view,
            render_plan=render_plan,
        )
        if projection_document is None:
            return False
        self._publication.publish_trailing_insert(
            projection_document,
            cache_reason="projection_fast_insert",
        )
        return True

    def try_incremental(
        self,
        *,
        previous_text: str,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> bool:
        """Apply scheduled safe typing through local reflow strategies."""

        next_text = document_view.source_text
        edit = single_source_text_edit(previous_text, next_text)
        if edit is None:
            if previous_text != next_text:
                return False
            semantic_result = self._semantic_transition.try_apply(
                document_view=document_view,
                render_plan=render_plan,
                previous_render_plan=previous_render_plan,
            )
            if semantic_result is None:
                return False
            self._publication.publish_semantic_transition(semantic_result)
            return True
        if not render_plan_ranges_match_after_source_edit(
            previous_render_plan,
            render_plan,
            edit=edit,
        ):
            return False
        previous_layout_identity = self._publication.current_layout_identity()
        result = self._reflow_strategy.try_incremental(
            previous_text=previous_text,
            next_text=next_text,
            start=edit.start,
            end=edit.end,
            replacement_text=edit.replacement_text,
        )
        if result.status is PromptProjectionPlainTextApplyStatus.APPLIED:
            self._publication.publish_incremental(
                result,
                start=edit.start,
                end=edit.end,
                replacement_text=edit.replacement_text,
                previous_layout_identity=previous_layout_identity,
            )
            return True
        if result.status is PromptProjectionPlainTextApplyStatus.APPLIED_REFLOW:
            self._publication.publish_reflow(result)
            return True
        return False


__all__ = ["PromptStateProjectionStrategy"]
