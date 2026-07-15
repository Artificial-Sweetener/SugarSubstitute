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

"""Render one shared terminal-style output surface."""

from __future__ import annotations

from collections.abc import Callable
from types import MethodType
from weakref import ReferenceType, WeakMethod, ref

from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication, QFrame, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import PlainTextEdit  # type: ignore[import-untyped]
from qfluentwidgets import qconfig
from shiboken6 import isValid as _shiboken_is_valid

from sugarsubstitute_shared.presentation.widgets.scrolling import (
    configure_qfluent_scroll_surface,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)
from sugarsubstitute_shared.presentation.terminal.ansi import (
    TerminalStyledLine,
    TerminalTextSpan,
)
from sugarsubstitute_shared.presentation.terminal.output_style import (
    build_terminal_output_log_stylesheet,
    build_terminal_output_stylesheet,
    create_terminal_output_font,
)
from sugarsubstitute_shared.presentation.terminal.output_transcript import (
    TerminalOutputMutation,
    TerminalOutputMutationKind,
    TerminalOutputTranscript,
)


class TerminalOutputView(QFrame):
    """Render one reusable terminal output surface bound to a transcript stream."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        min_height: int | None = None,
        max_height: int | None = None,
    ) -> None:
        """Build the terminal view as one shared terminal surface."""

        super().__init__(parent)
        self._stream: TerminalOutputStream | None = None
        self._direct_transcript = TerminalOutputTranscript(max_lines=None)
        self._follow_tail_enabled = True
        self._follow_tail_update_pending = False

        self.setObjectName("TerminalOutputView")
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(1, 1, 1, 1)
        root_layout.setSpacing(0)

        self._log_view = PlainTextEdit(self)
        self._log_view.setObjectName("TerminalOutputLog")
        self._log_view.setMinimumWidth(0)
        self._log_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._log_view.viewport().setObjectName("TerminalOutputViewport")
        self._log_view.setReadOnly(True)
        self._log_view.setUndoRedoEnabled(False)
        self._log_view.setCursorWidth(0)
        self._log_view.setLineWrapMode(PlainTextEdit.LineWrapMode.WidgetWidth)
        self._log_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._log_view.setViewportMargins(0, 0, 0, 2)
        self._disable_smooth_scrolling()
        terminal_layer = getattr(self._log_view, "layer", None)
        if terminal_layer is not None:
            terminal_layer.hide()
        # Keep the transcript visually close to the viewport bottom.
        self._log_view.document().setDocumentMargin(0)
        self._log_view.setFont(create_terminal_output_font())
        self._log_view.setStyleSheet(build_terminal_output_log_stylesheet())
        if min_height is not None:
            self._log_view.setMinimumHeight(min_height)
        if max_height is not None:
            self._log_view.setMaximumHeight(max_height)
        root_layout.addWidget(self._log_view)

        self._follow_tail_timer = QTimer(self)
        self._follow_tail_timer.setSingleShot(True)
        self._follow_tail_timer.timeout.connect(self._apply_pending_follow_tail_update)
        self._log_view.verticalScrollBar().rangeChanged.connect(
            self._handle_vertical_range_changed
        )
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

    @property
    def log_view(self) -> PlainTextEdit:
        """Return the underlying text widget for host wrappers and tests."""

        return self._log_view

    def set_stream(self, stream: TerminalOutputStream | None) -> None:
        """Bind this view to one terminal stream and replay existing history."""

        if self._stream is not None:
            self._stream.mutation_applied.disconnect(self._apply_stream_mutation)
            self._stream.cleared.disconnect(self._clear_visible_output)

        self._stream = stream
        self._clear_visible_output()
        if stream is None:
            self._direct_transcript.clear()
            self._log_view.setMaximumBlockCount(0)
            return

        self._log_view.setMaximumBlockCount(stream.max_lines)
        self._replace_output(stream.styled_snapshot())
        stream.mutation_applied.connect(self._apply_stream_mutation)
        stream.cleared.connect(self._clear_visible_output)

    def append_line(self, line: str) -> None:
        """Append one terminal record directly to the visible output surface."""

        if self._stream is not None:
            self._stream.append_line(line)
            return
        mutation = self._direct_transcript.apply_record(line)
        if mutation is None:
            return
        self._apply_mutation(mutation)

    def clear_output(self) -> None:
        """Clear the bound stream when available, or clear visible output only."""

        if self._stream is not None:
            self._stream.clear()
            return
        self._direct_transcript.clear()
        self._clear_visible_output()

    def copy_all_output(self) -> None:
        """Copy the current rendered output to the system clipboard."""

        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setText(self._log_view.toPlainText())

    @Slot()
    def _clear_visible_output(self) -> None:
        """Clear only the rendered text surface."""

        self._log_view.clear()

    def _replace_output(self, lines: tuple[TerminalStyledLine, ...]) -> None:
        """Replace the visible output from a buffered transcript snapshot."""

        self._clear_visible_output()
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for index, line in enumerate(lines):
            if index > 0:
                cursor.insertBlock()
            _insert_styled_line(cursor, line)
        self._log_view.setTextCursor(cursor)
        self._request_follow_tail_update()

    def _apply_theme_styles(self) -> None:
        """Reapply direct terminal styles after theme or accent changes."""

        self._log_view.setStyleSheet(build_terminal_output_log_stylesheet())
        self.setStyleSheet(build_terminal_output_stylesheet())

    def _disable_smooth_scrolling(self) -> None:
        """Disable QFluent wheel smoothing so terminal output tracks immediately."""

        configure_qfluent_scroll_surface(self._log_view)

    @Slot(object)
    def _apply_stream_mutation(self, mutation: object) -> None:
        """Apply one incremental mutation received from the bound stream."""

        self._apply_mutation(mutation)

    def _apply_mutation(self, mutation: object) -> None:
        """Apply one visible transcript mutation to the shared text widget."""

        if not isinstance(mutation, TerminalOutputMutation):
            raise TypeError(
                "TerminalOutputView expected a TerminalOutputMutation from the stream."
            )
        if mutation.kind is TerminalOutputMutationKind.APPEND_LINE:
            self._append_visible_line(mutation.styled_line)
        elif mutation.kind is TerminalOutputMutationKind.REPLACE_LAST_LINE:
            self._replace_last_visible_line(mutation.styled_line)
        else:
            raise ValueError(f"Unsupported terminal output mutation: {mutation.kind!r}")
        self._request_follow_tail_update()

    def _append_visible_line(self, line: TerminalStyledLine) -> None:
        """Append one rendered line without rebuilding the whole document."""

        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self._log_view.toPlainText():
            cursor.insertBlock()
        _insert_styled_line(cursor, line)
        self._log_view.setTextCursor(cursor)

    def _replace_last_visible_line(self, line: TerminalStyledLine) -> None:
        """Replace the current tail row without rebuilding the whole document."""

        if not self._log_view.toPlainText():
            self._append_visible_line(line)
            return
        last_block = self._log_view.document().lastBlock()
        cursor = QTextCursor(self._log_view.document())
        cursor.setPosition(last_block.position())
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        _insert_styled_line(cursor, line)
        self._log_view.setTextCursor(cursor)

    def _request_follow_tail_update(self) -> None:
        """Queue one coalesced follow-tail sync for the next event-loop turn."""

        if not self._follow_tail_enabled:
            return
        self._follow_tail_update_pending = True
        if self._follow_tail_timer.isActive():
            return
        self._follow_tail_timer.start(0)

    @Slot()
    def _apply_pending_follow_tail_update(self) -> None:
        """Apply one queued follow-tail sync after Qt has advanced layout once."""

        if not self._follow_tail_enabled or not self._follow_tail_update_pending:
            return
        self._follow_tail_update_pending = False
        self._pin_to_bottom()

    @Slot(int, int)
    def _handle_vertical_range_changed(
        self,
        _minimum: int,
        _maximum: int,
    ) -> None:
        """Re-pin the viewport when wrapped layout changes the scroll range."""

        if not self._follow_tail_enabled:
            return
        self._pin_to_bottom()

    def _pin_to_bottom(self) -> None:
        """Move the viewport to the newest rendered output."""

        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def connect_theme_refresh(
    widget: object,
    refresh: Callable[[], None],
) -> None:
    """Connect one live-widget refresh callback to QFluent theme changes."""

    widget_ref = _weak_ref_or_none(widget)
    refresh_ref = _weak_method_or_none(refresh)
    disconnected = False

    def _disconnect_theme_signals() -> None:
        """Detach this refresh callback from process-wide QFluent signals."""

        nonlocal disconnected
        if disconnected:
            return
        disconnected = True
        for signal in (qconfig.themeChangedFinished, qconfig.themeColorChanged):
            try:
                signal.disconnect(_refresh)
            except (RuntimeError, TypeError):
                continue

    def _resolve_widget() -> object | None:
        """Return the widget wrapper while it is still available."""

        return widget_ref() if widget_ref is not None else widget

    def _resolve_refresh() -> Callable[[], None] | None:
        """Return the refresh callable while its owning instance is alive."""

        return refresh_ref() if refresh_ref is not None else refresh

    def _refresh(*_args: object) -> None:
        target_widget = _resolve_widget()
        if target_widget is None or not _is_live_qt_object(target_widget):
            _disconnect_theme_signals()
            return
        refresh_callback = _resolve_refresh()
        if refresh_callback is None:
            _disconnect_theme_signals()
            return
        try:
            refresh_callback()
        except RuntimeError as error:
            if _is_deleted_qt_object_error(error):
                _disconnect_theme_signals()
                return
            raise

    def _disconnect_on_destroyed(*_args: object) -> None:
        """Detach process-wide theme refresh hooks when the widget is destroyed."""

        _disconnect_theme_signals()

    callbacks = getattr(widget, "_appearance_refresh_callbacks", None)
    if not isinstance(callbacks, list):
        callbacks = []
        setattr(widget, "_appearance_refresh_callbacks", callbacks)
    callbacks.append(_refresh)
    callbacks.append(_disconnect_on_destroyed)
    destroyed_signal = getattr(widget, "destroyed", None)
    if destroyed_signal is not None:
        try:
            destroyed_signal.connect(_disconnect_on_destroyed)
        except (RuntimeError, TypeError):
            pass
    qconfig.themeChangedFinished.connect(_refresh)
    qconfig.themeColorChanged.connect(_refresh)


def _weak_ref_or_none(target: object) -> ReferenceType[object] | None:
    """Return a weak object reference when the target type supports it."""

    try:
        return ref(target)
    except TypeError:
        return None


def _weak_method_or_none(
    callback: Callable[[], None],
) -> WeakMethod[Callable[[], None]] | None:
    """Return a weak bound-method reference for instance-owned callbacks."""

    if not isinstance(callback, MethodType):
        return None
    return WeakMethod(callback)


def _is_live_qt_object(target: object) -> bool:
    """Return whether a PySide wrapper still owns a valid C++ object."""

    try:
        return bool(_shiboken_is_valid(target))
    except (RuntimeError, TypeError):
        return False


def _is_deleted_qt_object_error(error: RuntimeError) -> bool:
    """Return whether Qt raised because a Python wrapper outlived its C++ object."""

    message = str(error)
    return "Internal C++ object" in message and "already deleted" in message


_ANSI_FOREGROUND_COLORS = {
    "black": "#17191c",
    "red": "#f66151",
    "green": "#33d17a",
    "yellow": "#e5a50a",
    "blue": "#3584e4",
    "magenta": "#c061cb",
    "cyan": "#33c7de",
    "white": "#deddda",
    "bright_black": "#77767b",
    "bright_red": "#ff7b72",
    "bright_green": "#57e389",
    "bright_yellow": "#f8e45c",
    "bright_blue": "#62a0ea",
    "bright_magenta": "#dc8add",
    "bright_cyan": "#5bc8af",
    "bright_white": "#ffffff",
}


def _insert_styled_line(cursor: QTextCursor, line: TerminalStyledLine) -> None:
    """Insert one styled terminal line at the cursor position."""

    if not line.spans:
        cursor.insertText(line.plain_text)
        return
    for span in line.spans:
        if span.foreground is None and not span.bold:
            cursor.setCharFormat(QTextCharFormat())
            cursor.insertText(span.text)
            continue
        cursor.insertText(span.text, _format_for_span(span))


def _format_for_span(span: TerminalTextSpan) -> QTextCharFormat:
    """Return the Qt character format for one terminal text span."""

    text_format = QTextCharFormat()
    if span.bold:
        text_format.setFontWeight(QFont.Weight.Bold)
    if span.foreground is not None:
        color = _ANSI_FOREGROUND_COLORS.get(span.foreground)
        if color is not None:
            text_format.setForeground(QColor(color))
    return text_format


__all__ = ["TerminalOutputView"]
