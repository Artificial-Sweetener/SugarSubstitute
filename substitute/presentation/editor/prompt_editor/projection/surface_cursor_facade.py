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

"""Own the Qt-compatible cursor contract exposed by the projection surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF
from PySide6.QtGui import QTextCursor

from ..core.editing.cursor_state import PromptCursorState
from ..core.editing.session import PromptEditingSession
from ..core.editing.source_commands import PromptSourceEditOrigin
from ..core.projection.caret import PromptProjectionCaretState
from ..interactions import prompt_word_bounds
from ..interactions.cursor_adapter import PromptCursorAdapter, PromptCursorAdapterHost
from .caret_geometry_owner import PromptProjectionCaretGeometryOwner
from .caret_movement_controller import PromptProjectionCaretMovementController
from .caret_publication_owner import PromptProjectionCaretPublicationOwner
from .caret_state_owner import PromptProjectionCaretStateOwner
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .frame_state import PromptProjectionEditorState
from .freshness_controller import PromptProjectionFreshnessController
from .surface_input_runtime import PromptProjectionSurfaceInputRuntime
from .surface_presentation_runtime import PromptProjectionSurfacePresentationRuntime
from .undo_payload import PromptProjectionUndoPayload


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceCursorBindings:
    """Declare state and effects required by the public cursor contract."""

    host: PromptCursorAdapterHost
    editing_session: PromptEditingSession[PromptProjectionUndoPayload]
    input_runtime: PromptProjectionSurfaceInputRuntime
    editor_state: PromptProjectionEditorState
    layout: PromptLayoutEditToFrameCoordinator
    caret_geometry: PromptProjectionCaretGeometryOwner
    caret_publication: PromptProjectionCaretPublicationOwner
    caret_state: PromptProjectionCaretStateOwner
    caret_movement: PromptProjectionCaretMovementController
    freshness: PromptProjectionFreshnessController
    presentation: PromptProjectionSurfacePresentationRuntime
    flush_pending_projection: Callable[[str], None]
    editing_enabled: Callable[[], bool]
    visible_scroll_bar: Callable[[], object]
    has_pending_projection_update: Callable[[], bool]
    scroll_offset: Callable[[], float]


class PromptProjectionSurfaceCursorFacade:
    """Implement one authoritative Qt-compatible source cursor contract."""

    def __init__(self, bindings: PromptProjectionSurfaceCursorBindings) -> None:
        """Store cursor state owners and projection geometry effects."""

        self._bindings = bindings

    @property
    def cursor_position(self) -> int:
        """Return the editing-session-owned raw source cursor position."""

        return self._bindings.editing_session.cursor_position

    @property
    def anchor_position(self) -> int:
        """Return the editing-session-owned raw source selection anchor."""

        return self._bindings.editing_session.anchor_position

    def text_cursor(self) -> PromptCursorAdapter:
        """Return a Qt-like cursor wrapper backed by the editing session."""

        return PromptCursorAdapter(
            self._bindings.host,
            self._bindings.editing_session.cursor_state,
        )

    def set_text_cursor(self, cursor: object) -> None:
        """Apply a Qt-compatible source cursor snapshot to the editor."""

        self.commit_state(
            self._state_from_compatible_cursor(cursor),
            reason="set_text_cursor",
        )

    def cursor_for_position(self, position: QPoint) -> PromptCursorAdapter:
        """Return a cursor wrapper after hit-testing one viewport-local point."""

        bindings = self._bindings
        bindings.flush_pending_projection("cursor_for_position")
        caret_state = bindings.layout.frame.geometry.hit_testing.hit_test(
            QPointF(position),
            scroll_offset=bindings.scroll_offset(),
        )
        self.set_from_projection_hit(caret_state, keep_anchor=False)
        return self.text_cursor()

    def source_text(self) -> str:
        """Return source text for the editing-session cursor adapter."""

        return self._bindings.editing_session.source_text

    def state(self) -> PromptCursorState:
        """Return the current source cursor state for a cursor adapter."""

        return self._bindings.editing_session.cursor_state

    def commit_state(
        self,
        cursor_state: PromptCursorState,
        *,
        reason: str,
    ) -> PromptCursorState:
        """Commit cursor adapter state through projection-aware placement."""

        _ = reason
        return self.set_positions(
            cursor_position=cursor_state.cursor_position,
            anchor_position=cursor_state.anchor_position,
        )

    @staticmethod
    def is_keep_anchor_mode(mode: object | None) -> bool:
        """Return whether an opaque cursor mode is QTextCursor KeepAnchor."""

        return mode == QTextCursor.MoveMode.KeepAnchor

    def finish_pending_key_edit_block(self, *, reason: str) -> None:
        """Flush key-owned edit groups before cursor-adapter mutations."""

        self._bindings.input_runtime.edit_execution.finish_pending_key_edit_block(
            reason=reason
        )

    def begin_edit_block(self, *, finish_typing: bool = True) -> None:
        """Begin an edit block requested by the source cursor adapter."""

        self._bindings.input_runtime.edit_execution.begin_edit_block(
            finish_typing=finish_typing
        )

    def end_edit_block(self) -> None:
        """End an edit block requested by the source cursor adapter."""

        self._bindings.input_runtime.edit_execution.end_edit_block()

    def delete_selection(self) -> None:
        """Delete the live selection requested by the source cursor adapter."""

        bindings = self._bindings
        if not bindings.editing_enabled():
            return
        selection = bindings.editing_session.selection()
        if selection.is_empty:
            return
        self.finish_pending_key_edit_block(reason="delete_selection")
        bindings.input_runtime.source_commands.replace_source_range(
            start=selection.start,
            end=selection.end,
            replacement_text="",
            origin=PromptSourceEditOrigin.TYPED,
            command_name="cursor_delete_selection",
        )

    def insert_text(self, text: str) -> None:
        """Insert text requested by the source cursor adapter."""

        self._bindings.input_runtime.text_mutations.insert_text(
            text,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            command_name="cursor_insert_text",
        )

    def cursor_rect(self) -> QRect:
        """Return the current viewport-local caret rect."""

        bindings = self._bindings
        bindings.visible_scroll_bar()
        bindings.has_pending_projection_update()
        transient_rect = bindings.caret_geometry.transient_document_rect()
        if transient_rect is not None:
            return transient_rect.translated(
                0.0,
                -bindings.scroll_offset(),
            ).toAlignedRect()
        bindings.flush_pending_projection("cursor_rect")
        return bindings.caret_geometry.current_viewport_rect().toAlignedRect()

    def input_method_caret_rect(self, source_position: int) -> QRectF:
        """Return a viewport-local caret rectangle for input-method geometry."""

        bindings = self._bindings
        bindings.flush_pending_projection("input_method_caret_rect")
        source_text = bindings.editing_session.source_text
        caret_state = bindings.editor_state.projection.document.caret_map.state_for_source_position(
            min(max(0, source_position), len(source_text))
        )
        return bindings.layout.frame.geometry.caret.cursor_rect(
            caret_state,
            scroll_offset=bindings.scroll_offset(),
        )

    def set_positions(
        self,
        *,
        cursor_position: int,
        anchor_position: int,
    ) -> PromptCursorState:
        """Resolve raw cursor positions through the authoritative caret map."""

        bindings = self._bindings
        bindings.flush_pending_projection("set_cursor_positions")
        if bindings.freshness.has_stale_projection_geometry():
            bindings.presentation.rebuild.rebuild()
        cursor_state = PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=anchor_position,
        ).clamped(len(bindings.editing_session.source_text))
        bindings.caret_geometry.clear_transient()
        caret_map = bindings.editor_state.projection.document.caret_map
        bindings.caret_publication.publish(
            cursor_state=caret_map.state_for_source_position(
                cursor_state.cursor_position
            ),
            anchor_state=caret_map.state_for_source_position(
                cursor_state.anchor_position
            ),
        )
        return bindings.editing_session.cursor_state

    def set_from_projection_hit(
        self,
        caret_state: PromptProjectionCaretState,
        keep_anchor: bool,
        *,
        caret_rect_override: QRectF | None = None,
    ) -> None:
        """Persist one layout-resolved caret state as the live cursor position."""

        bindings = self._bindings
        anchor_state = bindings.caret_state.anchor_state if keep_anchor else caret_state
        bindings.caret_publication.publish(
            cursor_state=caret_state,
            anchor_state=anchor_state,
            caret_rect_override=caret_rect_override,
        )

    def move_by_operation(
        self,
        operation: object,
        *,
        keep_anchor: bool,
    ) -> PromptCursorState:
        """Move the caret according to one supported QTextCursor operation."""

        bindings = self._bindings
        bindings.flush_pending_projection("move_cursor_by_operation")
        if operation == QTextCursor.MoveOperation.End:
            target = len(bindings.editing_session.source_text)
            return self.set_positions(
                cursor_position=target,
                anchor_position=self.anchor_position if keep_anchor else target,
            )
        if operation == QTextCursor.MoveOperation.Start:
            return self.set_positions(
                cursor_position=0,
                anchor_position=self.anchor_position if keep_anchor else 0,
            )
        if operation == QTextCursor.MoveOperation.Left:
            bindings.caret_movement.move_horizontally(
                bindings.layout.frame.geometry,
                -1,
                keep_anchor=keep_anchor,
            )
        elif operation == QTextCursor.MoveOperation.Right:
            bindings.caret_movement.move_horizontally(
                bindings.layout.frame.geometry,
                +1,
                keep_anchor=keep_anchor,
            )
        elif operation == QTextCursor.MoveOperation.Up:
            bindings.caret_movement.move_vertically(
                bindings.layout.frame.geometry,
                -1,
                keep_anchor=keep_anchor,
            )
        elif operation == QTextCursor.MoveOperation.Down:
            bindings.caret_movement.move_vertically(
                bindings.layout.frame.geometry,
                +1,
                keep_anchor=keep_anchor,
            )
        return bindings.editing_session.cursor_state

    def move_horizontally(self, direction: int, *, keep_anchor: bool) -> None:
        """Move through the current projection without forcing deferred work."""

        bindings = self._bindings
        bindings.caret_movement.move_horizontally(
            bindings.layout.frame.geometry,
            direction,
            keep_anchor=keep_anchor,
        )

    def move_vertically(self, direction: int, *, keep_anchor: bool) -> None:
        """Move by visual line while preserving stale-safe typing projection."""

        bindings = self._bindings
        bindings.caret_movement.move_vertically(
            bindings.layout.frame.geometry,
            direction,
            keep_anchor=keep_anchor,
        )

    def select_by_mode(self, mode: object) -> PromptCursorState:
        """Select the supported logical range around the current cursor."""

        bindings = self._bindings
        bindings.flush_pending_projection("select_by_mode")
        if mode != QTextCursor.SelectionType.WordUnderCursor:
            return bindings.editing_session.cursor_state
        start, end = prompt_word_bounds(self.source_text(), self.cursor_position)
        if start == end:
            return bindings.editing_session.cursor_state
        return self.set_positions(cursor_position=end, anchor_position=start)

    @staticmethod
    def _state_from_compatible_cursor(cursor: object) -> PromptCursorState:
        """Return source cursor state from a QTextCursor-like public object."""

        if isinstance(cursor, PromptCursorAdapter):
            return cursor.cursor_state()
        cursor_state_method = getattr(cursor, "cursor_state", None)
        if callable(cursor_state_method):
            cursor_state = cursor_state_method()
            if isinstance(cursor_state, PromptCursorState):
                return cursor_state
        position_method = getattr(cursor, "position", None)
        selection_start_method = getattr(cursor, "selectionStart", None)
        selection_end_method = getattr(cursor, "selectionEnd", None)
        if not (
            callable(position_method)
            and callable(selection_start_method)
            and callable(selection_end_method)
        ):
            raise TypeError("Cursor must expose position and selection bounds.")
        cursor_position = int(position_method())
        selection_start = int(selection_start_method())
        selection_end = int(selection_end_method())
        anchor_position = (
            selection_end if cursor_position == selection_start else selection_start
        )
        return PromptCursorState(
            cursor_position=cursor_position,
            anchor_position=anchor_position,
        )


__all__ = [
    "PromptProjectionSurfaceCursorBindings",
    "PromptProjectionSurfaceCursorFacade",
]
