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

"""Publish projected caret state and all state-derived presentation effects."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.projection.syntax_models import (
    PromptSyntaxRenderPlan,
)

from ..core.editing.cursor_state import PromptCursorState
from ..core.editing.session import PromptEditingSession
from ..core.projection.caret import (
    PromptProjectionCaretState,
    PromptProjectionSelection,
)
from ..core.projection.document import PromptProjectionDocument
from ..core.state.editor_state import PromptEditorDocumentState
from ..debug_probe import log_prompt_editor_probe
from ..geometry.selection import selection_paints_changed
from .caret_state_owner import PromptProjectionCaretStateOwner
from .undo_payload import PromptProjectionUndoPayload

PromptCaretPublicationEditorState = PromptEditorDocumentState[
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptProjectionDocument,
]


class PromptProjectionCaretPublicationOwner:
    """Own one logical-caret change from state resolution through repaint."""

    def __init__(
        self,
        *,
        state: PromptProjectionCaretStateOwner,
        editor_state: PromptCaretPublicationEditorState,
        editing_session: PromptEditingSession[PromptProjectionUndoPayload],
        selection: Callable[[], PromptProjectionSelection],
        current_caret_rect: Callable[[], QRectF],
        clear_transient_geometry: Callable[[], None],
        expanded_source_range_present: Callable[[], bool],
        collapse_expanded_token: Callable[[], None],
        reconcile_autocomplete: Callable[[int, bool], None],
        refresh_active_projection: Callable[[], None],
        ensure_caret_visible: Callable[[], None],
        refresh_caret_layers: Callable[[], None],
        refresh_deferred_caret_layers: Callable[[], None],
        restart_caret_blink: Callable[[], None],
        request_viewport_update: Callable[[], None],
        update_caret_paint: Callable[[QRectF | None], None],
        emit_cursor_position_changed: Callable[[], None],
        surface_state: Callable[[], dict[str, object]],
    ) -> None:
        """Store authoritative caret state and its ordered presentation effects."""

        self._state = state
        self._editor_state = editor_state
        self._editing_session = editing_session
        self._selection = selection
        self._current_caret_rect = current_caret_rect
        self._clear_transient_geometry = clear_transient_geometry
        self._expanded_source_range_present = expanded_source_range_present
        self._collapse_expanded_token = collapse_expanded_token
        self._reconcile_autocomplete = reconcile_autocomplete
        self._refresh_active_projection = refresh_active_projection
        self._ensure_caret_visible = ensure_caret_visible
        self._refresh_caret_layers = refresh_caret_layers
        self._refresh_deferred_caret_layers = refresh_deferred_caret_layers
        self._restart_caret_blink = restart_caret_blink
        self._request_viewport_update = request_viewport_update
        self._update_caret_paint = update_caret_paint
        self._emit_cursor_position_changed = emit_cursor_position_changed
        self._surface_state = surface_state

    @property
    def cursor_state(self) -> PromptProjectionCaretState:
        """Return the current projection-backed cursor state."""

        return self._state.cursor_state

    @property
    def anchor_state(self) -> PromptProjectionCaretState:
        """Return the current projection-backed anchor state."""

        return self._state.anchor_state

    def publish(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        reset_preferred_x: bool = True,
        caret_rect_override: QRectF | None = None,
        collapse_expanded_token: bool = True,
        preserve_unmapped_source_positions: bool = False,
        reason: str = "generic",
    ) -> None:
        """Resolve and publish one complete interactive caret transition."""

        log_prompt_editor_probe(
            "caret_publication.publish.begin",
            reason=reason,
            requested_cursor_position=cursor_state.source_position,
            requested_anchor_position=anchor_state.source_position,
            surface=self._surface_state(),
        )
        previous_caret_rect = self._current_caret_rect()
        previous_selection = self._selection()
        resolved_cursor_state = self._resolve_state(
            cursor_state,
            preserve_unmapped_source_position=preserve_unmapped_source_positions,
        )
        resolved_anchor_state = self._resolve_state(
            anchor_state,
            preserve_unmapped_source_position=preserve_unmapped_source_positions,
        )
        next_editing_session_state = PromptCursorState(
            cursor_position=resolved_cursor_state.source_position,
            anchor_position=resolved_anchor_state.source_position,
        ).clamped(len(self._editing_session.source_text))
        if (
            self._state.matches(
                cursor_state=resolved_cursor_state,
                anchor_state=resolved_anchor_state,
                caret_rect_override=caret_rect_override,
            )
            and self._editing_session.cursor_state == next_editing_session_state
        ):
            self._ensure_caret_visible()
            self._update_caret_paint(previous_caret_rect)
            log_prompt_editor_probe(
                "caret_publication.publish.end",
                reason=reason,
                changed=False,
                surface=self._surface_state(),
            )
            return
        self._clear_transient_geometry()
        self._editing_session.set_cursor_state(next_editing_session_state)
        self._state.publish(
            cursor_state=resolved_cursor_state,
            anchor_state=resolved_anchor_state,
            caret_rect_override=caret_rect_override,
            reset_preferred_x=reset_preferred_x,
        )
        if collapse_expanded_token and self._expanded_source_range_present():
            self._collapse_expanded_token()
        current_selection = self._selection()
        self._reconcile_autocomplete(
            resolved_cursor_state.source_position,
            current_selection.is_empty,
        )
        self._refresh_active_projection()
        self._ensure_caret_visible()
        self._refresh_caret_layers()
        self._restart_caret_blink()
        if selection_paints_changed(previous_selection, current_selection):
            self._request_viewport_update()
        self._update_caret_paint(previous_caret_rect)
        self._emit_cursor_position_changed()
        log_prompt_editor_probe(
            "caret_publication.publish.end",
            reason=reason,
            changed=True,
            surface=self._surface_state(),
        )

    def publish_deferred(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Publish raw source positions while projection reflow remains deferred."""

        previous_caret_rect = self._current_caret_rect()
        previous_selection = self._selection()
        self.replace_states(
            cursor_state=cursor_state,
            anchor_state=anchor_state,
            clear_caret_rect_override=True,
            reset_preferred_x=True,
        )
        self._ensure_caret_visible()
        self._refresh_deferred_caret_layers()
        self._restart_caret_blink()
        if selection_paints_changed(previous_selection, self._selection()):
            self._request_viewport_update()
        self._update_caret_paint(previous_caret_rect)
        self._emit_cursor_position_changed()

    def publish_direct_feedback(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
    ) -> None:
        """Publish direct-feedback positions without a committed projection remap."""

        self.replace_states(
            cursor_state=cursor_state,
            anchor_state=anchor_state,
            clear_caret_rect_override=True,
            reset_preferred_x=False,
        )
        self.refresh_visibility()

    def refresh_visibility(self) -> None:
        """Reveal the committed caret and restart its visual blink cycle."""

        self._ensure_caret_visible()
        self._restart_caret_blink()

    def replace_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        clear_caret_rect_override: bool,
        reset_preferred_x: bool,
    ) -> PromptCursorState:
        """Replace source-driven caret states and synchronize source positions."""

        self._state.replace_states(
            cursor_state=cursor_state,
            anchor_state=anchor_state,
            clear_caret_rect_override=clear_caret_rect_override,
            reset_preferred_x=reset_preferred_x,
        )
        return self.sync_editing_session()

    def remap_after_projection_publication(
        self,
        projection_document: PromptProjectionDocument,
    ) -> PromptCursorState:
        """Resolve current caret states through a newly published projection."""

        return self.replace_states(
            cursor_state=projection_document.caret_map.resolve_state(self.cursor_state),
            anchor_state=projection_document.caret_map.resolve_state(self.anchor_state),
            clear_caret_rect_override=True,
            reset_preferred_x=False,
        )

    def sync_editing_session(self) -> PromptCursorState:
        """Synchronize source cursor ownership from projection caret metadata."""

        return self._editing_session.set_cursor_positions(
            cursor_position=self.cursor_state.source_position,
            anchor_position=self.anchor_state.source_position,
        )

    def mark_source_edit_horizontal_movement_origin(self) -> None:
        """Make the next horizontal move leave same-source wrap affinity."""

        self._state.mark_source_edit_horizontal_movement_origin()

    def _resolve_state(
        self,
        state: PromptProjectionCaretState,
        *,
        preserve_unmapped_source_position: bool,
    ) -> PromptProjectionCaretState:
        """Resolve one state while optionally retaining a deferred source position."""

        resolved = self._editor_state.projection.document.caret_map.resolve_state(state)
        if (
            preserve_unmapped_source_position
            and resolved.source_position != state.source_position
        ):
            return state
        return resolved


__all__ = ["PromptProjectionCaretPublicationOwner"]
