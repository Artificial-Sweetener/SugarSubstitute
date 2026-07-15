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

"""Route prompt-editor mouse selection and pointer interaction intent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxAction,
)

from ..models import PromptEditorInteractionMode
from ..projection.hit_testing import (
    PromptProjectionCaretHit,
    PromptProjectionDragSelectionTarget,
)
from ..projection.model import (
    PromptProjectionCaretState,
    PromptProjectionToken,
    PromptProjectionTokenKind,
)


class _PromptSurfaceMouseLayout(Protocol):
    """Expose projection-owned geometry queries needed by pointer routing."""

    def caret_hit_test(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretHit:
        """Return one caret placement for a viewport-local pointer position."""

    def resolve_drag_selection_endpoint(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        anchor_line_index: int | None = None,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionDragSelectionTarget:
        """Return one drag-selection endpoint resolved by projection geometry."""

    def hit_test(
        self,
        viewport_position: QPointF,
        *,
        scroll_offset: float,
        preferred_line_index: int | None = None,
    ) -> PromptProjectionCaretState:
        """Return the logical caret state for one viewport-local position."""

    def line_index_for_document_y(self, document_y: float) -> int | None:
        """Return the wrapped visual line index for one document-local y value."""


class _PromptSurfaceMouseProjectionSession(Protocol):
    """Expose token expansion without coupling pointer routing to the surface."""

    def expand_token(self, token: PromptProjectionToken) -> None:
        """Expand one projected token in the projection session."""


class PromptSurfaceMouseHost(Protocol):
    """Expose bounded surface operations needed by interim pointer routing."""

    _anchor_state: PromptProjectionCaretState
    _focus_host: QWidget | None
    _layout: _PromptSurfaceMouseLayout
    _session: _PromptSurfaceMouseProjectionSession
    _weight_click_handler: Callable[[QPointF], bool] | None
    _weight_double_click_handler: Callable[[QPointF], bool] | None

    def viewport(self) -> QWidget:
        """Return the viewport widget that owns pointer-local updates."""

    def hasFocus(self) -> bool:
        """Return whether the surface currently owns focus."""

    def setFocus(self, reason: Qt.FocusReason) -> None:
        """Assign focus to the surface for one Qt focus reason."""

    def toPlainText(self) -> str:
        """Return the current prompt source text."""

    def prompt_document_view(self) -> PromptDocumentView:
        """Return the current source-backed prompt document view."""

    def clear_autocomplete_preview_state(self) -> None:
        """Clear any active projection-owned autocomplete preview."""

    def _finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Commit key-owned edit groups before pointer interaction mutates state."""

    def set_cursor_positions(
        self,
        *,
        cursor_position: int,
        anchor_position: int,
    ) -> object:
        """Persist source-backed cursor positions."""

    def _current_caret_document_rect(self) -> QRectF:
        """Return the current document-local caret rectangle."""

    def _emit_mouse_interaction_finished(self) -> None:
        """Publish that a pointer selection interaction has finished."""

    def _flush_pending_projection_update(self, *, reason: str) -> None:
        """Flush any pending projection update required by pointer policy."""

    def has_pending_projection_update(self) -> bool:
        """Return whether projection work is waiting on the freshness owner."""

    def _rebuild_projection(self) -> None:
        """Refresh projection state after token expansion changes session state."""

    def _request_lora_context_menu(
        self,
        viewport_position: QPointF,
        global_pos: QPoint,
    ) -> bool:
        """Request a LoRA context menu for one pointer position."""

    def _scroll_offset(self) -> float:
        """Return the viewport scroll offset used by projection geometry."""

    def _set_caret_states(
        self,
        *,
        cursor_state: PromptProjectionCaretState,
        anchor_state: PromptProjectionCaretState,
        caret_rect_override: QRectF | None = None,
    ) -> None:
        """Persist projection-backed cursor and anchor states."""

    def _token_at_viewport_position(
        self,
        local_position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the projection token under a viewport-local position."""


@dataclass(slots=True)
class _DragSelectionSession:
    """Track the anchor and preferred wrapped line for one active drag selection."""

    anchor_state: PromptProjectionCaretState
    anchor_line_index: int | None
    preferred_line_index: int | None


class PromptSurfaceMouseHandler:
    """Route surface pointer events while preserving projection/editing ownership."""

    def __init__(self, host: PromptSurfaceMouseHost) -> None:
        """Bind pointer routing to the bounded surface operations it may use."""

        self._host = host
        self._hovered_token_id: str | None = None
        self._mouse_selecting = False
        self._drag_selection_session: _DragSelectionSession | None = None
        self._pending_segment_word_selection_range: tuple[int, int] | None = None

    @property
    def hovered_token_id(self) -> str | None:
        """Return the currently hovered projection token identity."""

        return self._hovered_token_id

    def viewport_position_from_mouse_event(self, event: QMouseEvent) -> QPointF:
        """Map one pointer event to viewport-local coordinates."""

        return QPointF(
            self._host.viewport().mapFromGlobal(event.globalPosition().toPoint())
        )

    def handle_mouse_press(self, event: QMouseEvent) -> bool:
        """Handle one public mouse press event from the surface."""

        self._host._finish_pending_key_edit_block(reason="mouse_press")
        self._host.clear_autocomplete_preview_state()
        return self.handle_viewport_mouse_press(
            event,
            viewport_position=self.viewport_position_from_mouse_event(event),
        )

    def handle_mouse_move(self, event: QMouseEvent) -> bool:
        """Handle one public mouse move event from the surface."""

        return self.handle_viewport_mouse_move(
            event,
            viewport_position=self.viewport_position_from_mouse_event(event),
        )

    def handle_mouse_double_click(self, event: QMouseEvent) -> bool:
        """Handle one public mouse double-click event from the surface."""

        return self.handle_viewport_mouse_double_click(
            event,
            viewport_position=self.viewport_position_from_mouse_event(event),
        )

    def handle_viewport_mouse_press(
        self,
        event: QMouseEvent,
        *,
        viewport_position: QPointF,
    ) -> bool:
        """Handle one viewport-local mouse press for token-aware selection."""

        host = self._host
        host._flush_pending_projection_update(reason="mouse_press")
        if event.button() == Qt.MouseButton.RightButton:
            if host._request_lora_context_menu(
                viewport_position, event.globalPosition().toPoint()
            ):
                event.accept()
                return True
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            self._drag_selection_session = None
            self.clear_pending_segment_word_selection()
            return False
        if host._weight_click_handler is not None and host._weight_click_handler(
            viewport_position
        ):
            self._mouse_selecting = False
            self._drag_selection_session = None
            event.accept()
            return True
        self._ensure_focus_host_owns_pointer_interaction()
        if self._consume_pending_segment_word_selection_click(
            viewport_position=viewport_position,
            modifiers=event.modifiers(),
        ):
            event.accept()
            return True
        self.clear_pending_segment_word_selection()
        caret_hit = host._layout.caret_hit_test(
            viewport_position,
            scroll_offset=host._scroll_offset(),
        )
        keep_anchor = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self._set_cursor_from_projection_hit(
            caret_hit.state,
            keep_anchor=keep_anchor,
            caret_rect_override=caret_hit.document_rect,
        )
        self._mouse_selecting = True
        caret_center_y = host._current_caret_document_rect().center().y()
        self._drag_selection_session = _DragSelectionSession(
            anchor_state=host._anchor_state,
            anchor_line_index=host._layout.line_index_for_document_y(caret_center_y),
            preferred_line_index=host._layout.line_index_for_document_y(caret_center_y),
        )
        event.accept()
        return True

    def handle_viewport_mouse_move(
        self,
        event: QMouseEvent,
        *,
        viewport_position: QPointF,
    ) -> bool:
        """Handle one viewport-local mouse move for hover and drag selection."""

        host = self._host
        if not self._mouse_selecting or self._drag_selection_session is None:
            if host.has_pending_projection_update():
                if self._hovered_token_id is not None:
                    self._hovered_token_id = None
                    host.viewport().update()
                return False
            self.update_hovered_token(viewport_position)
            return False
        host._flush_pending_projection_update(reason="mouse_move_drag")
        self.update_hovered_token(viewport_position)
        drag_target = host._layout.resolve_drag_selection_endpoint(
            viewport_position,
            scroll_offset=host._scroll_offset(),
            anchor_line_index=self._drag_selection_session.anchor_line_index,
            preferred_line_index=self._drag_selection_session.preferred_line_index,
        )
        self._drag_selection_session.preferred_line_index = drag_target.line_index
        host._set_caret_states(
            cursor_state=drag_target.state,
            anchor_state=self._drag_selection_session.anchor_state,
        )
        event.accept()
        return True

    def handle_viewport_mouse_release(self, event: QMouseEvent) -> bool:
        """Handle one viewport-local mouse release that ends drag selection."""

        if event.button() != Qt.MouseButton.LeftButton and not self._mouse_selecting:
            return False
        self._mouse_selecting = False
        self._drag_selection_session = None
        self._host._emit_mouse_interaction_finished()
        event.accept()
        return True

    def handle_viewport_mouse_double_click(
        self,
        event: QMouseEvent,
        *,
        viewport_position: QPointF,
    ) -> bool:
        """Handle one viewport-local token-aware mouse double click."""

        host = self._host
        host._flush_pending_projection_update(reason="mouse_double_click")
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self.clear_pending_segment_word_selection()
        if (
            host._weight_double_click_handler is not None
            and host._weight_double_click_handler(viewport_position)
        ):
            self._mouse_selecting = False
            self._drag_selection_session = None
            event.accept()
            return True
        self._ensure_focus_host_owns_pointer_interaction()
        token = host._token_at_viewport_position(viewport_position)
        if token is not None:
            token_selection_range = self._double_click_selection_range_for_token(token)
            if token_selection_range is not None:
                host.set_cursor_positions(
                    cursor_position=token_selection_range[1],
                    anchor_position=token_selection_range[0],
                )
                self._pending_segment_word_selection_range = token_selection_range
                self._mouse_selecting = False
                self._drag_selection_session = None
                event.accept()
                return True
            host._session.expand_token(token)
            host._rebuild_projection()
            host.set_cursor_positions(
                cursor_position=token.source_end,
                anchor_position=token.source_start,
            )
            self._mouse_selecting = False
            self._drag_selection_session = None
            event.accept()
            return True
        caret_state = host._layout.hit_test(
            viewport_position,
            scroll_offset=host._scroll_offset(),
        )
        segment_selection_range = self._segment_selection_range_at_source_position(
            caret_state.source_position
        )
        if segment_selection_range is None:
            return False
        host.set_cursor_positions(
            cursor_position=segment_selection_range[1],
            anchor_position=segment_selection_range[0],
        )
        self._pending_segment_word_selection_range = segment_selection_range
        self._mouse_selecting = False
        self._drag_selection_session = None
        event.accept()
        return True

    def update_hovered_token(self, local_position: QPointF) -> None:
        """Refresh the token currently under the mouse pointer."""

        token = self._host._token_at_viewport_position(local_position)
        next_token_id = None if token is None else token.token_id
        if next_token_id == self._hovered_token_id:
            return
        self._hovered_token_id = next_token_id
        self._host.viewport().update()

    def clear_hovered_token(self, *, update: bool = True) -> None:
        """Clear the current hover token and optionally repaint the viewport."""

        if self._hovered_token_id is None:
            return
        self._hovered_token_id = None
        if update:
            self._host.viewport().update()

    def clear_pointer_state_for_source_replacement(self) -> None:
        """Clear transient pointer state after source text replacement."""

        self._hovered_token_id = None
        self._pending_segment_word_selection_range = None

    def clear_pending_segment_word_selection(self) -> None:
        """Discard pending follow-up word selection after segment double-click."""

        self._pending_segment_word_selection_range = None

    def _set_cursor_from_projection_hit(
        self,
        caret_state: PromptProjectionCaretState,
        keep_anchor: bool,
        *,
        caret_rect_override: QRectF | None = None,
    ) -> None:
        """Persist one layout-resolved caret state as the live cursor position."""

        next_anchor_state = self._host._anchor_state if keep_anchor else caret_state
        self._host._set_caret_states(
            cursor_state=caret_state,
            anchor_state=next_anchor_state,
            caret_rect_override=caret_rect_override,
        )

    def _ensure_focus_host_owns_pointer_interaction(self) -> None:
        """Restore the pointer interaction focus owner before mutating selection."""

        focus_owner = self._host._focus_host
        if focus_owner is not None:
            if not focus_owner.hasFocus():
                focus_owner.setFocus(Qt.FocusReason.MouseFocusReason)
            return
        if not self._host.hasFocus():
            self._host.setFocus(Qt.FocusReason.MouseFocusReason)

    def _consume_pending_segment_word_selection_click(
        self,
        *,
        viewport_position: QPointF,
        modifiers: Qt.KeyboardModifier,
    ) -> bool:
        """Select one clicked word after a whole-segment double-click selection."""

        pending_range = self._pending_segment_word_selection_range
        if pending_range is None or modifiers != Qt.KeyboardModifier.NoModifier:
            return False
        caret_state = self._host._layout.hit_test(
            viewport_position,
            scroll_offset=self._host._scroll_offset(),
        )
        if not pending_range[0] <= caret_state.source_position <= pending_range[1]:
            return False
        start, end = prompt_word_bounds(
            self._host.toPlainText(), caret_state.source_position
        )
        if start == end:
            return False
        self._host.set_cursor_positions(
            cursor_position=end,
            anchor_position=start,
        )
        self._pending_segment_word_selection_range = None
        self._mouse_selecting = False
        return True

    def _segment_selection_range_at_source_position(
        self,
        position: int,
    ) -> tuple[int, int] | None:
        """Return the segment range selected for one plain-text double click."""

        for segment in self._host.prompt_document_view().segments:
            if segment.selection_start <= position <= segment.selection_end:
                return segment.selection_start, segment.selection_end
        return None

    def _double_click_selection_range_for_token(
        self,
        token: PromptProjectionToken,
    ) -> tuple[int, int] | None:
        """Return the preferred double-click selection range for one token."""

        if (
            token.kind is PromptProjectionTokenKind.EMPHASIS
            and token.content_start is not None
            and token.content_end is not None
        ):
            return token.content_start, token.content_end
        return None


def prompt_word_bounds(text: str, position: int) -> tuple[int, int]:
    """Return simple prompt-word bounds around one source position."""

    if not text:
        return position, position

    start = max(0, min(position, len(text)))
    end = start
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "_-"):
        start -= 1
    while end < len(text) and (text[end].isalnum() or text[end] in "_-"):
        end += 1
    return start, end


class PromptMouseSelectionHost(Protocol):
    """Expose editor-level mouse orchestration without owning feature semantics."""

    @property
    def interaction_mode(self) -> PromptEditorInteractionMode:
        """Return the active editor interaction mode."""

    def clear_mouse_emphasis_session(self) -> None:
        """Clear transient emphasis state before mouse-owned syntax actions."""

    def syntax_action_at_mouse_position(
        self,
        position: QPointF,
    ) -> PromptSyntaxAction | None:
        """Return the prepared syntax action at one mouse position."""

    def apply_mouse_syntax_action(self, action: PromptSyntaxAction) -> None:
        """Apply one prepared syntax action through the existing feature owner."""

    def schedule_mouse_release_autocomplete_refresh(self) -> None:
        """Request autocomplete refresh after mouse-driven caret movement."""

    def refresh_mouse_release_cursor_state(self) -> None:
        """Refresh active cursor-derived state after a mouse interaction."""


class PromptMouseSelectionController:
    """Coordinate editor-level mouse press/release handoffs."""

    def __init__(self, host: PromptMouseSelectionHost) -> None:
        """Bind mouse orchestration to the existing behavior host."""

        self._host = host

    def handle_mouse_press(self, event: QMouseEvent) -> bool:
        """Consume syntax-owned inline clicks before normal text editing."""

        if self._host.interaction_mode is not PromptEditorInteractionMode.TEXT_EDITING:
            return False

        self._host.clear_mouse_emphasis_session()
        syntax_action = self._host.syntax_action_at_mouse_position(event.position())
        if syntax_action is None:
            return False

        self._host.apply_mouse_syntax_action(syntax_action)
        return True

    def handle_mouse_release(self) -> None:
        """Refresh state after caret movement caused by mouse interaction."""

        if self._host.interaction_mode is PromptEditorInteractionMode.TEXT_EDITING:
            self._host.schedule_mouse_release_autocomplete_refresh()
        self._host.refresh_mouse_release_cursor_state()
