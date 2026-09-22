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

"""Own the semantic editor API exposed by the mounted projection surface."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QTextDocument
from PySide6.QtWidgets import QScrollBar, QWidget

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptSyntaxSpanView,
)

from ..commands.execution import PromptEditExecution
from ..commands.source_service import PromptSourceCommandService
from ..core.editing.commit import PromptEditCommit
from ..core.editing.session import PromptEditingSession
from ..core.projection.document import (
    PromptProjectionDisplayMode,
    PromptProjectionDocument,
)
from ..core.projection.tokens import PromptProjectionToken
from ..geometry.models import PromptProjectionSourceLineRect
from .autocomplete_preview_projection_owner import (
    PromptAutocompletePreviewProjectionOwner,
)
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .emphasis_projection_owner import PromptProjectionEmphasisOwner
from .fill_band_cache import PromptFillBandRect
from .frame_state import PromptProjectionEditorState
from .history_owner import PromptProjectionHistoryOwner
from .reorder_projection_owner import PromptReorderProjectionOwner
from .source_commit_application import PromptProjectionSourceCommitApplication
from .source_range_commit_application import PromptCanonicalSemanticPreparer
from .source_document import PromptProjectionSourceDocument
from .surface_input_runtime import PromptProjectionSurfaceInputRuntime
from .surface_interaction_runtime import PromptProjectionSurfaceInteractionRuntime
from .surface_lifecycle_runtime import PromptProjectionSurfaceLifecycleRuntime
from .surface_presentation_runtime import PromptProjectionSurfacePresentationRuntime
from .freshness_controller import PromptProjectionFreshnessController
from .undo_payload import PromptProjectionUndoPayload


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceEditorBindings:
    """Declare owners exposed through the mounted semantic editor API."""

    editing_session: PromptEditingSession[PromptProjectionUndoPayload]
    source_document: PromptProjectionSourceDocument
    source_commit: PromptProjectionSourceCommitApplication[PromptProjectionUndoPayload]
    input_runtime: PromptProjectionSurfaceInputRuntime
    interaction: PromptProjectionSurfaceInteractionRuntime
    lifecycle: PromptProjectionSurfaceLifecycleRuntime
    presentation: PromptProjectionSurfacePresentationRuntime
    editor_state: PromptProjectionEditorState
    freshness: PromptProjectionFreshnessController
    diagnostics: PromptDiagnosticLayerOwner


class PromptProjectionSurfaceEditorFacade:
    """Expose source, projection, and semantic presentation as one editor API."""

    def __init__(self, bindings: PromptProjectionSurfaceEditorBindings) -> None:
        """Store the authoritative editor owners and local interaction modes."""

        self._bindings = bindings
        self._editing_enabled = True
        self._exact_source_editing_enabled = False

    @property
    def editor_state(self) -> PromptProjectionEditorState:
        """Return the shared revisioned state owner used by composition."""

        return self._bindings.editor_state

    @property
    def reorder(self) -> PromptReorderProjectionOwner:
        """Return the focused reorder projection owner."""

        return self._bindings.lifecycle.reorder

    @property
    def emphasis(self) -> PromptProjectionEmphasisOwner:
        """Return the focused emphasis projection owner."""

        return self._bindings.lifecycle.emphasis

    @property
    def diagnostics(self) -> PromptDiagnosticLayerOwner:
        """Return the diagnostic state and render-layer owner."""

        return self._bindings.diagnostics

    @property
    def autocomplete_preview(self) -> PromptAutocompletePreviewProjectionOwner:
        """Return the autocomplete preview projection owner."""

        return self._bindings.interaction.autocomplete_preview

    @property
    def edit_execution(self) -> PromptEditExecution[PromptProjectionUndoPayload]:
        """Return the construction-owned editing execution service."""

        return self._bindings.input_runtime.edit_execution

    @property
    def source_commands(
        self,
    ) -> PromptSourceCommandService[PromptProjectionUndoPayload]:
        """Return the focused source command service."""

        return self._bindings.input_runtime.source_commands

    @property
    def history(self) -> PromptProjectionHistoryOwner:
        """Return the undo and clipboard-history owner."""

        return self._bindings.input_runtime.history

    def document(self) -> QTextDocument:
        """Return the plain-text source document for compatibility helpers."""

        return self._bindings.source_document.document()

    def source_text(self) -> str:
        """Return the current raw prompt source text."""

        return self._bindings.editing_session.source_text

    def prompt_document_view(self) -> PromptDocumentView:
        """Return the current prepared prompt document view."""

        return self._bindings.editor_state.edit_semantic.document

    def apply_edit_commit(
        self,
        commit: PromptEditCommit[PromptProjectionUndoPayload],
    ) -> None:
        """Apply the sole committed editing result to projection state."""

        self._bindings.source_commit.apply_edit_commit(commit)

    def bind_canonical_semantic_preparer(
        self,
        preparer: PromptCanonicalSemanticPreparer,
    ) -> None:
        """Bind the syntax owner used for canonical paste preparation."""

        self._bindings.source_commit.bind_canonical_semantic_preparer(preparer)

    def attach_external_scroll_bar(self, scroll_bar: QScrollBar) -> None:
        """Attach the host-owned visible scrollbar."""

        self._bindings.input_runtime.wheel.attach_external_scroll_bar(scroll_bar)

    def attach_focus_host(self, focus_host: QWidget) -> None:
        """Attach the widget whose focus drives caret and accent visibility."""

        self._bindings.interaction.focus.attach(focus_host)

    def set_editing_enabled(self, editing_enabled: bool) -> bool:
        """Set source mutation availability and report whether it changed."""

        changed = self._editing_enabled != editing_enabled
        self._editing_enabled = editing_enabled
        return changed

    @property
    def editing_enabled(self) -> bool:
        """Return whether clipboard and history owners may mutate source text."""

        return self._editing_enabled

    @property
    def exact_source_editing_enabled(self) -> bool:
        """Return whether user edits bypass prompt source normalization."""

        return self._exact_source_editing_enabled

    def set_exact_source_editing_enabled(self, enabled: bool) -> None:
        """Set exact source preservation for user edits."""

        self._exact_source_editing_enabled = enabled

    @property
    def display_mode(self) -> PromptProjectionDisplayMode:
        """Return the current visible prompt display mode."""

        return self._bindings.presentation.rebuild.display_mode

    def set_display_mode(self, display_mode: PromptProjectionDisplayMode) -> None:
        """Replace the visible display mode without changing source text."""

        self._bindings.presentation.rebuild.set_display_mode(display_mode)

    @property
    def projection_document(self) -> PromptProjectionDocument:
        """Return the committed token-aware projection document."""

        return self._bindings.presentation.queries.projection_document

    @property
    def active_projection_document(self) -> PromptProjectionDocument:
        """Return the current geometry-bearing projection document."""

        return self._bindings.presentation.queries.active_projection_document

    def content_height(self) -> float:
        """Return the current laid-out projection content height."""

        return self._bindings.presentation.queries.content_height()

    def text_line_height(self) -> float:
        """Return the row height owned by the current prepared layout."""

        return self._bindings.presentation.queries.text_line_height()

    def source_range_fragments(self, *, start: int, end: int) -> tuple[QRectF, ...]:
        """Return wrapped viewport fragments covering one source range."""

        return self._bindings.presentation.queries.source_range_fragments(
            start=start,
            end=end,
        )

    def source_line_rects(self) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible source-line rects aligned to the projection."""

        return self._bindings.presentation.queries.source_line_rects()

    def visible_fill_band_rects(self) -> tuple[PromptFillBandRect, ...]:
        """Return visible prompt fill-band rows in viewport coordinates."""

        return self._bindings.presentation.queries.visible_fill_band_rects()

    def fill_band_color(self) -> QColor:
        """Return the alternating prompt fill color."""

        return self._bindings.presentation.queries.fill_band_color()

    def current_source_line_index(self) -> int:
        """Return the source line containing the cursor."""

        return self._bindings.presentation.queries.current_source_line_index()

    def set_source_line_chrome_enabled(self, enabled: bool) -> None:
        """Set source-line background visibility."""

        self._bindings.presentation.source_line.set_enabled(enabled)

    def set_source_line_content_left_inset(self, inset: float) -> None:
        """Reserve viewport-local space for source line numbers."""

        self._bindings.presentation.source_line.set_content_left_inset(inset)

    def set_scene_error_keys(self, scene_error_keys: frozenset[str]) -> None:
        """Replace scene keys rendered as title-level diagnostics."""

        self._bindings.presentation.scene_diagnostics.set_keys(scene_error_keys)

    @property
    def scene_error_keys(self) -> frozenset[str]:
        """Return scene keys included in projection builds."""

        return self._bindings.presentation.scene_diagnostics.keys

    def set_search_matches(
        self,
        matches: tuple[tuple[int, int], ...],
        *,
        active_index: int | None,
    ) -> None:
        """Replace transient search matches rendered by the projection."""

        self._bindings.presentation.search.set_matches(
            matches,
            active_index=active_index,
        )

    def clear_search_matches(self) -> None:
        """Clear transient search highlights."""

        self._bindings.presentation.search.clear_matches()

    def active_syntax_span(self) -> PromptSyntaxSpanView | None:
        """Return the syntax span owned by caret or token focus."""

        return self._bindings.presentation.queries.active_syntax_span()

    def hovered_token(self) -> PromptProjectionToken | None:
        """Return the token under the pointer when present."""

        return self._bindings.presentation.queries.hovered_token()

    def focused_token(self) -> PromptProjectionToken | None:
        """Return the token owning caret focus when present."""

        return self._bindings.presentation.queries.focused_token()

    def token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the projected token under one viewport-local point."""

        return self._bindings.presentation.queries.token_at_viewport_position(position)

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local anchor rect for token controls."""

        return self._bindings.presentation.queries.token_anchor_rect(token)

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the projection-owned weight slot for one emphasis token."""

        return self._bindings.presentation.queries.token_weight_text_rect(token)

    def defer_source_rebuilds_until_prompt_state(self, enabled: bool) -> None:
        """Set whether source edits wait for controller-owned prompt snapshots."""

        self._bindings.freshness.set_defer_source_rebuilds_until_prompt_state(enabled)


__all__ = [
    "PromptProjectionSurfaceEditorBindings",
    "PromptProjectionSurfaceEditorFacade",
]
