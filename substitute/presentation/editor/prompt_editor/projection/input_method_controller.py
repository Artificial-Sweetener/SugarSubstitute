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

from typing import Generic, Protocol, TypeVar

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QInputMethodEvent,
    QPalette,
    QTextCharFormat,
)

from substitute.presentation.text_coordinates import TextCoordinateMap

from ..commands.source_service import PromptSourceCommandService
from ..core.editing.ime import PromptImePreedit, PromptImeSession
from ..core.editing.source_commands import PromptSourceEditOrigin
from .input_method_layer_preparer import PromptInputMethodRenderLayerPreparer
from .input_method_render_state import (
    EMPTY_INPUT_METHOD_RENDER_LAYER,
    PromptInputMethodRenderLayer,
    PromptPreeditFormat,
)

TPayload = TypeVar("TPayload")


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

    def font(self) -> QFont:
        """Return the current presentation font."""

    def palette(self) -> QPalette:
        """Return the current presentation palette."""

    def input_method_caret_rect(self, source_position: int) -> QRectF:
        """Return a viewport-local caret rectangle for a source position."""


class PromptInputMethodController(Generic[TPayload]):
    """Translate Qt input-method events into one source mutation per commit."""

    def __init__(
        self,
        host: PromptInputMethodHost,
        *,
        source_commands: PromptSourceCommandService[TPayload],
    ) -> None:
        """Store the host while keeping preedit state transient and bounded."""

        self._host = host
        self._source_commands = source_commands
        self._ime_session = PromptImeSession()
        self._cursor_color: QColor | None = None
        self._formats: tuple[PromptPreeditFormat, ...] = ()
        self._layer_preparer = PromptInputMethodRenderLayerPreparer()
        self._render_layer = EMPTY_INPUT_METHOD_RENDER_LAYER

    @property
    def preedit_state(self) -> PromptImePreedit | None:
        """Return the current immutable preedit snapshot when composing."""

        return self._ime_session.preedit

    @property
    def is_composing(self) -> bool:
        """Return whether a non-empty preedit string is active."""

        return self._ime_session.is_composing

    @property
    def render_layer(self) -> PromptInputMethodRenderLayer:
        """Return the currently published shaped preedit layer."""

        return self._render_layer

    def handle_event(self, event: QInputMethodEvent) -> None:
        """Apply one Qt composition event without storing preedit in source text."""

        source_text = self._host.toPlainText()
        preedit = self._ime_session.preedit
        if preedit is None:
            source_start = min(self._host.cursor_position, self._host.anchor_position)
            source_end = max(self._host.cursor_position, self._host.anchor_position)
        else:
            source_start = preedit.source_start
            source_end = preedit.source_end

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
            self._clear_preedit()
            return
        if not self._host.editing_enabled():
            self._clear_preedit()
            return
        cursor_utf16, cursor_visible, cursor_color = _preedit_cursor(
            event, preedit_text
        )
        self._ime_session.set_preedit(
            PromptImePreedit(
                source_start=min(source_start, len(source_text)),
                source_end=min(source_end, len(source_text)),
                text=preedit_text,
                cursor_utf16=cursor_utf16,
                cursor_visible=cursor_visible,
            )
        )
        self._cursor_color = cursor_color
        self._formats = _preedit_formats(event)
        self.refresh_render_layer()

    def cancel(self) -> None:
        """Discard transient composition without mutating prompt source text."""

        self._clear_preedit()

    def source_changed(self) -> None:
        """Cancel composition when an unrelated source owner replaces the document."""

        self._ime_session.source_changed()
        if not self._ime_session.is_composing:
            self._clear_preedit_paint_state()
            self.refresh_render_layer()

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

    def refresh_render_layer(
        self,
        *,
        font: QFont | None = None,
        palette: QPalette | None = None,
    ) -> bool:
        """Publish preedit glyph and cursor geometry for current presentation state."""

        state = self._ime_session.preedit
        if state is None:
            if self._render_layer is EMPTY_INPUT_METHOD_RENDER_LAYER:
                return False
            self._render_layer = EMPTY_INPUT_METHOD_RENDER_LAYER
            return True
        resolved_font = self._host.font() if font is None else font
        resolved_palette = self._host.palette() if palette is None else palette
        next_layer = self._layer_preparer.prepare(
            state,
            formats=self._formats,
            cursor_color=self._cursor_color,
            font=resolved_font,
            palette=resolved_palette,
            base_caret_rect=self._host.input_method_caret_rect(state.source_start),
            previous=self._render_layer,
        )
        if next_layer is self._render_layer:
            return False
        self._render_layer = next_layer
        return True

    def cursor_rect(self, *, font: QFont, palette: QPalette) -> QRectF:
        """Return the viewport-local candidate-window rectangle for composition."""

        state = self._ime_session.preedit
        if state is None:
            return self._host.input_method_caret_rect(self._host.cursor_position)
        self.refresh_render_layer(font=font, palette=palette)
        candidate_rect = self._render_layer.candidate_rect
        if candidate_rect is None:
            return self._host.input_method_caret_rect(state.source_start)
        return QRectF(*candidate_rect)

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
            self._ime_session.begin_commit()
            try:
                self._source_commands.replace_source_range(
                    start=edit_start,
                    end=edit_end,
                    replacement_text=edit_text,
                    origin=PromptSourceEditOrigin.TYPED,
                    command_name="input_method_commit",
                    record_undo=True,
                )
            finally:
                self._ime_session.end_commit()
        next_preedit_start = replacement_start + len(commit_text)
        return result_text, next_preedit_start

    def _clear_preedit(self) -> None:
        """Clear core composition and presentation-only paint attributes."""

        self._ime_session.cancel()
        self._clear_preedit_paint_state()
        self.refresh_render_layer()

    def _clear_preedit_paint_state(self) -> None:
        """Clear Qt paint values associated with inactive composition."""

        self._cursor_color = None
        self._formats = ()


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


__all__ = [
    "PromptInputMethodController",
    "PromptInputMethodHost",
]
