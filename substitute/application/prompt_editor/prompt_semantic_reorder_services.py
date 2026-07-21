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

"""Adapt ordinary tag reorder services to active document semantics."""

from __future__ import annotations

from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_semantics import PromptDocumentSemantics
from .prompt_document_views import PromptDocumentView, PromptReorderChipView
from .prompt_reorder_drop_service import PromptReorderDropService
from .prompt_reorder_projection_service import PromptReorderProjectionService
from .prompt_reorder_serialization_service import PromptReorderSerializationService
from .prompt_reorder_views import (
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderSessionView,
    PromptReorderStateView,
)
from .prompt_structured_reorder_document import PromptStructuredReorderDocument


class PromptSemanticReorderProjectionService(PromptReorderProjectionService):
    """Project normal tag chips from raw or decoded structured source."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Store ordinary projection and structured translation collaborators."""

        super().__init__(document_projector=document_projector)
        self._semantic_document_projector = document_projector
        self._semantic_document_semantics = document_semantics

    def reorder_chips(
        self,
        document_view: PromptDocumentView,
    ) -> tuple[PromptReorderChipView, ...]:
        """Return normal tag chips mapped into active source coordinates."""

        structured = self._structured_document(document_view)
        if structured is None:
            return super().reorder_chips(document_view)
        return tuple(
            structured.map_chip(chip)
            for chip in super().reorder_chips(structured.document_view)
        )

    def build_reorder_session_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderSessionView:
        """Build one normal reorder session mapped to active source."""

        structured = self._structured_document(document_view)
        if structured is None:
            return super().build_reorder_session_view(document_view)
        return structured.map_session(
            super().build_reorder_session_view(structured.document_view)
        )

    def build_reorder_state_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderStateView:
        """Build authoritative reorder state from decoded values when needed."""

        structured = self._structured_document(document_view)
        return super().build_reorder_state_view(
            document_view if structured is None else structured.document_view
        )

    def build_reorder_layout_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderLayoutView:
        """Build reorder rows from decoded values when source is structured."""

        structured = self._structured_document(document_view)
        return super().build_reorder_layout_view(
            document_view if structured is None else structured.document_view
        )

    def _structured_document(
        self,
        document_view: PromptDocumentView,
    ) -> PromptStructuredReorderDocument | None:
        """Return a decoded reorder document only for structured source."""

        if not self._semantic_document_semantics.uses_structured_prompt_values:
            return None
        return PromptStructuredReorderDocument.build(
            source_text=document_view.source_text,
            document_semantics=self._semantic_document_semantics,
            document_projector=self._semantic_document_projector,
        )


class PromptSemanticReorderDropService(PromptReorderDropService):
    """Apply ordinary drop transforms against decoded structured values."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Store ordinary drop and structured translation collaborators."""

        super().__init__(document_projector=document_projector)
        self._semantic_document_projector = document_projector
        self._semantic_document_semantics = document_semantics

    def build_base_drag_layout_view(
        self,
        document_view: PromptDocumentView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Build a hidden-chip layout from decoded values when structured."""

        return super().build_base_drag_layout_view(
            self._reorder_document_view(document_view),
            dragged_segment_index=dragged_segment_index,
        )

    def build_base_drag_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Build an in-session hidden-chip layout with virtual source metadata."""

        return super().build_base_drag_layout_view_from_layout(
            self._reorder_document_view(document_view),
            layout_view,
            dragged_segment_index=dragged_segment_index,
        )

    def build_preview_drop_layout_view(
        self,
        document_view: PromptDocumentView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Build a decoded-value drop preview when source is structured."""

        return super().build_preview_drop_layout_view(
            self._reorder_document_view(document_view),
            dragged_segment_index=dragged_segment_index,
            drop_target=drop_target,
        )

    def build_preview_drop_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Build an in-session decoded-value drop preview."""

        return super().build_preview_drop_layout_view_from_layout(
            self._reorder_document_view(document_view),
            layout_view,
            dragged_segment_index=dragged_segment_index,
            drop_target=drop_target,
        )

    def build_preview_drop_reorder_state_from_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        current_layout_view: PromptReorderLayoutView,
        base_drag_layout_view: PromptReorderLayoutView | None,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderStateView:
        """Apply a decoded-value drop target to authoritative source state."""

        return super().build_preview_drop_reorder_state_from_state(
            self._reorder_document_view(document_view),
            state_view,
            current_layout_view=current_layout_view,
            base_drag_layout_view=base_drag_layout_view,
            dragged_segment_index=dragged_segment_index,
            drop_target=drop_target,
        )

    def _reorder_document_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptDocumentView:
        """Return raw source or its decoded virtual reorder document view."""

        if not self._semantic_document_semantics.uses_structured_prompt_values:
            return document_view
        return PromptStructuredReorderDocument.build(
            source_text=document_view.source_text,
            document_semantics=self._semantic_document_semantics,
            document_projector=self._semantic_document_projector,
        ).document_view


class PromptSemanticReorderSerializationService(PromptReorderSerializationService):
    """Serialize ordinary reorder state back into active source structure."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector,
        document_semantics: PromptDocumentSemantics,
    ) -> None:
        """Store ordinary serialization and structured translation collaborators."""

        super().__init__(document_projector=document_projector)
        self._semantic_document_projector = document_projector
        self._semantic_document_semantics = document_semantics

    def serialize_reorder_layout_view(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
    ) -> str:
        """Serialize a layout into raw or structure-preserving source."""

        structured = self._structured_document(document_view)
        if structured is None:
            return super().serialize_reorder_layout_view(document_view, layout_view)
        virtual_text = super().serialize_reorder_layout_view(
            structured.document_view,
            layout_view,
        )
        return structured.source_for_virtual_text(virtual_text)

    def serialize_reorder_state_view(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
    ) -> str:
        """Serialize authoritative state into raw or structured source."""

        structured = self._structured_document(document_view)
        if structured is None:
            return super().serialize_reorder_state_view(document_view, state_view)
        virtual_text = super().serialize_reorder_state_view(
            structured.document_view,
            state_view,
        )
        return structured.source_for_virtual_text(virtual_text)

    def build_reorder_preview_snapshot(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        include_edge_gaps: bool = True,
    ) -> PromptReorderPreviewSnapshot:
        """Build a raw-source preview from ordinary decoded-value layout state."""

        structured = self._structured_document(document_view)
        if structured is None:
            return super().build_reorder_preview_snapshot(
                document_view,
                layout_view,
                include_edge_gaps=include_edge_gaps,
            )
        preview = super().build_reorder_preview_snapshot(
            structured.document_view,
            layout_view,
            include_edge_gaps=include_edge_gaps,
        )
        return structured.map_preview(preview)

    def build_reorder_preview_snapshot_from_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        layout_view: PromptReorderLayoutView,
        include_edge_gaps: bool = True,
    ) -> PromptReorderPreviewSnapshot:
        """Build a raw-source preview from authoritative decoded-value state."""

        structured = self._structured_document(document_view)
        if structured is None:
            return super().build_reorder_preview_snapshot_from_state(
                document_view,
                state_view,
                layout_view=layout_view,
                include_edge_gaps=include_edge_gaps,
            )
        preview = super().build_reorder_preview_snapshot_from_state(
            structured.document_view,
            state_view,
            layout_view=layout_view,
            include_edge_gaps=include_edge_gaps,
        )
        return structured.map_preview(preview)

    def _structured_document(
        self,
        document_view: PromptDocumentView,
    ) -> PromptStructuredReorderDocument | None:
        """Return a decoded reorder document only for structured source."""

        if not self._semantic_document_semantics.uses_structured_prompt_values:
            return None
        return PromptStructuredReorderDocument.build(
            source_text=document_view.source_text,
            document_semantics=self._semantic_document_semantics,
            document_projector=self._semantic_document_projector,
        )


__all__ = [
    "PromptSemanticReorderDropService",
    "PromptSemanticReorderProjectionService",
    "PromptSemanticReorderSerializationService",
]
