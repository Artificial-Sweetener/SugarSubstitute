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

"""Build one same-source semantic projection and its bounded frame transition."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)

from ..layout.contracts import PromptLayoutDamage
from .applicator import PromptProjectionApplicator
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .projection_build_context import PromptProjectionBuildContext
from .semantic_transition import semantic_projection_change_range

PromptSemanticTransitionEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


@dataclass(frozen=True, slots=True)
class PromptSemanticTransitionResult:
    """Carry one built projection document and its published frame damage."""

    projection_document: PromptProjectionDocument
    layout_damage: PromptLayoutDamage


class PromptSemanticTransitionStrategy:
    """Own bounded same-source token-topology transitions."""

    def __init__(
        self,
        context: PromptProjectionBuildContext,
        *,
        applicator: PromptProjectionApplicator,
        editor_state: PromptSemanticTransitionEditorState,
        layout: PromptLayoutEditToFrameCoordinator,
    ) -> None:
        """Store explicit projection construction and frame owners."""

        self._context = context
        self._applicator = applicator
        self._editor_state = editor_state
        self._layout = layout

    def try_apply(
        self,
        *,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        previous_render_plan: PromptSyntaxRenderPlan,
    ) -> PromptSemanticTransitionResult | None:
        """Build and publish one eligible local semantic frame transition."""

        context = self._context
        blockers = context._projection_freshness_blockers()
        if (
            blockers.display_mode is not PromptProjectionDisplayMode.PROJECTED
            or blockers.reorder_preview_active
            or blockers.autocomplete_preview_active
            or blockers.exact_weight_edit_active
            or blockers.expanded_source_range_active
            or self._editor_state.projection.document.source_text
            != document_view.source_text
        ):
            return None
        changed_range = semantic_projection_change_range(
            previous_render_plan,
            render_plan,
        )
        if changed_range is None:
            return None
        start, end = changed_range
        if not 0 <= start < end <= len(document_view.source_text):
            return None
        projection_document = self._applicator.build_projection(
            document_view,
            render_plan,
            display_mode=context._display_mode,
            session=context._session,
            active_span_range=None,
            decoration_accent_ranges=context._decoration_accent_ranges(),
            scene_error_keys=context._scene_error_keys,
        )
        layout_damage = self._layout.set_projection_after_source_edit(
            projection_document,
            prompt_document_view=document_view,
            edit_start=start,
            edit_end=end,
            replacement_text=document_view.source_text[start:end],
        )
        return PromptSemanticTransitionResult(
            projection_document=projection_document,
            layout_damage=layout_damage,
        )


__all__ = [
    "PromptSemanticTransitionResult",
    "PromptSemanticTransitionStrategy",
]
