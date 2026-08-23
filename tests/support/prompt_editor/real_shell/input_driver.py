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

"""Drive real prompt-editor key and pointer interactions for one mounted session."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QKeySequence, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.prompt_editor.real_shell.models import (
    PromptEditorKeyRoute,
    PromptEditorStateSnapshot,
    PromptEditorTraceAction,
    PromptFieldHandle,
)
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)


class StateSnapshotCapture(Protocol):
    """Capture state needed to describe an interaction route."""

    def __call__(
        self, field: PromptFieldHandle, *, label: str, settle_cycles: int = 6
    ) -> PromptEditorStateSnapshot:
        """Capture the mounted editor state."""


class PromptEditorInputDriver:
    """Drive input through the production prompt-editor event surfaces."""

    def __init__(
        self,
        *,
        shell: QWidget,
        input_canvas_provider: Callable[[], QWidget],
        canvas_provider: Callable[[str], QWidget | None],
        canvas_activator: Callable[[str], None],
        trace_actions: list[PromptEditorTraceAction],
        snapshot_capture: StateSnapshotCapture,
    ) -> None:
        """Bind the driver to one real-shell session's input and trace owners."""

        self._shell = shell
        self._input_canvas_provider = input_canvas_provider
        self._canvas_provider = canvas_provider
        self._canvas_activator = canvas_activator
        self._trace_actions = trace_actions
        self._capture_state_snapshot = snapshot_capture

    def focus_editor(self, field: PromptFieldHandle) -> QWidget:
        """Focus the real prompt projection surface used for keyboard input."""

        field.editor.show()
        self._shell.show()
        self._shell.raise_()
        self._shell.activateWindow()
        focus_target = editor_event_widget(field.editor)
        focus_target.setFocus(Qt.FocusReason.OtherFocusReason)
        wait_for_qt_condition(focus_target.hasFocus, timeout_ms=3000)
        return focus_target

    def replace_text_with_keys(self, field: PromptFieldHandle, text: str) -> None:
        """Replace prompt source through real selection and key events."""

        target = self.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.SelectAll)
        QTest.keyClicks(target, text)
        self._trace_actions.append(PromptEditorTraceAction("replace_text", text))
        wait_for_queued_qt_turn()

    def type_text(self, field: PromptFieldHandle, text: str) -> None:
        """Type text into the real prompt editor focus target."""

        target = self.focus_editor(field)
        QTest.keyClicks(target, text)
        self._trace_actions.append(PromptEditorTraceAction("type_text", text))
        wait_for_queued_qt_turn()

    def paste_text(self, field: PromptFieldHandle, text: str) -> None:
        """Paste text through the real clipboard and editor key route."""

        target = self.focus_editor(field)
        QApplication.clipboard().setText(text)
        QTest.keySequence(target, QKeySequence.StandardKey.Paste)
        self._trace_actions.append(PromptEditorTraceAction("paste_text", text))
        wait_for_queued_qt_turn()

    def undo(self, field: PromptFieldHandle) -> None:
        """Undo through the real editor key route."""

        target = self.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.Undo)
        self._trace_actions.append(PromptEditorTraceAction("undo", ""))
        wait_for_queued_qt_turn()

    def redo(self, field: PromptFieldHandle) -> None:
        """Redo through the real editor key route."""

        target = self.focus_editor(field)
        QTest.keySequence(target, QKeySequence.StandardKey.Redo)
        self._trace_actions.append(PromptEditorTraceAction("redo", ""))
        wait_for_queued_qt_turn()

    def set_source_cursor_position(
        self,
        field: PromptFieldHandle,
        position: int,
    ) -> None:
        """Place the real source cursor at one exact source boundary."""

        cursor = cast(Any, field.editor).textCursor()
        cursor.setPosition(position)
        field.editor.setTextCursor(cursor)
        wait_for_queued_qt_turn()

    def click_projected_source_position(
        self,
        field: PromptFieldHandle,
        position: int,
    ) -> None:
        """Click the production caret geometry for one source boundary."""

        self.set_source_cursor_position(field, position)
        point = field.editor.cursorRect().center()
        self.click_editor_viewport_point(field, point)
        self._trace_actions.append(
            PromptEditorTraceAction(
                "click_projected_source_position",
                f"{position}@{point.x()},{point.y()}",
            )
        )

    def click_editor_viewport_point(
        self,
        field: PromptFieldHandle,
        point: QPoint,
    ) -> None:
        """Click one exact viewport-local point through the production mouse route."""

        target = field.editor.viewport()
        QTest.mouseClick(
            target,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            point,
        )
        self._trace_actions.append(
            PromptEditorTraceAction(
                "click_editor_viewport_point",
                f"{point.x()},{point.y()}",
            )
        )
        wait_for_queued_qt_turn()

    def set_rich_rendering(
        self,
        field: PromptFieldHandle,
        *,
        enabled: bool,
    ) -> None:
        """Switch the real editor between projected and exact-source display."""

        field.editor.setRichPromptRenderingEnabled(enabled)
        wait_for_queued_qt_turn()

    def press_key(
        self,
        field: PromptFieldHandle,
        key: Qt.Key,
        *,
        text: str = "",
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    ) -> PromptEditorKeyRoute:
        """Send one key event and return a before/after route diagnostic."""

        target = self.focus_editor(field)
        before = self._capture_state_snapshot(field, label="before-key")
        QTest.keyClick(target, key, modifiers)
        self._trace_actions.append(
            PromptEditorTraceAction(
                "press_key",
                text,
                key=enum_value(key),
                modifiers=enum_value(modifiers),
            )
        )
        wait_for_queued_qt_turn()
        after = self._capture_state_snapshot(field, label="after-key")
        return PromptEditorKeyRoute(
            key_name=Qt.Key(key).name,
            text=text,
            modifiers=str(Qt.KeyboardModifier(modifiers).name),
            focus_before=before.focus_widget_path,
            focus_after=after.focus_widget_path,
            active_window_before=before.active_window_path,
            active_window_after=after.active_window_path,
            source_before=before.source_text,
            source_after=after.source_text,
            cursor_before=before.cursor_position,
            cursor_after=after.cursor_position,
            dropdown_visible_before=before.popup_visual_visible,
            dropdown_visible_after=after.popup_visual_visible,
            ghost_visible_before=before.ghost_visual_visible,
            ghost_visible_after=after.ghost_visual_visible,
            inserted_text=source_inserted_text(before.source_text, after.source_text),
        )

    def press_key_burst(
        self,
        field: PromptFieldHandle,
        key: Qt.Key,
        *,
        repetitions: int,
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    ) -> None:
        """Send contiguous key events before settling the event loop once."""

        if repetitions < 1:
            raise ValueError("repetitions must be positive")
        target = self.focus_editor(field)
        for _iteration in range(repetitions):
            QTest.keyClick(target, key, modifiers)
        self._trace_actions.append(
            PromptEditorTraceAction(
                "press_key_burst",
                str(repetitions),
                key=enum_value(key),
                modifiers=enum_value(modifiers),
            )
        )
        wait_for_queued_qt_turn()

    def press_key_and_capture_immediate_state(
        self,
        field: PromptFieldHandle,
        key: Qt.Key,
        *,
        label: str,
    ) -> PromptEditorStateSnapshot:
        """Capture owner state synchronously after one production key event."""

        target = self.focus_editor(field)
        QTest.keyClick(target, key)
        self._trace_actions.append(
            PromptEditorTraceAction(
                "press_key_immediate",
                "",
                key=enum_value(key),
            )
        )
        return self._capture_state_snapshot(
            field,
            label=label,
            settle_cycles=0,
        )

    def type_text_and_capture_immediate_state(
        self,
        field: PromptFieldHandle,
        text: str,
        *,
        label: str,
    ) -> PromptEditorStateSnapshot:
        """Capture owner state synchronously after production text key events."""

        target = self.focus_editor(field)
        QTest.keyClicks(target, text)
        self._trace_actions.append(PromptEditorTraceAction("type_text_immediate", text))
        return self._capture_state_snapshot(
            field,
            label=label,
            settle_cycles=0,
        )

    def move_cursor_to_end(self, field: PromptFieldHandle) -> None:
        """Move the real prompt cursor to the end through Qt cursor APIs."""

        cursor = cast(Any, field.editor).textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        field.editor.setTextCursor(cursor)
        wait_for_queued_qt_turn()

    def scroll_editor(self, field: PromptFieldHandle, target: str) -> None:
        """Scroll the mounted editor viewport through its real scrollbar owner."""

        scrollbar = field.editor.verticalScrollBar()
        if target == "top":
            value = scrollbar.minimum()
        elif target == "middle":
            value = (scrollbar.minimum() + scrollbar.maximum()) // 2
        elif target == "bottom":
            value = scrollbar.maximum()
        else:
            raise AssertionError(f"unknown scroll target {target!r}")
        scrollbar.setValue(value)
        self._trace_actions.append(PromptEditorTraceAction("scroll_editor", target))
        wait_for_queued_qt_turn()

    def seed_text_directly(self, field: PromptFieldHandle, text: str) -> None:
        """Seed editor text for setup-only abuse paths through a replayable action."""

        self.press_key(field, Qt.Key.Key_Escape)
        cast(Any, field.editor).setPlainText(text)
        self._trace_actions.append(PromptEditorTraceAction("seed_text_directly", text))
        wait_for_queued_qt_turn()
        self.move_cursor_to_end(field)

    def move_cursor_inside_text(self, field: PromptFieldHandle, text: str) -> None:
        """Place the caret inside the first matching source fragment."""

        source = field.editor.toPlainText()
        index = source.index(text)
        cursor = cast(Any, field.editor).textCursor()
        cursor.setPosition(index + 1)
        field.editor.setTextCursor(cursor)
        wait_for_queued_qt_turn()

    def click_away_from_editor(self) -> None:
        """Click a real focusable shell widget outside the prompt editor."""

        focus_target = self._input_canvas_provider()
        focus_target.setFocus(Qt.FocusReason.MouseFocusReason)
        QTest.mouseClick(
            focus_target,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            focus_target.rect().center(),
        )
        self._trace_actions.append(PromptEditorTraceAction("click_away", ""))
        wait_for_queued_qt_turn()

    def switch_canvas(self, label: str) -> None:
        """Switch a real canvas tab through the shell canvas tab manager."""

        self._canvas_activator(label)
        canvas = self._canvas_provider(label)
        if isinstance(canvas, QWidget):
            canvas.setFocus(Qt.FocusReason.OtherFocusReason)
        self._trace_actions.append(PromptEditorTraceAction("switch_canvas", label))
        wait_for_queued_qt_turn()


def editor_event_widget(editor: PromptEditor) -> QWidget:
    """Return the real widget receiving prompt editor key events."""
    focus_proxy = editor.focusProxy()
    return focus_proxy if isinstance(focus_proxy, QWidget) else editor


def source_inserted_text(before: str, after: str) -> str:
    """Return inserted source text for simple before/after diagnostics."""
    if after.startswith(before):
        return after[len(before) :]
    position = source_insert_position(before, after)
    return (
        ""
        if position is None
        else after[position : position + len(after) - len(before)]
    )


def source_insert_position(before: str, after: str) -> int | None:
    """Return the insertion offset when after is before plus text."""
    if len(after) <= len(before):
        return None
    prefix_length = 0
    while (
        prefix_length < min(len(before), len(after))
        and before[prefix_length] == after[prefix_length]
    ):
        prefix_length += 1
    suffix_length = 0
    while (
        suffix_length < len(before) - prefix_length
        and before[len(before) - 1 - suffix_length]
        == after[len(after) - 1 - suffix_length]
    ):
        suffix_length += 1
    return prefix_length if prefix_length + suffix_length == len(before) else None


def enum_value(value: object) -> int:
    """Return the integer payload for Qt enum and flag values."""
    raw_value = getattr(value, "value", value)
    return raw_value if isinstance(raw_value, int) else int(cast(Any, raw_value))
