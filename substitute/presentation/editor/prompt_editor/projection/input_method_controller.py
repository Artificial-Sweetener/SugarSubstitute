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

"""Own input-method composition for the custom prompt projection surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QInputMethodEvent,
    QPainter,
    QPalette,
    QTextCharFormat,
    QTextLayout,
    QTextLine,
)

from substitute.presentation.text_coordinates import TextCoordinateMap


class PromptInputMethodHost(Protocol):
    """Expose source and presentation state needed by input-method composition."""

    @property
    def cursor_position(self) -> int:
        """Return the current Python source cursor position."""

    @property
    def anchor_position(self) -> int:
        """Return the current Python source selection anchor."""

    def toPlainText(self) -> str:  # noqa: N802
        """Return the current prompt source text."""

    def editing_enabled(self) -> bool:
        """Return whether the source accepts mutations."""

    def input_method_caret_rect(self, source_position: int) -> QRectF:
        """Return a viewport-local caret rectangle for a source position."""

    def replace_input_method_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
    ) -> None:
        """Commit one input-method replacement through the mutation owner."""


@dataclass(frozen=True, slots=True)
class PromptPreeditFormat:
    """Describe one UTF-16 preedit format range."""

    start: int
    length: int
    text_format: QTextCharFormat


@dataclass(frozen=True, slots=True)
class PromptPreeditState:
    """Describe transient composition without placing it in prompt source history."""

    source_start: int
    source_end: int
    text: str
    cursor_utf16: int
    cursor_visible: bool
    cursor_color: QColor | None
    formats: tuple[PromptPreeditFormat, ...]


class PromptInputMethodController:
    """Translate Qt input-method events into one source mutation per commit."""

    def __init__(self, host: PromptInputMethodHost) -> None:
        """Store the host while keeping preedit state transient and bounded."""

        self._host = host
        self._preedit: PromptPreeditState | None = None
        self._committing = False

    @property
    def preedit_state(self) -> PromptPreeditState | None:
        """Return the current immutable preedit snapshot when composing."""

        return self._preedit

    @property
    def is_composing(self) -> bool:
        """Return whether a non-empty preedit string is active."""

        return self._preedit is not None

    def handle_event(self, event: QInputMethodEvent) -> None:
        """Apply one Qt composition event without storing preedit in source text."""

        source_text = self._host.toPlainText()
        if self._preedit is None:
            source_start = min(self._host.cursor_position, self._host.anchor_position)
            source_end = max(self._host.cursor_position, self._host.anchor_position)
        else:
            source_start = self._preedit.source_start
            source_end = self._preedit.source_end

        commit_text = event.commitString()
        should_commit = (
            bool(commit_text)
            or event.replacementStart() != 0
            or event.replacementLength() != 0
        )
        if should_commit and self._host.editing_enabled():
            source_text, source_start = self._commit_event(
                source_text=source_text,
                source_start=source_start,
                source_end=source_end,
                event=event,
            )
            source_end = source_start

        preedit_text = event.preeditString()
        if not preedit_text:
            self._preedit = None
            return
        if not self._host.editing_enabled():
            self._preedit = None
            return
        cursor_utf16, cursor_visible, cursor_color = _preedit_cursor(
            event, preedit_text
        )
        self._preedit = PromptPreeditState(
            source_start=min(source_start, len(source_text)),
            source_end=min(source_end, len(source_text)),
            text=preedit_text,
            cursor_utf16=cursor_utf16,
            cursor_visible=cursor_visible,
            cursor_color=cursor_color,
            formats=_preedit_formats(event),
        )

    def cancel(self) -> None:
        """Discard transient composition without mutating prompt source text."""

        self._preedit = None

    def source_changed(self) -> None:
        """Cancel composition when an unrelated source owner replaces the document."""

        if not self._committing:
            self.cancel()

    def query(
        self,
        query: Qt.InputMethodQuery,
        *,
        font: QFont,
        palette: QPalette,
        input_method_hints: Qt.InputMethodHint,
        viewport_rect: QRectF,
    ) -> object | None:
        """Return the Qt input-method value for one supported query."""

        source_text = self._host.toPlainText()
        coordinates = TextCoordinateMap(source_text)
        cursor_position = self._host.cursor_position
        anchor_position = self._host.anchor_position
        if query is Qt.InputMethodQuery.ImEnabled:
            return self._host.editing_enabled()
        if query is Qt.InputMethodQuery.ImReadOnly:
            return not self._host.editing_enabled()
        if query is Qt.InputMethodQuery.ImHints:
            return input_method_hints
        if query is Qt.InputMethodQuery.ImFont:
            return font
        if query is Qt.InputMethodQuery.ImCursorRectangle:
            return self.cursor_rect(font=font, palette=palette)
        if query is Qt.InputMethodQuery.ImAnchorRectangle:
            return self._host.input_method_caret_rect(anchor_position)
        if query is Qt.InputMethodQuery.ImInputItemClipRectangle:
            return viewport_rect
        if query is Qt.InputMethodQuery.ImSurroundingText:
            return source_text
        if query in {
            Qt.InputMethodQuery.ImCursorPosition,
            Qt.InputMethodQuery.ImAbsolutePosition,
        }:
            return coordinates.python_to_utf16(cursor_position)
        if query is Qt.InputMethodQuery.ImAnchorPosition:
            return coordinates.python_to_utf16(anchor_position)
        if query is Qt.InputMethodQuery.ImCurrentSelection:
            return source_text[
                min(cursor_position, anchor_position) : max(
                    cursor_position, anchor_position
                )
            ]
        if query is Qt.InputMethodQuery.ImTextBeforeCursor:
            return source_text[:cursor_position]
        if query is Qt.InputMethodQuery.ImTextAfterCursor:
            return source_text[cursor_position:]
        if query is Qt.InputMethodQuery.ImMaximumTextLength:
            return 2_147_483_647
        return None

    def paint(self, painter: QPainter, *, font: QFont, palette: QPalette) -> None:
        """Paint the shaped preedit string and its input-method caret."""

        state = self._preedit
        if state is None:
            return
        layout, line = self._build_layout(font=font, palette=palette)
        if not line.isValid():
            return
        origin = self._host.input_method_caret_rect(state.source_start).topLeft()
        painter.save()
        try:
            layout.draw(painter, origin)
            if state.cursor_visible:
                cursor_x = _cursor_x(line, state.cursor_utf16)
                painter.setPen(
                    state.cursor_color or palette.color(QPalette.ColorRole.Text)
                )
                painter.drawLine(
                    QPointF(origin.x() + cursor_x, origin.y()),
                    QPointF(origin.x() + cursor_x, origin.y() + line.height()),
                )
        finally:
            painter.restore()

    def cursor_rect(self, *, font: QFont, palette: QPalette) -> QRectF:
        """Return the viewport-local candidate-window rectangle for composition."""

        state = self._preedit
        if state is None:
            return self._host.input_method_caret_rect(self._host.cursor_position)
        _layout, line = self._build_layout(font=font, palette=palette)
        base_rect = self._host.input_method_caret_rect(state.source_start)
        if not line.isValid():
            return base_rect
        cursor_x = _cursor_x(line, state.cursor_utf16)
        return QRectF(
            base_rect.x() + cursor_x,
            base_rect.y(),
            max(1.0, base_rect.width()),
            max(base_rect.height(), line.height()),
        )

    def _commit_event(
        self,
        *,
        source_text: str,
        source_start: int,
        source_end: int,
        event: QInputMethodEvent,
    ) -> tuple[str, int]:
        """Commit selection deletion and relative replacement as one source edit."""

        virtual_source = source_text[:source_start] + source_text[source_end:]
        virtual_coordinates = TextCoordinateMap(virtual_source)
        preedit_start_utf16 = virtual_coordinates.python_to_utf16(source_start)
        replacement_start_utf16 = preedit_start_utf16 + event.replacementStart()
        replacement_end_utf16 = replacement_start_utf16 + event.replacementLength()
        replacement_start = virtual_coordinates.utf16_to_python(
            replacement_start_utf16,
            prefer_after=event.replacementStart() > 0,
        )
        replacement_end = virtual_coordinates.utf16_to_python(
            replacement_end_utf16,
            prefer_after=True,
        )
        replacement_start, replacement_end = sorted(
            (replacement_start, replacement_end)
        )
        commit_text = event.commitString()
        result_text = (
            virtual_source[:replacement_start]
            + commit_text
            + virtual_source[replacement_end:]
        )
        edit_start, edit_end, edit_text = _single_source_edit(source_text, result_text)
        if edit_start != edit_end or edit_text:
            self._committing = True
            try:
                self._host.replace_input_method_range(
                    start=edit_start,
                    end=edit_end,
                    replacement_text=edit_text,
                )
            finally:
                self._committing = False
        next_preedit_start = replacement_start + len(commit_text)
        return result_text, next_preedit_start

    def _build_layout(
        self, *, font: QFont, palette: QPalette
    ) -> tuple[QTextLayout, QTextLine]:
        """Build one short-lived shaped layout for the bounded preedit string."""

        state = self._preedit
        if state is None:
            return QTextLayout(), QTextLine()
        layout = QTextLayout(state.text, font)
        formats = [
            _layout_format_range(
                start=format_range.start,
                length=format_range.length,
                text_format=format_range.text_format,
            )
            for format_range in state.formats
        ]
        if not formats:
            default_format = QTextCharFormat()
            default_format.setForeground(palette.brush(QPalette.ColorRole.Text))
            default_format.setFontUnderline(True)
            formats.append(
                _layout_format_range(
                    start=0,
                    length=TextCoordinateMap(state.text).utf16_length,
                    text_format=default_format,
                )
            )
        layout.setFormats(formats)
        layout.beginLayout()
        line = layout.createLine()
        if line.isValid():
            line.setLineWidth(1_000_000.0)
        layout.endLayout()
        return layout, line


def _single_source_edit(previous: str, current: str) -> tuple[int, int, str]:
    """Return the minimal contiguous edit that transforms previous into current."""

    prefix = 0
    prefix_limit = min(len(previous), len(current))
    while prefix < prefix_limit and previous[prefix] == current[prefix]:
        prefix += 1
    previous_suffix = len(previous)
    current_suffix = len(current)
    while (
        previous_suffix > prefix
        and current_suffix > prefix
        and previous[previous_suffix - 1] == current[current_suffix - 1]
    ):
        previous_suffix -= 1
        current_suffix -= 1
    return prefix, previous_suffix, current[prefix:current_suffix]


def _preedit_cursor(
    event: QInputMethodEvent,
    preedit_text: str,
) -> tuple[int, bool, QColor | None]:
    """Resolve the cursor attribute for one preedit event."""

    default_position = TextCoordinateMap(preedit_text).utf16_length
    for attribute in event.attributes():
        if attribute.type is not QInputMethodEvent.AttributeType.Cursor:
            continue
        color = attribute.value if isinstance(attribute.value, QColor) else None
        return max(0, attribute.start), attribute.length != 0, color
    return default_position, True, None


def _preedit_formats(event: QInputMethodEvent) -> tuple[PromptPreeditFormat, ...]:
    """Copy input-method text-format attributes into immutable paint state."""

    formats: list[PromptPreeditFormat] = []
    for attribute in event.attributes():
        if attribute.type is not QInputMethodEvent.AttributeType.TextFormat:
            continue
        if not isinstance(attribute.value, QTextCharFormat):
            continue
        formats.append(
            PromptPreeditFormat(
                start=max(0, attribute.start),
                length=max(0, attribute.length),
                text_format=QTextCharFormat(attribute.value),
            )
        )
    return tuple(formats)


def _cursor_x(line: QTextLine, utf16_position: int) -> float:
    """Return a shaped line x-coordinate for a clamped UTF-16 position."""

    result = cast(tuple[float, int], line.cursorToX(max(0, utf16_position)))
    return float(result[0])


def _layout_format_range(
    *,
    start: int,
    length: int,
    text_format: QTextCharFormat,
) -> QTextLayout.FormatRange:
    """Build one mutable Qt layout format range with typed assignments."""

    format_range = QTextLayout.FormatRange()
    format_range.start = start
    format_range.length = length
    format_range.format = text_format
    return format_range


__all__ = [
    "PromptInputMethodController",
    "PromptInputMethodHost",
    "PromptPreeditFormat",
    "PromptPreeditState",
]
