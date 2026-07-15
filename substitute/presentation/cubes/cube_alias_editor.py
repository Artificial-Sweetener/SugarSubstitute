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

"""Inline editor for cube aliases using shared cube-card text layout."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QFont,
    QFontMetrics,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPaintEvent,
    QPainter,
)
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    ThemeColor,
    isDarkTheme,
)

from substitute.presentation.cubes.cube_alias_text_layout import (
    CubeAliasTextLayout,
    layout_cube_alias_text,
    prefix_token_range,
)


class CubeAliasEditor(QWidget):
    """Edit one cube alias with cube-card text geometry and prefix-token behavior."""

    accepted = Signal(str)
    cancelled = Signal()
    editingFinished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a transparent single-line cube alias editor."""

        super().__init__(parent)
        self._text = ""
        self._original_text = ""
        self._cursor_index = 0
        self._selection_anchor: int | None = None
        self._token_range: tuple[int, int] | None = None
        self._editing_active = False
        self._primary_font = QFont(self.font())
        self._text_color = QColor()
        self.setObjectName("cubeAliasEditor")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.hide()

    def begin(self, text: str) -> None:
        """Start editing one alias and select all text."""

        self._original_text = text
        self.setText(text)
        self._selection_anchor = 0
        self._cursor_index = len(self._text)
        self._editing_active = True
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.show()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.update()

    def text(self) -> str:
        """Return current editor text."""

        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        """Replace current editor text and refresh token state."""

        self._text = text
        self._token_range = prefix_token_range(text)
        self._cursor_index = max(0, min(self._cursor_index, len(self._text)))
        self._selection_anchor = self._clamped_anchor(self._selection_anchor)
        self.update()

    def setTextColor(self, color: QColor) -> None:
        """Set primary text color used by the editor."""

        self._text_color = QColor(color)
        self.update()

    def setPrimaryFont(self, font: QFont) -> None:
        """Set the primary body font used for layout."""

        self._primary_font = QFont(font)
        self.setFont(self._primary_font)
        self.update()

    def cursorIndex(self) -> int:
        """Return current cursor index for tests and host synchronization."""

        return self._cursor_index

    def selectionRange(self) -> tuple[int, int] | None:
        """Return the current ordered selection range when present."""

        return self._selection_range()

    def isEditing(self) -> bool:
        """Return whether this editor is actively editing an alias."""

        return self._editing_active

    def selectRange(self, start: int, end: int) -> None:
        """Select a text range and move the cursor to the range end."""

        bounded_start = self._bounded_index(start)
        bounded_end = self._bounded_index(end)
        self._selection_anchor = bounded_start
        self._cursor_index = bounded_end
        self.update()

    def commit(self) -> None:
        """Emit accepted stripped text and finish editing."""

        if not self._editing_active:
            return
        committed = self._text.strip()
        self._finish_editing()
        self.hide()
        if committed and committed != self._original_text:
            self.accepted.emit(committed)
        self.editingFinished.emit()

    def cancel(self) -> None:
        """Restore/cancel editing and emit cancelled."""

        if not self._editing_active:
            return
        self._text = self._original_text
        self._token_range = prefix_token_range(self._text)
        self._finish_editing()
        self.hide()
        self.cancelled.emit()
        self.editingFinished.emit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Commit editing when a mouse press lands outside the editor."""

        if (
            self._editing_active
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(watched, QWidget)
            and watched is not self
            and not self.isAncestorOf(watched)
        ):
            self.commit()
        return super().eventFilter(watched, event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        """Commit aliases when focus leaves, matching normal line-edit rename."""

        self.commit()
        super().focusOutEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Handle single-line alias editing keyboard commands."""

        key = event.key()
        modifiers = event.modifiers()
        if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.commit()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
            return
        if key == Qt.Key.Key_A and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.selectRange(0, len(self._text))
            event.accept()
            return
        if key == Qt.Key.Key_C and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._copy_selection()
            event.accept()
            return
        if key == Qt.Key.Key_X and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._cut_selection()
            event.accept()
            return
        if key == Qt.Key.Key_V and modifiers & Qt.KeyboardModifier.ControlModifier:
            self._insert_text(QApplication.clipboard().text())
            event.accept()
            return
        if key == Qt.Key.Key_Backspace:
            self._backspace()
            event.accept()
            return
        if key == Qt.Key.Key_Delete:
            self._delete()
            event.accept()
            return
        if key == Qt.Key.Key_Left:
            self._move_left(
                extend=bool(modifiers & Qt.KeyboardModifier.ShiftModifier),
                by_word=bool(modifiers & Qt.KeyboardModifier.ControlModifier),
            )
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            self._move_right(
                extend=bool(modifiers & Qt.KeyboardModifier.ShiftModifier),
                by_word=bool(modifiers & Qt.KeyboardModifier.ControlModifier),
            )
            event.accept()
            return
        if key == Qt.Key.Key_Home:
            self._move_cursor(
                0,
                extend=bool(modifiers & Qt.KeyboardModifier.ShiftModifier),
            )
            event.accept()
            return
        if key == Qt.Key.Key_End:
            self._move_cursor(
                len(self._text),
                extend=bool(modifiers & Qt.KeyboardModifier.ShiftModifier),
            )
            event.accept()
            return

        text = event.text()
        if text and (not text.isspace() or text == " "):
            self._insert_text(text)
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Move the caret while snapping clicks inside the prefix token."""

        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        index = self._index_at_x(event.position().x())
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._move_cursor(index, extend=True)
        else:
            self._selection_anchor = index
            self._cursor_index = index
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Extend drag selection while snapping through the prefix token."""

        if not event.buttons() & Qt.MouseButton.LeftButton:
            super().mouseMoveEvent(event)
            return
        if self._selection_anchor is None:
            self._selection_anchor = self._cursor_index
        self._cursor_index = self._index_at_x(event.position().x())
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Select the full prefix token when it is double-clicked."""

        token_range = self._token_range
        if (
            event.button() == Qt.MouseButton.LeftButton
            and token_range is not None
            and self._x_hits_prefix(event.position().x())
        ):
            self.selectRange(token_range[0], token_range[1])
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Paint the edited alias, selection, and caret using cube-card layout."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect())
        layout = self._layout(painter)
        self._draw_selection(painter, layout)
        self._draw_layout_text(painter, layout)
        self._draw_selected_layout_text(painter, layout)
        self._draw_caret(painter, layout)

    def _layout(self, painter: QPainter) -> CubeAliasTextLayout:
        """Return current text layout for the editor row."""

        return layout_cube_alias_text(
            painter,
            text=self._text,
            row_rect=QRectF(self.rect()),
            primary_font=self._primary_font,
        )

    def _draw_layout_text(
        self,
        painter: QPainter,
        layout: CubeAliasTextLayout,
    ) -> None:
        """Draw the editable text segments without changing alias content."""

        color = self._resolved_text_color()
        if layout.prefix_segment is not None:
            self._draw_text_at_baseline(
                painter,
                text=layout.prefix_segment.text,
                x=layout.prefix_segment.rect.x(),
                baseline_y=layout.prefix_segment.baseline_y,
                font=layout.prefix_segment.font,
                color=color,
            )
        self._draw_text_at_baseline(
            painter,
            text=layout.body_segment.text,
            x=layout.body_segment.rect.x(),
            baseline_y=layout.body_segment.baseline_y,
            font=layout.body_segment.font,
            color=color,
        )

    @staticmethod
    def _draw_text_at_baseline(
        painter: QPainter,
        *,
        text: str,
        x: float,
        baseline_y: float,
        font: QFont,
        color: QColor,
    ) -> None:
        """Draw text at one explicit baseline."""

        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QPointF(x, baseline_y), text)

    def _draw_selection(
        self,
        painter: QPainter,
        layout: CubeAliasTextLayout,
    ) -> None:
        """Draw selection rectangles behind selected text."""

        selection = self._selection_range()
        if selection is None:
            return
        start, end = self._expanded_for_token(*selection)
        if start == end:
            return
        start_x = self._x_for_index(start, layout)
        end_x = self._x_for_index(end, layout)
        if end_x < start_x:
            start_x, end_x = end_x, start_x
        painter.fillRect(
            QRectF(
                start_x, layout.row_rect.y(), end_x - start_x, layout.row_rect.height()
            ),
            self._resolved_selection_color(),
        )

    def _draw_selected_layout_text(
        self,
        painter: QPainter,
        layout: CubeAliasTextLayout,
    ) -> None:
        """Draw selected text with QFluent line-edit highlighted text color."""

        selection = self._selection_range()
        if selection is None:
            return
        start, end = selection
        if start == end:
            return
        start_x = self._x_for_index(start, layout)
        end_x = self._x_for_index(end, layout)
        if end_x < start_x:
            start_x, end_x = end_x, start_x

        painter.save()
        painter.setClipRect(
            QRectF(
                start_x, layout.row_rect.y(), end_x - start_x, layout.row_rect.height()
            )
        )
        color = self._resolved_selected_text_color()
        if layout.prefix_segment is not None:
            self._draw_text_at_baseline(
                painter,
                text=layout.prefix_segment.text,
                x=layout.prefix_segment.rect.x(),
                baseline_y=layout.prefix_segment.baseline_y,
                font=layout.prefix_segment.font,
                color=color,
            )
        self._draw_text_at_baseline(
            painter,
            text=layout.body_segment.text,
            x=layout.body_segment.rect.x(),
            baseline_y=layout.body_segment.baseline_y,
            font=layout.body_segment.font,
            color=color,
        )
        painter.restore()

    def _draw_caret(
        self,
        painter: QPainter,
        layout: CubeAliasTextLayout,
    ) -> None:
        """Draw the caret on the shared body baseline."""

        if self._selection_range() is not None:
            return
        caret_x = self._x_for_index(self._cursor_index, layout)
        painter.setPen(ThemeColor.PRIMARY.color())
        painter.drawLine(
            QPointF(caret_x, layout.baseline_y - 13),
            QPointF(caret_x, layout.baseline_y + 3),
        )

    def _resolved_text_color(self) -> QColor:
        """Return configured text color or the current palette text color."""

        if self._text_color.isValid():
            return QColor(self._text_color)
        return QColor(self.palette().text().color())

    @staticmethod
    def _resolved_selection_color() -> QColor:
        """Return the QFluent line-edit selection fill for the active theme."""

        if isDarkTheme():
            return QColor(ThemeColor.PRIMARY.color())
        return QColor(ThemeColor.LIGHT_1.color())

    @staticmethod
    def _resolved_selected_text_color() -> QColor:
        """Return the QFluent line-edit selected text color for the active theme."""

        return QColor(Qt.GlobalColor.black if isDarkTheme() else Qt.GlobalColor.white)

    def _insert_text(self, text: str) -> None:
        """Insert text at the cursor, replacing any selected range."""

        if not text:
            return
        selection = self._selection_range()
        if selection is not None:
            self._replace_range(*self._expanded_for_token(*selection), text)
            return
        self._replace_range(self._cursor_index, self._cursor_index, text)

    def _backspace(self) -> None:
        """Delete the previous text unit, treating the prefix as one token."""

        selection = self._selection_range()
        if selection is not None:
            self._replace_range(*self._expanded_for_token(*selection), "")
            return
        token_range = self._token_range
        if (
            token_range is not None
            and token_range[0] < self._cursor_index <= token_range[1]
        ):
            self._replace_range(token_range[0], token_range[1], "")
            return
        if self._cursor_index > 0:
            self._replace_range(self._cursor_index - 1, self._cursor_index, "")

    def _delete(self) -> None:
        """Delete the next text unit, treating the prefix as one token."""

        selection = self._selection_range()
        if selection is not None:
            self._replace_range(*self._expanded_for_token(*selection), "")
            return
        token_range = self._token_range
        if (
            token_range is not None
            and token_range[0] <= self._cursor_index < token_range[1]
        ):
            self._replace_range(token_range[0], token_range[1], "")
            return
        if self._cursor_index < len(self._text):
            self._replace_range(self._cursor_index, self._cursor_index + 1, "")

    def _replace_range(self, start: int, end: int, replacement: str) -> None:
        """Replace one text range and move the cursor to the replacement end."""

        bounded_start = self._bounded_index(start)
        bounded_end = self._bounded_index(end)
        if bounded_end < bounded_start:
            bounded_start, bounded_end = bounded_end, bounded_start
        self._text = self._text[:bounded_start] + replacement + self._text[bounded_end:]
        self._cursor_index = bounded_start + len(replacement)
        self._selection_anchor = None
        self._token_range = prefix_token_range(self._text)
        self.update()

    def _copy_selection(self) -> None:
        """Copy selected text to the clipboard."""

        selection = self._selection_range()
        if selection is None:
            return
        start, end = selection
        QApplication.clipboard().setText(self._text[start:end])

    def _cut_selection(self) -> None:
        """Cut selected text to the clipboard."""

        selection = self._selection_range()
        if selection is None:
            return
        start, end = self._expanded_for_token(*selection)
        QApplication.clipboard().setText(self._text[start:end])
        self._replace_range(start, end, "")

    def _move_left(self, *, extend: bool, by_word: bool = False) -> None:
        """Move the cursor one unit left."""

        selection = self._selection_range()
        if selection is not None and not extend:
            self._move_cursor(selection[0], extend=False)
            return
        if by_word:
            self._move_cursor(self._previous_word_boundary(), extend=extend)
            return
        token_range = self._token_range
        if token_range is not None and self._cursor_index == token_range[1]:
            self._move_cursor(token_range[0], extend=extend)
            return
        self._move_cursor(max(0, self._cursor_index - 1), extend=extend)

    def _move_right(self, *, extend: bool, by_word: bool = False) -> None:
        """Move the cursor one unit right."""

        selection = self._selection_range()
        if selection is not None and not extend:
            self._move_cursor(selection[1], extend=False)
            return
        if by_word:
            self._move_cursor(self._next_word_boundary(), extend=extend)
            return
        token_range = self._token_range
        if token_range is not None and self._cursor_index == token_range[0]:
            self._move_cursor(token_range[1], extend=extend)
            return
        self._move_cursor(min(len(self._text), self._cursor_index + 1), extend=extend)

    def _previous_word_boundary(self) -> int:
        """Return the previous Ctrl+Left boundary with prefix as one token."""

        token_range = self._token_range
        if token_range is not None:
            token_start, token_end = token_range
            if token_start < self._cursor_index <= token_end:
                return token_start

        index = self._cursor_index
        while index > 0 and self._text[index - 1].isspace():
            index -= 1
        body_floor = token_range[1] if token_range is not None else 0
        while index > body_floor and not self._text[index - 1].isspace():
            index -= 1
        if token_range is not None and index <= body_floor:
            return body_floor if self._cursor_index > body_floor else token_range[0]
        return index

    def _next_word_boundary(self) -> int:
        """Return the next Ctrl+Right boundary with prefix as one token."""

        token_range = self._token_range
        if token_range is not None:
            token_start, token_end = token_range
            if token_start <= self._cursor_index < token_end:
                return token_end

        index = self._cursor_index
        text_length = len(self._text)
        while index < text_length and self._text[index].isspace():
            index += 1
        while index < text_length and not self._text[index].isspace():
            index += 1
        return index

    def _move_cursor(self, index: int, *, extend: bool) -> None:
        """Move the cursor and optionally extend selection."""

        bounded = self._bounded_index(index)
        if extend and self._selection_anchor is None:
            self._selection_anchor = self._cursor_index
        elif not extend:
            self._selection_anchor = None
        self._cursor_index = bounded
        self.update()

    def _selection_range(self) -> tuple[int, int] | None:
        """Return ordered current selection range when non-empty."""

        if (
            self._selection_anchor is None
            or self._selection_anchor == self._cursor_index
        ):
            return None
        start = min(self._selection_anchor, self._cursor_index)
        end = max(self._selection_anchor, self._cursor_index)
        return self._expanded_for_token(start, end)

    def _expanded_for_token(self, start: int, end: int) -> tuple[int, int]:
        """Expand a range to include the full prefix token when intersecting it."""

        token_range = self._token_range
        if token_range is None:
            return (start, end)
        token_start, token_end = token_range
        if start < token_end and end > token_start:
            return (min(start, token_start), max(end, token_end))
        return (start, end)

    def _x_for_index(self, index: int, layout: CubeAliasTextLayout) -> float:
        """Return the local x-coordinate for one text index."""

        bounded = self._bounded_index(index)
        prefix = layout.prefix_segment
        if prefix is not None and bounded <= prefix.end:
            if bounded <= prefix.start:
                return prefix.rect.x()
            return prefix.rect.x() + prefix.rect.width()
        body = layout.body_segment
        body_offset = max(0, bounded - body.start)
        width = QFontMetrics(body.font).horizontalAdvance(body.text[:body_offset])
        return body.rect.x() + width

    def _index_at_x(self, x: float) -> int:
        """Return nearest text index for a local x-coordinate."""

        image, painter = self._offscreen_painter()
        layout = self._layout(painter)
        prefix = layout.prefix_segment
        if (
            prefix is not None
            and prefix.rect.x() <= x <= prefix.rect.x() + prefix.rect.width()
        ):
            painter.end()
            _ = image
            midpoint = prefix.rect.x() + (prefix.rect.width() / 2)
            return prefix.start if x < midpoint else prefix.end

        body = layout.body_segment
        metrics = QFontMetrics(body.font)
        local_x = max(0.0, x - body.rect.x())
        best_index = body.start
        best_distance = abs(local_x)
        for offset in range(1, len(body.text) + 1):
            width = metrics.horizontalAdvance(body.text[:offset])
            distance = abs(local_x - width)
            if distance < best_distance:
                best_distance = distance
                best_index = body.start + offset
        painter.end()
        _ = image
        return self._bounded_index(best_index)

    def _x_hits_prefix(self, x: float) -> bool:
        """Return whether a local x-coordinate hits the prefix token."""

        image, painter = self._offscreen_painter()
        layout = self._layout(painter)
        painter.end()
        _ = image
        prefix = layout.prefix_segment
        return (
            prefix is not None
            and prefix.rect.x() <= x <= prefix.rect.x() + prefix.rect.width()
        )

    def _offscreen_painter(self) -> tuple[QImage, QPainter]:
        """Return an active offscreen painter for non-paint-event metrics."""

        image = QImage(
            max(1, self.width()),
            max(1, self.height()),
            QImage.Format.Format_ARGB32,
        )
        return image, QPainter(image)

    def _finish_editing(self) -> None:
        """Stop active editing and remove application-level mouse watching."""

        self._editing_active = False
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def _bounded_index(self, index: int) -> int:
        """Clamp one text index to the current alias."""

        return max(0, min(index, len(self._text)))

    def _clamped_anchor(self, anchor: int | None) -> int | None:
        """Clamp a nullable selection anchor."""

        if anchor is None:
            return None
        return self._bounded_index(anchor)


__all__ = ["CubeAliasEditor"]
