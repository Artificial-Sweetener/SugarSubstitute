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

"""Resolve authoritative caret geometry across committed and transient state."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)

from ..core.projection.caret import PromptProjectionCaretState
from ..core.projection.document import PromptProjectionDocument
from ..core.state.editor_state import PromptEditorDocumentState
from .caret_state_owner import PromptProjectionCaretStateOwner
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController

PromptCaretGeometryEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptProjectionCaretGeometryOwner:
    """Choose and translate the geometry for the current logical caret."""

    def __init__(
        self,
        *,
        state: PromptProjectionCaretStateOwner,
        editor_state: PromptCaretGeometryEditorState,
        overlays: PromptProjectionTransientEditOverlayController,
        freshness_is_stale_safe: Callable[[], bool],
        cursor_position: Callable[[], int],
        anchor_position: Callable[[], int],
        committed_document_rect: Callable[[PromptProjectionCaretState], QRectF],
        scroll_offset: Callable[[], float],
    ) -> None:
        """Store the complete identity and coordinate dependencies for caret geometry."""

        self._state = state
        self._editor_state = editor_state
        self._overlays = overlays
        self._freshness_is_stale_safe = freshness_is_stale_safe
        self._cursor_position = cursor_position
        self._anchor_position = anchor_position
        self._committed_document_rect = committed_document_rect
        self._scroll_offset = scroll_offset

    def clear_transient(self) -> None:
        """Discard temporary caret and edit geometry after committed catch-up."""

        self._overlays.clear()

    def transient_document_rect(self) -> QRectF | None:
        """Return source-current transient geometry while committed layout is stale."""

        return self._overlays.valid_caret_document_rect(
            freshness_is_stale_safe=self._freshness_is_stale_safe(),
            source_identity=self._editor_state.source_identity,
            cursor_position=self._cursor_position(),
            anchor_position=self._anchor_position(),
        )

    def current_document_rect(self) -> QRectF:
        """Return current document-local geometry with explicit affinity precedence."""

        transient_rect = self.transient_document_rect()
        if transient_rect is not None:
            return transient_rect
        caret_rect_override = self._state.caret_rect_override
        if caret_rect_override is not None:
            return caret_rect_override
        return self._committed_document_rect(self._state.cursor_state)

    def current_viewport_rect(self) -> QRectF:
        """Translate current document-local caret geometry into viewport coordinates."""

        return self.current_document_rect().translated(0.0, -self._scroll_offset())


__all__ = ["PromptProjectionCaretGeometryOwner"]
