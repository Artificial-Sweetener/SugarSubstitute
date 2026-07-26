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

"""Resolve bounded source-edit facts before projection strategy selection."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.state.editor_state import (
    PromptEditorDocumentState,
)

from ..core.editing.source_commands import PromptSourceEditOrigin
from .applicator import PromptProjectionApplicator
from .edit_fact_resolver import PromptEditFactResolver
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .freshness_controller import PromptProjectionFreshnessController
from .freshness_controller import PromptProjectionFreshnessBlockers
from .source_edit_projection_policy import (
    PromptSourceEditProjectionDecision,
    PromptSourceEditProjectionPolicy,
)
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController

PromptSourceEditFactEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptSourceEditProjectionFactContext(Protocol):
    """Expose the two live geometry queries needed for overlay eligibility."""

    def viewport(self) -> QWidget:
        """Return the active editor viewport."""

    def _current_caret_document_rect(self) -> QRectF:
        """Return the committed document-local caret rectangle."""

    def _projection_freshness_blockers(self) -> PromptProjectionFreshnessBlockers:
        """Return current modes that can block deferred projection work."""


class PromptSourceEditProjectionFactResolver:
    """Resolve edit-policy facts once from authoritative state owners."""

    def __init__(
        self,
        context: PromptSourceEditProjectionFactContext,
        *,
        applicator: PromptProjectionApplicator,
        editor_state: PromptSourceEditFactEditorState,
        freshness: PromptProjectionFreshnessController,
        layout: PromptLayoutEditToFrameCoordinator,
        overlays: PromptProjectionTransientEditOverlayController,
        policy: PromptSourceEditProjectionPolicy | None = None,
    ) -> None:
        """Store immutable-state, freshness, geometry, and overlay owners."""

        self._context = context
        self._applicator = applicator
        self._editor_state = editor_state
        self._freshness = freshness
        self._layout = layout
        self._overlays = overlays
        self._policy = policy or PromptSourceEditProjectionPolicy()
        self._facts = PromptEditFactResolver(self._policy)

    def resolve(
        self,
        *,
        start: int,
        end: int,
        replaced_text: str,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        previous_source_text: str,
        updated_text: str,
        normalized_text: str,
        region_structure_requires_rebuild: bool,
        cursor_state: PromptProjectionCaretState,
    ) -> PromptSourceEditProjectionDecision:
        """Return all bounded eligibility facts for one committed source edit."""

        if region_structure_requires_rebuild:
            return PromptSourceEditProjectionDecision(
                can_defer_projection=False,
                deferral_reason="region_structure_topology_changed",
            )
        if self._applicator.source_edit_requires_canonical_rebuild(
            previous_source_text,
            normalized_text,
            start=start,
            end=end,
        ):
            return PromptSourceEditProjectionDecision(
                can_defer_projection=False,
                deferral_reason="source_projection_topology_changed",
                projection_topology_requires_rebuild=True,
            )

        blockers = self._context._projection_freshness_blockers()
        document = self._editor_state.projection.document
        typed_character_requires_projection = bool(
            replacement_text
            and self._facts.typed_character_requires_projection(
                replacement_text,
                start=start,
                end=end,
                document=document,
                cursor_state=cursor_state,
                display_mode=blockers.display_mode,
                reorder_preview_active=blockers.reorder_preview_active,
                expanded_source_range_active=blockers.expanded_source_range_active,
                exact_weight_edit_active=blockers.exact_weight_edit_active,
            )
        )
        syntax_sensitive_prefix_deferrable = bool(
            replacement_text
            and self._facts.can_defer_syntax_autocomplete_prefix(
                start=start,
                end=end,
                replacement_text=replacement_text,
                normalized_text=normalized_text,
                document=document,
                cursor_state=cursor_state,
            )
        )
        insertion_inside_projected_token = self._facts.source_insertion_is_inside_token(
            start,
            document=document,
        )
        deletion_intersects_projected_token = (
            self._facts.source_range_intersects_tokens(
                start=start,
                end=end,
                document=document,
            )
        )
        can_defer, deferral_reason = self._freshness.can_defer_source_rebuild_for_edit(
            blockers=blockers,
            start=start,
            end=end,
            replaced_text=replaced_text,
            replacement_text=replacement_text,
            origin=origin,
            updated_text=updated_text,
            normalized_text=normalized_text,
            edit_inside_projected_token=insertion_inside_projected_token,
            delete_intersects_projected_token=(deletion_intersects_projected_token),
            typed_character_requires_immediate_projection=(
                typed_character_requires_projection
            ),
            syntax_sensitive_autocomplete_prefix=(syntax_sensitive_prefix_deferrable),
        )
        insertion_overlay_can_defer = (
            not replacement_text
            or not can_defer
            or self._insertion_overlay_can_defer(
                start=start,
                end=end,
                replacement_text=replacement_text,
                live_source_length=len(normalized_text),
            )
        )
        return self._policy.decide(
            can_defer_projection=can_defer,
            deferral_reason=deferral_reason,
            replacement_text=replacement_text,
            autocomplete_preview_active=blockers.autocomplete_preview_active,
            insertion_overlay_can_defer=insertion_overlay_can_defer,
            typed_character_requires_projection=(typed_character_requires_projection),
            syntax_sensitive_prefix_deferrable=(syntax_sensitive_prefix_deferrable),
            insertion_inside_projected_token=insertion_inside_projected_token,
            deletion_intersects_projected_token=(deletion_intersects_projected_token),
        )

    def _insertion_overlay_can_defer(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        live_source_length: int,
    ) -> bool:
        """Return whether committed geometry can paint one insertion."""

        content_width = self._layout.frame.output.snapshot.content_size.width()
        content_right = (
            content_width
            if content_width > 1.0
            else float(self._context.viewport().width())
        )
        return self._overlays.can_defer_insertion_overlay(
            start=start,
            end=end,
            replacement_text=replacement_text,
            live_source_length=live_source_length,
            committed_source_length=len(
                self._editor_state.projection.document.source_text
            ),
            caret_rect=self._context._current_caret_document_rect(),
            content_right=content_right,
            metrics=self._layout.frame.output.configuration.metrics,
            freshness_is_stale_safe=self._freshness.has_stale_projection_geometry(),
            source_identity=self._editor_state.source_identity,
        )


__all__ = [
    "PromptSourceEditProjectionFactContext",
    "PromptSourceEditProjectionFactResolver",
]
