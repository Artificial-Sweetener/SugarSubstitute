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

"""Publish accepted edit frames through explicit projection effect sinks."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptLayoutIdentity,
)
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

from ..layout.contracts import PromptLayoutDamage
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .frame_state import PromptProjectionFrameStatePublisher
from .incremental_edit_contracts import PromptProjectionPlainTextApplyResult
from .semantic_transition_strategy import PromptSemanticTransitionResult


PromptEditPublicationState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptEditPublicationSink(Protocol):
    """Expose surface effects that remain outside revisioned edit state."""

    _cursor_state: PromptProjectionCaretState
    _anchor_state: PromptProjectionCaretState
    _caret_rect_override: QRectF | None
    _last_rendered_active_span_range: tuple[int, int] | None

    def _active_span_range(self) -> tuple[int, int] | None:
        """Return the active projected span range."""

    def _sync_editing_session_to_caret_states(self) -> object:
        """Mirror resolved projection caret states into the editing session."""

    def _clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Discard cached diagnostic fragments."""

    def _preserve_diagnostic_fragment_cache_for_incremental_edit(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        previous_layout_identity: PromptLayoutIdentity,
        next_layout_identity: PromptLayoutIdentity,
        fragment_y_delta: float = 0.0,
    ) -> None:
        """Preserve unaffected diagnostic fragments across a local edit."""

    def _rebuild_active_projection(self, *, commit_projection: bool = False) -> None:
        """Refresh prepared paint state after frame publication."""

    def _rebuild_projection(self) -> None:
        """Run one canonical projection rebuild."""

    def _update_incremental_plain_text_projection_paint(
        self,
        layout_result: PromptLayoutDamage,
    ) -> None:
        """Repaint lines dirtied by an accepted local edit."""

    def _clear_transient_caret_geometry(self) -> None:
        """Clear provisional caret geometry after committed catch-up."""

    def viewport(self) -> QWidget:
        """Return the repaint target."""


class PromptEditPublication:
    """Own state, caret, cache, paint, and viewport effects for accepted edits."""

    def __init__(
        self,
        sink: PromptEditPublicationSink,
        *,
        editor_state: PromptEditPublicationState,
        frame_state: PromptProjectionFrameStatePublisher,
        layout: PromptLayoutEditToFrameCoordinator,
    ) -> None:
        """Store explicit revisioned state and the remaining surface effect sink."""

        self._sink = sink
        self._editor_state = editor_state
        self._frame_state = frame_state
        self._layout = layout

    def current_layout_identity(self) -> PromptLayoutIdentity | None:
        """Return the active layout identity before a strategy mutates the frame."""

        return self._frame_state.current_layout_identity(self._layout.frame.output)

    def rebuild_projection(self) -> None:
        """Publish the terminal canonical projection rebuild."""

        self._sink._rebuild_projection()

    def clear_diagnostic_fragment_cache(self, *, reason: str) -> None:
        """Clear diagnostic geometry after a deferred terminal outcome."""

        self._sink._clear_diagnostic_fragment_cache(reason=reason)

    def publish_trailing_insert(
        self,
        projection_document: PromptProjectionDocument,
        *,
        cache_reason: str,
    ) -> None:
        """Publish an accepted trailing insertion and remap caret state."""

        sink = self._sink
        previous_cursor_state = sink._cursor_state
        previous_anchor_state = sink._anchor_state
        self._editor_state.publish_projection(projection_document)
        sink._last_rendered_active_span_range = sink._active_span_range()
        sink._clear_diagnostic_fragment_cache(reason=cache_reason)
        sink._cursor_state = projection_document.caret_map.resolve_state(
            previous_cursor_state
        )
        sink._anchor_state = projection_document.caret_map.resolve_state(
            previous_anchor_state
        )
        sink._sync_editing_session_to_caret_states()
        sink._caret_rect_override = None
        self._finish_trailing_publication()

    def publish_plain_delete(
        self,
        projection_document: PromptProjectionDocument,
        *,
        start: int,
        end: int,
        previous_layout_identity: PromptLayoutIdentity | None,
    ) -> None:
        """Publish a plain deletion while retaining unaffected diagnostics."""

        sink = self._sink
        self._editor_state.publish_projection(projection_document)
        sink._last_rendered_active_span_range = sink._active_span_range()
        next_layout_identity = self._frame_state.publish_layout(
            self._layout.frame.output
        )
        if previous_layout_identity is None or next_layout_identity is None:
            sink._clear_diagnostic_fragment_cache(reason="projection_fast_delete")
        else:
            sink._preserve_diagnostic_fragment_cache_for_incremental_edit(
                start=start,
                end=end,
                replacement_text="",
                previous_layout_identity=previous_layout_identity,
                next_layout_identity=next_layout_identity,
            )
        self._finish_trailing_publication()

    def publish_newline_delete(
        self,
        projection_document: PromptProjectionDocument,
    ) -> None:
        """Publish a newline deletion and invalidate diagnostic geometry."""

        sink = self._sink
        self._editor_state.publish_projection(projection_document)
        sink._last_rendered_active_span_range = sink._active_span_range()
        sink._clear_diagnostic_fragment_cache(reason="projection_fast_newline_delete")
        self._finish_trailing_publication()

    def publish_incremental(
        self,
        result: PromptProjectionPlainTextApplyResult,
        *,
        start: int,
        end: int,
        replacement_text: str,
        previous_layout_identity: PromptLayoutIdentity | None,
    ) -> None:
        """Publish one accepted same-line or hard-line incremental result."""

        projection_document = result.projection_document
        layout_result = result.layout_result
        if projection_document is None or layout_result is None:
            raise AssertionError("accepted incremental edit omitted frame state")
        sink = self._sink
        self._editor_state.publish_projection(projection_document)
        sink._last_rendered_active_span_range = sink._active_span_range()
        next_layout_identity = self._frame_state.publish_layout(
            self._layout.frame.output
        )
        if previous_layout_identity is None or next_layout_identity is None:
            sink._clear_diagnostic_fragment_cache(
                reason="projection_incremental_plain_text"
            )
        else:
            sink._preserve_diagnostic_fragment_cache_for_incremental_edit(
                start=start,
                end=end,
                replacement_text=replacement_text,
                previous_layout_identity=previous_layout_identity,
                next_layout_identity=next_layout_identity,
                fragment_y_delta=(
                    layout_result.content_height_delta
                    if layout_result.content_height_changed
                    else 0.0
                ),
            )
        sink._rebuild_active_projection(commit_projection=True)
        sink._clear_transient_caret_geometry()
        sink._update_incremental_plain_text_projection_paint(layout_result)

    def publish_reflow(
        self,
        result: PromptProjectionPlainTextApplyResult,
    ) -> None:
        """Publish one bounded canonical reflow and its exact damage."""

        projection_document = result.projection_document
        layout_result = result.layout_result
        if projection_document is None or layout_result is None:
            raise AssertionError("accepted canonical reflow omitted frame state")
        sink = self._sink
        self._editor_state.publish_projection(projection_document)
        sink._last_rendered_active_span_range = sink._active_span_range()
        sink._clear_diagnostic_fragment_cache(reason="projection_prebuilt_reflow")
        sink._rebuild_active_projection(commit_projection=True)
        sink._clear_transient_caret_geometry()
        sink._update_incremental_plain_text_projection_paint(layout_result)

    def publish_checkpoint(
        self,
        projection_document: PromptProjectionDocument,
    ) -> None:
        """Publish one exact history frame restored by the checkpoint owner."""

        sink = self._sink
        self._editor_state.publish_projection(projection_document)
        sink._last_rendered_active_span_range = sink._active_span_range()
        sink._clear_diagnostic_fragment_cache(
            reason="projection_history_checkpoint_restore"
        )
        sink._rebuild_active_projection(commit_projection=True)
        sink._clear_transient_caret_geometry()
        sink.viewport().update()

    def publish_semantic_transition(
        self,
        result: PromptSemanticTransitionResult,
    ) -> None:
        """Publish one same-source semantic document and bounded frame damage."""

        sink = self._sink
        previous_cursor_state = sink._cursor_state
        previous_anchor_state = sink._anchor_state
        projection_document = result.projection_document
        self._editor_state.publish_projection(projection_document)
        sink._last_rendered_active_span_range = sink._active_span_range()
        sink._clear_diagnostic_fragment_cache(
            reason="projection_local_semantic_transition"
        )
        sink._cursor_state = projection_document.caret_map.resolve_state(
            previous_cursor_state
        )
        sink._anchor_state = projection_document.caret_map.resolve_state(
            previous_anchor_state
        )
        sink._sync_editing_session_to_caret_states()
        sink._rebuild_active_projection(commit_projection=True)
        sink._clear_transient_caret_geometry()
        sink._update_incremental_plain_text_projection_paint(result.layout_damage)

    def _finish_trailing_publication(self) -> None:
        """Commit prepared paint state and repaint after a trailing edit."""

        sink = self._sink
        sink._rebuild_active_projection(commit_projection=True)
        sink._clear_transient_caret_geometry()
        sink.viewport().update()


__all__ = [
    "PromptEditPublication",
    "PromptEditPublicationSink",
]
