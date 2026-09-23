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

"""Apply prompt reorder mutations and serialize active reorder sessions."""

from __future__ import annotations

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.editing.mutation_result import (
    PromptMutation,
    PromptMutationProjector,
)
from substitute.application.prompt_editor.reorder.projection import (
    PromptReorderProjectionService,
)
from substitute.application.prompt_editor.reorder.serialization import (
    PromptReorderSerializationService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderStateView,
)
from substitute.domain.prompt.document.ranges import SourceRange
from substitute.domain.prompt.reorder.models import (
    PromptGapBlankLineDropTarget as DomainPromptGapBlankLineDropTarget,
    PromptLineDropTarget as DomainPromptLineDropTarget,
)
from substitute.domain.prompt.reorder.mutations import reorder_segments


class PromptReorderMutationService:
    """Own drop-target adaptation and reorder-session serialization."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector,
        mutation_projector: PromptMutationProjector,
        reorder_projection_service: PromptReorderProjectionService,
        reorder_serialization_service: PromptReorderSerializationService,
    ) -> None:
        """Store collaborators that project and serialize reorder state."""

        self._document_projector = document_projector
        self._mutation_projector = mutation_projector
        self._reorder_projection_service = reorder_projection_service
        self._reorder_serialization_service = reorder_serialization_service

    def reorder_chips(
        self,
        text: str,
        *,
        dragged_chip_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptMutation:
        """Reorder prompt chips by applying one typed row or gap target."""

        document = self._document_projector.parse_document(text)
        result = reorder_segments(
            document,
            dragged_segment_index=dragged_chip_index,
            drop_target=_domain_drop_target(drop_target),
        )
        return self._mutation_projector.project_result(result)

    def reorder_layout(
        self,
        text: str,
        *,
        layout_view: PromptReorderLayoutView,
        selected_chip_index: int | None,
    ) -> PromptMutation:
        """Commit one in-session reorder layout back into prompt text."""

        current_document_view = self._document_projector.build_document_view(text)
        preview_snapshot = (
            self._reorder_serialization_service.build_reorder_preview_snapshot(
                current_document_view,
                layout_view,
                include_edge_gaps=False,
            )
        )
        return self._mutation_from_preview(
            preview_snapshot.text,
            preview_snapshot.chip_ranges_by_index,
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

        current_document_view = self._document_projector.build_document_view(text)
        layout_view = (
            self._reorder_projection_service.build_reorder_layout_view_from_state(
                reorder_state
            )
        )
        preview_snapshot = self._reorder_serialization_service.build_reorder_preview_snapshot_from_state(
            current_document_view,
            reorder_state,
            layout_view=layout_view,
            include_edge_gaps=False,
        )
        return self._mutation_from_preview(
            preview_snapshot.text,
            preview_snapshot.chip_ranges_by_index,
            selected_chip_index=selected_chip_index,
        )

    def _mutation_from_preview(
        self,
        text: str,
        chip_ranges_by_index: dict[int, tuple[int, int]],
        *,
        selected_chip_index: int | None,
    ) -> PromptMutation:
        """Project serialized reorder text and its selected chip range."""

        selected_range = (
            None
            if selected_chip_index is None
            else chip_ranges_by_index.get(selected_chip_index)
        )
        selection_range = (
            None if selected_range is None else SourceRange(*selected_range)
        )
        return self._mutation_projector.project_document(
            text=text,
            document=self._document_projector.parse_document(text),
            selection_range=selection_range,
        )


def _domain_drop_target(
    drop_target: PromptReorderDropTarget,
) -> DomainPromptLineDropTarget | DomainPromptGapBlankLineDropTarget:
    """Convert one application drop target into its domain equivalent."""

    if isinstance(drop_target, PromptLineDropTarget):
        return DomainPromptLineDropTarget(
            row_index=drop_target.row_index,
            insertion_index=drop_target.insertion_index,
        )
    return DomainPromptGapBlankLineDropTarget(
        gap_index=drop_target.gap_index,
        blank_line_index=drop_target.blank_line_index,
    )


__all__ = ["PromptReorderMutationService"]
