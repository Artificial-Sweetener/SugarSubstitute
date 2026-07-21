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

"""Build application-facing prompt document views for the prompt editor."""

from __future__ import annotations

from substitute.domain.prompt import (
    PromptDocument,
)

from .prompt_autocomplete_query_service import (
    PromptAutocompleteQueryService,
)
from .prompt_autocomplete_queries import (
    PromptAutocompleteFallbackQuery,
    PromptAutocompleteQuery,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from .prompt_document_cache import (
    clear_prompt_document_caches,
)
from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_semantics import PromptDocumentSemantics
from .prompt_document_selection_service import (
    PromptDocumentSelectionService,
)
from .prompt_document_views import (
    PromptDocumentView,
    PromptEmphasisView,
    PromptLoraView as PromptLoraView,
    PromptReorderChipView,
    PromptSegmentView,
    PromptSyntaxSpanView as PromptSyntaxSpanView,
    PromptWildcardView as PromptWildcardView,
)
from .prompt_lora_autocomplete_service import PromptLoraAutocompleteQuery
from .prompt_reorder_drop_service import PromptReorderDropService
from .prompt_reorder_projection_service import (
    PromptReorderProjectionService,
)
from .prompt_reorder_serialization_service import (
    PromptReorderSerializationService,
    blank_line_drop_offsets as reorder_blank_line_drop_offsets,
)
from .prompt_reorder_views import (
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderGapPlacement,
    PromptReorderGapView,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderRowView,
    PromptReorderSessionView,
    PromptReorderStateView,
)
from .prompt_semantic_reorder_services import (
    PromptSemanticReorderDropService,
    PromptSemanticReorderProjectionService,
    PromptSemanticReorderSerializationService,
)


class PromptDocumentService:
    """Parse prompt text once and answer application-facing prompt queries."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
        selection_service: PromptDocumentSelectionService | None = None,
        autocomplete_query_service: PromptAutocompleteQueryService | None = None,
        document_semantics: PromptDocumentSemantics | None = None,
        reorder_projection_service: PromptReorderProjectionService | None = None,
        reorder_drop_service: PromptReorderDropService | None = None,
        reorder_serialization_service: PromptReorderSerializationService | None = None,
    ) -> None:
        """Store extracted prompt document collaborators."""

        self._document_projector = document_projector or PromptDocumentProjector()
        self._selection_service = selection_service or PromptDocumentSelectionService()
        self._autocomplete_query_service = (
            autocomplete_query_service
            or PromptAutocompleteQueryService(
                document_projector=self._document_projector,
                selection_service=self._selection_service,
            )
        )
        self._reorder_projection_service = reorder_projection_service or (
            PromptReorderProjectionService(document_projector=self._document_projector)
            if document_semantics is None
            else PromptSemanticReorderProjectionService(
                document_projector=self._document_projector,
                document_semantics=document_semantics,
            )
        )
        self._reorder_drop_service = reorder_drop_service or (
            PromptReorderDropService(document_projector=self._document_projector)
            if document_semantics is None
            else PromptSemanticReorderDropService(
                document_projector=self._document_projector,
                document_semantics=document_semantics,
            )
        )
        self._reorder_serialization_service = reorder_serialization_service or (
            PromptReorderSerializationService(
                document_projector=self._document_projector
            )
            if document_semantics is None
            else PromptSemanticReorderSerializationService(
                document_projector=self._document_projector,
                document_semantics=document_semantics,
            )
        )

    def parse_document(self, text: str) -> PromptDocument:
        """Parse plain prompt text into the canonical domain document."""

        return self._document_projector.parse_document(text)

    def build_document_view(self, text: str) -> PromptDocumentView:
        """Build one application-safe prompt snapshot from plain text."""

        return self._document_projector.build_document_view(text)

    def prewarm_document_views(self, texts: tuple[str, ...]) -> int:
        """Populate process-wide prompt document caches for restored prompt texts."""

        return self._document_projector.prewarm_document_views(texts)

    def build_document_view_from_document(
        self,
        document: PromptDocument,
    ) -> PromptDocumentView:
        """Project one domain prompt document into the application snapshot."""

        return self._document_projector.build_document_view_from_document(document)

    def segment_at_position(
        self,
        document_view: PromptDocumentView,
        position: int,
    ) -> PromptSegmentView | None:
        """Return the visible prompt segment at one cursor position."""

        return self._selection_service.segment_at_position(document_view, position)

    def reorder_chip_at_position(
        self,
        document_view: PromptDocumentView,
        position: int,
    ) -> PromptReorderChipView | None:
        """Return the reorder chip selected by one cursor position."""

        return self._selection_service.reorder_chip_at_position(
            self.reorder_chips(document_view),
            position,
        )

    def reorder_chips(
        self,
        document_view: PromptDocumentView,
    ) -> tuple[PromptReorderChipView, ...]:
        """Return typed reorder chips with explicit separator metadata."""

        return self._reorder_projection_service.reorder_chips(document_view)

    def build_reorder_session_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderSessionView:
        """Build reorder chips and layout from one shared parsed document."""

        return self._reorder_projection_service.build_reorder_session_view(
            document_view
        )

    def build_reorder_state_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderStateView:
        """Build authoritative reorder source state from the current prompt snapshot."""

        return self._reorder_projection_service.build_reorder_state_view(document_view)

    def build_reorder_layout_view_from_state(
        self,
        state_view: PromptReorderStateView,
    ) -> PromptReorderLayoutView:
        """Derive display rows and gaps from authoritative reorder state."""

        return self._reorder_projection_service.build_reorder_layout_view_from_state(
            state_view
        )

    def build_reorder_layout_view(
        self,
        document_view: PromptDocumentView,
    ) -> PromptReorderLayoutView:
        """Build one derived reorder layout view from the current prompt snapshot."""

        return self._reorder_projection_service.build_reorder_layout_view(document_view)

    def build_base_drag_layout_view(
        self,
        document_view: PromptDocumentView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Build the derived layout view shown while the dragged chip is hidden."""

        return self._reorder_drop_service.build_base_drag_layout_view(
            document_view,
            dragged_segment_index=dragged_segment_index,
        )

    def build_base_drag_layout_view_from_layout(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderLayoutView:
        """Build the hidden-drag layout from the supplied in-session reorder layout."""

        return self._reorder_drop_service.build_base_drag_layout_view_from_layout(
            document_view,
            layout_view,
            dragged_segment_index=dragged_segment_index,
        )

    def build_base_drag_reorder_state_from_state(
        self,
        state_view: PromptReorderStateView,
        *,
        dragged_segment_index: int,
    ) -> PromptReorderStateView:
        """Return authoritative source state while one chip is lifted."""

        return self._reorder_drop_service.build_base_drag_reorder_state_from_state(
            state_view,
            dragged_segment_index=dragged_segment_index,
        )

    def build_preview_drop_layout_view(
        self,
        document_view: PromptDocumentView,
        *,
        dragged_segment_index: int,
        drop_target: PromptReorderDropTarget,
    ) -> PromptReorderLayoutView:
        """Build the derived layout view previewed for the supplied drop target."""

        return self._reorder_drop_service.build_preview_drop_layout_view(
            document_view,
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
        """Build one preview layout from the current in-session reorder layout."""

        return self._reorder_drop_service.build_preview_drop_layout_view_from_layout(
            document_view,
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
        """Apply a drop target to authoritative source state for commit/preview."""

        return self._reorder_drop_service.build_preview_drop_reorder_state_from_state(
            document_view,
            state_view,
            current_layout_view=current_layout_view,
            base_drag_layout_view=base_drag_layout_view,
            dragged_segment_index=dragged_segment_index,
            drop_target=drop_target,
        )

    def serialize_reorder_layout_view(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
    ) -> str:
        """Serialize one reorder layout view using the canonical separator-slot rules."""

        return self._reorder_serialization_service.serialize_reorder_layout_view(
            document_view,
            layout_view,
        )

    def serialize_reorder_state_view(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
    ) -> str:
        """Serialize authoritative reorder source state without layout reversal."""

        return self._reorder_serialization_service.serialize_reorder_state_view(
            document_view,
            state_view,
        )

    def build_reorder_preview_snapshot(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        *,
        include_edge_gaps: bool = True,
    ) -> PromptReorderPreviewSnapshot:
        """Build one syntax-ready preview snapshot for the supplied reorder layout."""

        return self._reorder_serialization_service.build_reorder_preview_snapshot(
            document_view,
            layout_view,
            include_edge_gaps=include_edge_gaps,
        )

    def build_reorder_preview_snapshot_from_state(
        self,
        document_view: PromptDocumentView,
        state_view: PromptReorderStateView,
        *,
        layout_view: PromptReorderLayoutView,
        include_edge_gaps: bool = True,
    ) -> PromptReorderPreviewSnapshot:
        """Build a syntax-ready preview from authoritative reorder source state."""

        return self._reorder_serialization_service.build_reorder_preview_snapshot_from_state(
            document_view,
            state_view,
            layout_view=layout_view,
            include_edge_gaps=include_edge_gaps,
        )

    def reorder_layout_chip_indices(
        self,
        layout_view: PromptReorderLayoutView,
    ) -> tuple[int, ...]:
        """Return the flattened prompt chip order represented by one layout view."""

        return self._reorder_projection_service.reorder_layout_chip_indices(layout_view)

    def emphasis_at_position(
        self,
        document_view: PromptDocumentView,
        position: int,
    ) -> PromptEmphasisView | None:
        """Return the innermost emphasis span selected by one cursor position."""

        return self._selection_service.emphasis_at_position(document_view, position)

    def emphasis_for_content_range(
        self,
        document_view: PromptDocumentView,
        *,
        content_start: int,
        content_end: int,
    ) -> PromptEmphasisView | None:
        """Return the emphasis span matching or containing one visible content range."""

        return self._selection_service.emphasis_for_content_range(
            document_view,
            content_start=content_start,
            content_end=content_end,
        )

    def emphasis_for_outer_range(
        self,
        document_view: PromptDocumentView,
        *,
        outer_start: int,
        outer_end: int,
    ) -> PromptEmphasisView | None:
        """Return the emphasis span whose full shell matches one outer source range."""

        return self._selection_service.emphasis_for_outer_range(
            document_view,
            outer_start=outer_start,
            outer_end=outer_end,
        )

    def autocomplete_query_at_cursor(
        self,
        document_view: PromptDocumentView,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
        minimum_prefix_length: int,
    ) -> PromptAutocompleteQuery | None:
        """Resolve one prompt-aware autocomplete query from the current caret state."""

        return self._autocomplete_query_service.autocomplete_query_at_cursor(
            document_view,
            text=text,
            cursor_position=cursor_position,
            has_selection=has_selection,
            minimum_prefix_length=minimum_prefix_length,
        )

    def wildcard_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptWildcardAutocompleteQuery | None:
        """Resolve a curly wildcard autocomplete query from the caret state."""

        return self._autocomplete_query_service.wildcard_autocomplete_query_at_cursor(
            text=text,
            cursor_position=cursor_position,
            has_selection=has_selection,
        )

    def scene_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptSceneAutocompleteQuery | None:
        """Resolve a line-start scene autocomplete query from the caret state."""

        return self._autocomplete_query_service.scene_autocomplete_query_at_cursor(
            text=text,
            cursor_position=cursor_position,
            has_selection=has_selection,
        )

    def lora_autocomplete_query_at_cursor(
        self,
        *,
        text: str,
        cursor_position: int,
        has_selection: bool,
    ) -> PromptLoraAutocompleteQuery | None:
        """Resolve a LoRA schedule autocomplete query from the caret state."""

        return self._autocomplete_query_service.lora_autocomplete_query_at_cursor(
            text=text,
            cursor_position=cursor_position,
            has_selection=has_selection,
        )


def blank_line_drop_offsets(separator_text: str) -> tuple[int, ...]:
    """Return blank-line split offsets for one reorder separator string."""

    return reorder_blank_line_drop_offsets(separator_text)


def prewarm_prompt_document_views(texts: tuple[str, ...]) -> int:
    """Populate process-wide prompt document caches for restored prompt texts."""

    return PromptDocumentService().prewarm_document_views(texts)


__all__ = [
    "PromptAutocompleteFallbackQuery",
    "PromptAutocompleteQuery",
    "PromptDocumentService",
    "PromptDocumentView",
    "PromptEmphasisView",
    "PromptGapBlankLineDropTarget",
    "PromptLineDropTarget",
    "PromptReorderChipView",
    "PromptReorderDropTarget",
    "PromptReorderGapPlacement",
    "PromptReorderGapView",
    "PromptReorderLayoutView",
    "PromptReorderPreviewSnapshot",
    "PromptReorderRowView",
    "PromptReorderSessionView",
    "PromptReorderStateView",
    "PromptSceneAutocompleteQuery",
    "PromptSegmentView",
    "PromptSyntaxSpanView",
    "PromptWildcardAutocompleteQuery",
    "PromptWildcardView",
    "blank_line_drop_offsets",
    "clear_prompt_document_caches",
    "prewarm_prompt_document_views",
]
