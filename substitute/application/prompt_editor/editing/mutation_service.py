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

"""Compose prompt mutation-family owners behind one application boundary."""

from __future__ import annotations

from decimal import Decimal

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.document.semantics import (
    OrdinaryPromptDocumentSemantics,
    PromptDocumentSemantics,
)
from substitute.application.prompt_editor.editing.emphasis_mutations import (
    PromptEmphasisMutationService,
)
from substitute.application.prompt_editor.editing.lora_mutations import (
    PromptLoraMutationService,
)
from substitute.application.prompt_editor.editing.mutation_result import (
    PromptMutation,
    PromptMutationProjector,
)
from substitute.application.prompt_editor.editing.reorder_mutations import (
    PromptReorderMutationService,
)
from substitute.application.prompt_editor.editing.syntax_action_router import (
    PromptSyntaxActionRouter,
)
from substitute.application.prompt_editor.editing.syntax_actions import (
    PromptSyntaxAction,
)
from substitute.application.prompt_editor.editing.wildcard_mutations import (
    PromptWildcardMutationService,
)
from substitute.application.prompt_editor.reorder.projection import (
    PromptReorderProjectionService,
)
from substitute.application.prompt_editor.reorder.semantics import (
    PromptSemanticReorderProjectionService,
    PromptSemanticReorderSerializationService,
)
from substitute.application.prompt_editor.reorder.serialization import (
    PromptReorderSerializationService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderStateView,
)


class PromptMutationService:
    """Expose the complete prompt mutation use case through focused owners."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
        reorder_projection_service: PromptReorderProjectionService | None = None,
        reorder_serialization_service: PromptReorderSerializationService | None = None,
        document_semantics: PromptDocumentSemantics | None = None,
    ) -> None:
        """Compose syntax-family, reorder, and result-projection collaborators."""

        resolved_document_projector = document_projector or PromptDocumentProjector()
        resolved_semantics = document_semantics or OrdinaryPromptDocumentSemantics()
        mutation_projector = PromptMutationProjector(resolved_document_projector)
        self._emphasis_mutations = PromptEmphasisMutationService(
            resolved_document_projector,
            mutation_projector,
        )
        self._lora_mutations = PromptLoraMutationService(
            resolved_document_projector,
            mutation_projector,
        )
        self._wildcard_mutations = PromptWildcardMutationService(
            resolved_document_projector,
            mutation_projector,
        )
        resolved_reorder_projection = reorder_projection_service or (
            PromptSemanticReorderProjectionService(
                document_projector=resolved_document_projector,
                document_semantics=resolved_semantics,
            )
        )
        resolved_reorder_serialization = reorder_serialization_service or (
            PromptSemanticReorderSerializationService(
                document_projector=resolved_document_projector,
                document_semantics=resolved_semantics,
            )
        )
        self._reorder_mutations = PromptReorderMutationService(
            document_projector=resolved_document_projector,
            mutation_projector=mutation_projector,
            reorder_projection_service=resolved_reorder_projection,
            reorder_serialization_service=resolved_reorder_serialization,
        )
        self._syntax_action_router = PromptSyntaxActionRouter(
            document_semantics=resolved_semantics,
            mutation_projector=mutation_projector,
            emphasis_mutations=self._emphasis_mutations,
            lora_mutations=self._lora_mutations,
            wildcard_mutations=self._wildcard_mutations,
        )

    def apply_syntax_action(
        self,
        text: str,
        action: PromptSyntaxAction,
    ) -> PromptMutation | None:
        """Route one typed syntax action to its authoritative family owner."""

        return self._syntax_action_router.apply(text, action)

    def adjust_emphasis(
        self,
        text: str,
        *,
        selection_start: int,
        selection_end: int,
        delta: float | Decimal,
    ) -> PromptMutation:
        """Increase or decrease emphasis around the selected text."""

        return self._emphasis_mutations.adjust(
            text,
            selection_start=selection_start,
            selection_end=selection_end,
            delta=delta,
        )

    def set_emphasis_weight(
        self,
        text: str,
        *,
        selection_start: int,
        selection_end: int,
        weight: float | Decimal,
    ) -> PromptMutation:
        """Set emphasis to one exact weight over a content range."""

        return self._emphasis_mutations.set_weight(
            text,
            selection_start=selection_start,
            selection_end=selection_end,
            weight=weight,
        )

    def adjust_emphasis_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        delta: float | Decimal,
    ) -> PromptMutation | None:
        """Adjust the emphasis span matching one exact outer source range."""

        return self._emphasis_mutations.adjust_outer_range(
            text,
            outer_start=outer_start,
            outer_end=outer_end,
            delta=delta,
        )

    def set_emphasis_weight_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        weight: float | Decimal,
    ) -> PromptMutation | None:
        """Set the weight of the emphasis span matching one outer range."""

        return self._emphasis_mutations.set_weight_for_outer_range(
            text,
            outer_start=outer_start,
            outer_end=outer_end,
            weight=weight,
        )

    def adjust_lora_weight_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        delta: float | Decimal,
    ) -> PromptMutation | None:
        """Adjust the first weight for the LoRA matching one outer range."""

        return self._lora_mutations.adjust_weight_for_outer_range(
            text,
            outer_start=outer_start,
            outer_end=outer_end,
            delta=delta,
        )

    def set_lora_weight_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        weight: float | Decimal,
    ) -> PromptMutation | None:
        """Set the first weight for the LoRA matching one outer range."""

        return self._lora_mutations.set_weight_for_outer_range(
            text,
            outer_start=outer_start,
            outer_end=outer_end,
            weight=weight,
        )

    def set_wildcard_tag_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        tag: str,
    ) -> PromptMutation | None:
        """Set or replace the tag for one wildcard placeholder range."""

        return self._wildcard_mutations.set_tag_for_outer_range(
            text,
            outer_start=outer_start,
            outer_end=outer_end,
            tag=tag,
        )

    def adjust_wildcard_numeric_tag_for_outer_range(
        self,
        text: str,
        *,
        outer_start: int,
        outer_end: int,
        current_display_tag: str,
        delta: int,
    ) -> PromptMutation | None:
        """Persist a stepped numeric group tag for one wildcard range."""

        return self._wildcard_mutations.adjust_numeric_tag_for_outer_range(
            text,
            outer_start=outer_start,
            outer_end=outer_end,
            current_display_tag=current_display_tag,
            delta=delta,
        )

    def reorder_chips(
        self,
        text: str,
        *,
        dragged_chip_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptMutation:
        """Reorder prompt chips by applying one typed row or gap target."""

        return self._reorder_mutations.reorder_chips(
            text,
            dragged_chip_index=dragged_chip_index,
            drop_target=drop_target,
        )

    def reorder_layout(
        self,
        text: str,
        *,
        layout_view: PromptReorderLayoutView,
        selected_chip_index: int | None,
    ) -> PromptMutation:
        """Commit one in-session reorder layout back into prompt text."""

        return self._reorder_mutations.reorder_layout(
            text,
            layout_view=layout_view,
            selected_chip_index=selected_chip_index,
        )

    def reorder_state(
        self,
        text: str,
        *,
        reorder_state: PromptReorderStateView,
        selected_chip_index: int | None,
    ) -> PromptMutation:
        """Commit authoritative reorder source state back into prompt text."""

        return self._reorder_mutations.reorder_state(
            text,
            reorder_state=reorder_state,
            selected_chip_index=selected_chip_index,
        )


__all__ = ["PromptMutationService"]
