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

"""Own projection undo payloads, availability, and clipboard history routing."""

from __future__ import annotations

from collections.abc import Callable

from ..core.editing.cursor_state import PromptCursorState
from ..core.editing.session import PromptEditingSession
from ..core.projection.caret import PromptProjectionCaretState
from ..interactions.clipboard_history_controller import PromptClipboardHistoryActions
from ..layout.checkpoints import capture_layout_checkpoint
from .caret_state_owner import PromptProjectionCaretStateOwner
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .frame_state import PromptProjectionEditorState
from .session import PromptProjectionSession
from .undo_payload import PromptProjectionUndoPayload


class PromptProjectionHistoryOwner:
    """Publish source history with its matching projection restoration state."""

    def __init__(
        self,
        *,
        editing_session: PromptEditingSession[PromptProjectionUndoPayload],
        caret_state: PromptProjectionCaretStateOwner,
        projection_session: PromptProjectionSession,
        editor_state: PromptProjectionEditorState,
        layout: PromptLayoutEditToFrameCoordinator,
        set_cursor_positions: Callable[[int, int], object],
        publish_undo_available: Callable[[bool], None],
        publish_redo_available: Callable[[bool], None],
    ) -> None:
        """Bind the state owners needed to capture and restore editing history."""

        self._editing_session = editing_session
        self._caret_state = caret_state
        self._projection_session = projection_session
        self._editor_state = editor_state
        self._layout = layout
        self._set_cursor_positions = set_cursor_positions
        self._publish_undo_available = publish_undo_available
        self._publish_redo_available = publish_redo_available
        self._clipboard_history_actions: PromptClipboardHistoryActions | None = None

    def bind_clipboard_history(
        self,
        clipboard_history_actions: PromptClipboardHistoryActions,
    ) -> None:
        """Bind the runtime-created clipboard history controller exactly once."""

        if self._clipboard_history_actions is not None:
            raise RuntimeError("Clipboard history actions were already bound.")
        self._clipboard_history_actions = clipboard_history_actions

    @property
    def clipboard_history_actions(self) -> PromptClipboardHistoryActions:
        """Return the initialized clipboard and history action port."""

        actions = self._clipboard_history_actions
        if actions is None:
            raise RuntimeError("Clipboard history actions are not bound.")
        return actions

    def can_undo(self) -> bool:
        """Return whether the source editing session can undo."""

        return self._editing_session.can_undo()

    def can_redo(self) -> bool:
        """Return whether the source editing session can redo."""

        return self._editing_session.can_redo()

    def set_clipboard_history_cursor_state(
        self,
        cursor_state: PromptCursorState,
    ) -> None:
        """Apply a clipboard/history cursor state through projection caret routing."""

        self._set_cursor_positions(
            cursor_state.cursor_position,
            cursor_state.anchor_position,
        )

    def undo_restoration_payload(self) -> PromptProjectionUndoPayload:
        """Capture passive projection state for one source undo snapshot."""

        paint_input = self._layout.frame.paint_input
        return PromptProjectionUndoPayload(
            cursor_state=self._caret_state.cursor_state,
            anchor_state=self._caret_state.anchor_state,
            expanded_source_range=self._projection_session.expanded_source_range,
            document_view=self._editor_state.projection_semantic.document,
            render_plan=self._editor_state.projection_semantic.render_plan,
            layout_checkpoint=capture_layout_checkpoint(
                self._layout.frame.output,
                palette_key=int(paint_input.palette.cacheKey()),
                semantic_palette=paint_input.semantic_palette,
            ),
        )

    def undo_comparison_payload(
        self,
    ) -> tuple[
        PromptProjectionCaretState,
        PromptProjectionCaretState,
        tuple[int, int] | None,
    ]:
        """Return projection state that contributes to undo snapshot equality."""

        return (
            self._caret_state.cursor_state,
            self._caret_state.anchor_state,
            self._projection_session.expanded_source_range,
        )

    def emit_undo_available_changed(self, available: bool) -> None:
        """Publish an undo availability transition from edit execution."""

        self._publish_undo_available(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Publish a redo availability transition from edit execution."""

        self._publish_redo_available(available)


__all__ = ["PromptProjectionHistoryOwner"]
