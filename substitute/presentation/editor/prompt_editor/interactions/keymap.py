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

"""Route prompt-editor keyboard intent through narrow interaction protocols."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence

from ..editing_session.undo_coalescing import PromptUndoCoalescingActions
from ..models import (
    PromptEditorInteractionMode,
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from .clipboard_history_controller import PromptClipboardHistoryActions


class _PromptSurfaceEmphasisShortcutSignal(Protocol):
    """Emit keyboard emphasis shortcut intent from the surface key path."""

    def emit(self, delta: float, /) -> None:
        """Emit one emphasis delta accepted by the key handler."""


class PromptSurfaceKeyHost(Protocol):
    """Expose the bounded surface operations needed by key routing."""

    emphasisShortcutTriggered: _PromptSurfaceEmphasisShortcutSignal
    _editing_enabled: bool

    @property
    def anchor_position(self) -> int:
        """Return the current source-backed anchor position."""

    @property
    def cursor_position(self) -> int:
        """Return the current source-backed cursor position."""

    def toPlainText(self) -> str:
        """Return the current prompt source text."""

    def _insert_viewport_text(
        self,
        text: str,
    ) -> None:
        """Insert source text through the existing command/editing boundary."""

    def set_cursor_positions(
        self,
        *,
        cursor_position: int,
        anchor_position: int,
    ) -> object:
        """Persist source-backed cursor positions."""

    def _clear_pending_segment_word_selection(self) -> None:
        """Clear any pending segment word-selection follow-up."""

    def _move_horizontally(self, direction: int, *, keep_anchor: bool) -> None:
        """Move the caret horizontally through projection-aware geometry."""

    def _move_vertically(self, direction: int, *, keep_anchor: bool) -> None:
        """Move the caret vertically through projection-aware geometry."""

    def _backspace(self) -> None:
        """Delete the previous source boundary."""

    def _delete(self) -> None:
        """Delete the next source boundary."""


class PromptSurfaceKeyHandler:
    """Route surface key events while preserving existing edit boundaries."""

    def __init__(
        self,
        host: PromptSurfaceKeyHost,
        *,
        clipboard_history_actions: Callable[
            [],
            PromptClipboardHistoryActions | None,
        ],
        undo_coalescing_actions: Callable[
            [],
            PromptUndoCoalescingActions | None,
        ],
    ) -> None:
        """Bind the handler to the surface operations it may delegate to."""

        self._host = host
        self._clipboard_history_actions = clipboard_history_actions
        self._undo_coalescing_actions = undo_coalescing_actions

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle one key press or return false for default Qt processing."""

        host = self._host
        undo_coalescing = self._undo_coalescing_actions()
        if undo_coalescing is None:
            return False
        host._clear_pending_segment_word_selection()
        if event.key() not in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete}:
            undo_coalescing.finish_delete_group(reason="non_delete_key")

        if _has_plain_control_modifier(event.modifiers()):
            if event.key() == Qt.Key.Key_Up:
                undo_coalescing.finish_typing_group(reason="emphasis_shortcut")
                host.emphasisShortcutTriggered.emit(0.05)
                event.accept()
                return True
            if event.key() == Qt.Key.Key_Down:
                undo_coalescing.finish_typing_group(reason="emphasis_shortcut")
                host.emphasisShortcutTriggered.emit(-0.05)
                event.accept()
                return True

        if event.matches(QKeySequence.StandardKey.Copy):
            actions = self._clipboard_history_actions()
            if actions is None:
                return False
            actions.copy()
            event.accept()
            return True
        if event.matches(QKeySequence.StandardKey.Cut):
            actions = self._clipboard_history_actions()
            if actions is None:
                return False
            actions.cut()
            event.accept()
            return True
        if event.matches(QKeySequence.StandardKey.Paste):
            actions = self._clipboard_history_actions()
            if actions is None:
                return False
            actions.paste()
            event.accept()
            return True
        if event.matches(QKeySequence.StandardKey.SelectAll):
            actions = self._clipboard_history_actions()
            if actions is None:
                return False
            actions.select_all()
            event.accept()
            return True
        if event.matches(QKeySequence.StandardKey.Undo):
            if not host._editing_enabled:
                event.accept()
                return True
            actions = self._clipboard_history_actions()
            if actions is None:
                return False
            actions.undo()
            event.accept()
            return True
        if event.matches(QKeySequence.StandardKey.Redo):
            if not host._editing_enabled:
                event.accept()
                return True
            actions = self._clipboard_history_actions()
            if actions is None:
                return False
            actions.redo()
            event.accept()
            return True

        keep_anchor = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if event.key() == Qt.Key.Key_Left:
            undo_coalescing.finish_typing_group(reason="cursor_move")
            host._move_horizontally(-1, keep_anchor=keep_anchor)
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Right:
            undo_coalescing.finish_typing_group(reason="cursor_move")
            host._move_horizontally(+1, keep_anchor=keep_anchor)
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Up:
            undo_coalescing.finish_typing_group(reason="cursor_move")
            host._move_vertically(-1, keep_anchor=keep_anchor)
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Down:
            undo_coalescing.finish_typing_group(reason="cursor_move")
            host._move_vertically(+1, keep_anchor=keep_anchor)
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Home:
            undo_coalescing.finish_typing_group(reason="cursor_move")
            host.set_cursor_positions(
                cursor_position=0,
                anchor_position=host.anchor_position if keep_anchor else 0,
            )
            event.accept()
            return True
        if event.key() == Qt.Key.Key_End:
            undo_coalescing.finish_typing_group(reason="cursor_move")
            end_position = len(host.toPlainText())
            host.set_cursor_positions(
                cursor_position=end_position,
                anchor_position=host.anchor_position if keep_anchor else end_position,
            )
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Backspace:
            if not host._editing_enabled:
                event.accept()
                return True
            undo_coalescing.finish_typing_group(reason="backspace")
            undo_coalescing.begin_delete_group(
                key=event.key(),
                autorepeat=event.isAutoRepeat(),
            )
            host._backspace()
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Delete:
            if not host._editing_enabled:
                event.accept()
                return True
            undo_coalescing.finish_typing_group(reason="delete")
            undo_coalescing.begin_delete_group(
                key=event.key(),
                autorepeat=event.isAutoRepeat(),
            )
            host._delete()
            event.accept()
            return True
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if not host._editing_enabled:
                event.accept()
                return True
            undo_coalescing.finish_typing_group(reason="newline")
            host._insert_viewport_text("\n")
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Tab:
            undo_coalescing.finish_typing_group(reason="tab")
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Escape:
            undo_coalescing.finish_typing_group(reason="escape")
            event.accept()
            return True

        text = event.text()
        if (
            text
            and _is_plain_text_insertion_event(event)
            and (not text.isspace() or text in {" ", "\t"})
        ):
            if not host._editing_enabled:
                event.accept()
                return True
            if undo_coalescing.can_group_typed_text(text):
                undo_coalescing.begin_or_extend_typing_group(text)
            else:
                undo_coalescing.finish_typing_group(reason="typing_boundary")
            host._insert_viewport_text(text)
            event.accept()
            return True
        if text and not _is_plain_text_insertion_event(event):
            event.ignore()
            return True
        return False

    def handle_key_release(self, event: QKeyEvent) -> bool:
        """Accept delete-key releases while undo coalescing waits for idle."""

        if event.key() in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete}:
            event.accept()
            return True
        return False


class PromptKeymapHost(Protocol):
    """Expose editor-level operations needed by keymap orchestration."""

    @property
    def interaction_mode(self) -> PromptEditorInteractionMode:
        """Return the active interaction mode."""

    def enter_segment_reorder_mode_from_keymap(self) -> None:
        """Enter reorder mode for the Alt key path."""

    def cancel_segment_reorder_mode_from_keymap(
        self,
        intent: PromptReorderCancelIntent,
    ) -> None:
        """Cancel reorder mode for the Escape key path."""

    def commit_segment_reorder_mode_from_keymap(
        self,
        intent: PromptReorderCommitIntent,
    ) -> None:
        """Commit reorder mode for the Alt-release key path."""

    def move_keyboard_reorder_chip_from_keymap(
        self,
        intent: PromptReorderKeyboardMoveIntent,
    ) -> None:
        """Move the active reorder chip through the existing reorder owner."""

    def handle_exact_weight_key_press(self, event: QKeyEvent) -> bool:
        """Delegate active exact-weight editing key handling."""

    def handle_autocomplete_key_press_from_keymap(self, event: QKeyEvent) -> bool:
        """Delegate pre-edit autocomplete key handling."""

    def handle_autocomplete_post_key_press_from_keymap(
        self,
        event: QKeyEvent,
    ) -> None:
        """Delegate post-edit autocomplete refresh handling."""

    def clear_autocomplete_for_emphasis_shortcut_from_keymap(self) -> None:
        """Clear autocomplete after keyboard emphasis accepts a shortcut."""

    def clear_autocomplete_for_non_text_key_from_keymap(self) -> None:
        """Clear autocomplete after a non-text key is accepted by the surface."""

    def flush_semantic_refresh_from_keymap(self, *, reason: str) -> None:
        """Flush pending semantic refresh for key-owned syntax reasons."""

    def clear_keyboard_emphasis_session_from_keymap(self) -> None:
        """Clear keyboard-owned emphasis state when Ctrl is released."""


class PromptKeymapController:
    """Coordinate prompt-editor key routing without owning feature behavior."""

    def __init__(self, host: PromptKeymapHost) -> None:
        """Bind the controller to the keymap host."""

        self._host = host

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Handle pre-edit key routing that should intercept normal text editing."""

        if self._host.interaction_mode is PromptEditorInteractionMode.SEGMENT_REORDER:
            if self._handle_reorder_key_press(event):
                return True
            if event.key() == Qt.Key.Key_Escape:
                self._host.cancel_segment_reorder_mode_from_keymap(
                    PromptReorderCancelIntent(reason="escape")
                )
            return True

        if event.key() == Qt.Key.Key_Alt:
            self._host.enter_segment_reorder_mode_from_keymap()
            return True
        if self._host.handle_exact_weight_key_press(event):
            return True
        return self._host.handle_autocomplete_key_press_from_keymap(event)

    def handle_emphasis_shortcut_accepted(self) -> None:
        """Mute autocomplete after a keyboard emphasis shortcut is accepted."""

        self._host.clear_autocomplete_for_emphasis_shortcut_from_keymap()

    def handle_post_key_press(self, event: QKeyEvent) -> None:
        """Handle post-edit prompt operations that depend on updated source."""

        if self._host.interaction_mode is PromptEditorInteractionMode.SEGMENT_REORDER:
            return

        if self._host.interaction_mode is PromptEditorInteractionMode.TEXT_EDITING:
            if self._should_flush_semantic_refresh_for_key(event):
                self._host.flush_semantic_refresh_from_keymap(
                    reason="syntax_closing_key"
                )
            self._host.handle_autocomplete_post_key_press_from_keymap(event)

    def handle_key_release(self, event: QKeyEvent) -> bool:
        """Commit modifier-owned interaction state when the owning key releases."""

        if self._host.interaction_mode is PromptEditorInteractionMode.SEGMENT_REORDER:
            if event.key() == Qt.Key.Key_Alt:
                self._host.commit_segment_reorder_mode_from_keymap(
                    PromptReorderCommitIntent(reason="alt_release")
                )
            return True

        if event.key() == Qt.Key.Key_Control:
            self._host.clear_keyboard_emphasis_session_from_keymap()
        return False

    def _handle_reorder_key_press(self, event: QKeyEvent) -> bool:
        """Route reorder-mode arrow keys through typed keyboard move intents."""

        key = event.key()
        if key == Qt.Key.Key_Left:
            self._host.move_keyboard_reorder_chip_from_keymap(
                PromptReorderKeyboardMoveIntent(direction="left")
            )
            return True
        if key == Qt.Key.Key_Right:
            self._host.move_keyboard_reorder_chip_from_keymap(
                PromptReorderKeyboardMoveIntent(direction="right")
            )
            return True
        if key == Qt.Key.Key_Up:
            self._host.move_keyboard_reorder_chip_from_keymap(
                PromptReorderKeyboardMoveIntent(direction="up")
            )
            return True
        if key == Qt.Key.Key_Down:
            self._host.move_keyboard_reorder_chip_from_keymap(
                PromptReorderKeyboardMoveIntent(direction="down")
            )
            return True
        return False

    @staticmethod
    def _should_flush_semantic_refresh_for_key(event: QKeyEvent) -> bool:
        """Return whether a key should immediately publish completed syntax."""

        if bool(
            event.modifiers()
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            return False
        if event.key() in {
            Qt.Key.Key_ParenRight,
            Qt.Key.Key_BracketRight,
            Qt.Key.Key_BraceRight,
            Qt.Key.Key_Greater,
        }:
            return True
        return event.text() in {")", "]", "}", ">"}


def _has_plain_control_modifier(modifiers: Qt.KeyboardModifier) -> bool:
    """Return whether one key event carries Ctrl without Shift, Alt, or Meta."""

    if not modifiers & Qt.KeyboardModifier.ControlModifier:
        return False
    disallowed_modifiers = (
        Qt.KeyboardModifier.ShiftModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.MetaModifier
    )
    return not bool(modifiers & disallowed_modifiers)


def _is_plain_text_insertion_event(event: QKeyEvent) -> bool:
    """Return whether one key event should write its text into prompt source."""

    blocked_modifiers = (
        Qt.KeyboardModifier.ControlModifier
        | Qt.KeyboardModifier.AltModifier
        | Qt.KeyboardModifier.MetaModifier
    )
    return not bool(event.modifiers() & blocked_modifiers)


__all__ = [
    "PromptKeymapController",
    "PromptKeymapHost",
    "PromptSurfaceKeyHandler",
    "PromptSurfaceKeyHost",
]
