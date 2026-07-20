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

"""Own transient input-method composition for the painted cube alias editor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtGui import QInputMethodEvent

from substitute.presentation.text_coordinates import TextCoordinateMap


class CubeAliasInputMethodHost(Protocol):
    """Expose committed alias state consumed by input-method composition."""

    def text(self) -> str:
        """Return committed alias text."""

    def cursorIndex(self) -> int:  # noqa: N802
        """Return the committed Python cursor index."""

    def selectionRange(self) -> tuple[int, int] | None:  # noqa: N802
        """Return the committed Python selection range."""

    def replace_input_method_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
    ) -> None:
        """Replace one committed alias range without changing presentation policy."""


@dataclass(frozen=True, slots=True)
class CubeAliasPreeditState:
    """Describe one transient composition snapshot outside committed alias text."""

    source_start: int
    source_end: int
    text: str
    cursor_utf16: int
    cursor_visible: bool


class CubeAliasInputMethodController:
    """Apply Qt IME commits while keeping preedit text out of alias state."""

    def __init__(self, host: CubeAliasInputMethodHost) -> None:
        """Store the painted editor that owns committed alias mutations."""

        self._host = host
        self._preedit: CubeAliasPreeditState | None = None

    @property
    def preedit_state(self) -> CubeAliasPreeditState | None:
        """Return the active transient composition snapshot when present."""

        return self._preedit

    def handle_event(self, event: QInputMethodEvent) -> None:
        """Apply one input-method event as at most one committed alias mutation."""

        source_text = self._host.text()
        if self._preedit is None:
            selection = self._host.selectionRange()
            if selection is None:
                source_start = self._host.cursorIndex()
                source_end = source_start
            else:
                source_start, source_end = selection
        else:
            source_start = self._preedit.source_start
            source_end = self._preedit.source_end

        should_commit = (
            bool(event.commitString())
            or event.replacementStart() != 0
            or event.replacementLength() != 0
        )
        if should_commit:
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
        cursor_utf16, cursor_visible = _preedit_cursor(event, preedit_text)
        self._preedit = CubeAliasPreeditState(
            source_start=min(source_start, len(source_text)),
            source_end=min(source_end, len(source_text)),
            text=preedit_text,
            cursor_utf16=cursor_utf16,
            cursor_visible=cursor_visible,
        )

    def cancel(self) -> None:
        """Discard preedit state without changing the committed alias."""

        self._preedit = None

    def display_text(self) -> str:
        """Return committed text with transient preedit projected in place."""

        state = self._preedit
        source_text = self._host.text()
        if state is None:
            return source_text
        return (
            source_text[: state.source_start]
            + state.text
            + source_text[state.source_end :]
        )

    def _commit_event(
        self,
        *,
        source_text: str,
        source_start: int,
        source_end: int,
        event: QInputMethodEvent,
    ) -> tuple[str, int]:
        """Resolve selection and relative QString replacement into one alias edit."""

        virtual_source = source_text[:source_start] + source_text[source_end:]
        coordinates = TextCoordinateMap(virtual_source)
        preedit_start_utf16 = coordinates.python_to_utf16(source_start)
        replacement_start_utf16 = preedit_start_utf16 + event.replacementStart()
        replacement_end_utf16 = replacement_start_utf16 + event.replacementLength()
        replacement_start = coordinates.utf16_to_python(
            replacement_start_utf16,
            prefer_after=event.replacementStart() > 0,
        )
        replacement_end = coordinates.utf16_to_python(
            replacement_end_utf16,
            prefer_after=True,
        )
        replacement_start, replacement_end = sorted(
            (replacement_start, replacement_end)
        )
        result_text = (
            virtual_source[:replacement_start]
            + event.commitString()
            + virtual_source[replacement_end:]
        )
        edit_start, edit_end, edit_text = _single_source_edit(source_text, result_text)
        if edit_start != edit_end or edit_text:
            self._host.replace_input_method_range(
                start=edit_start,
                end=edit_end,
                replacement_text=edit_text,
            )
        return result_text, replacement_start + len(event.commitString())


def _preedit_cursor(
    event: QInputMethodEvent,
    preedit_text: str,
) -> tuple[int, bool]:
    """Resolve the Qt cursor attribute for the current preedit string."""

    default_position = TextCoordinateMap(preedit_text).utf16_length
    for attribute in event.attributes():
        if attribute.type is QInputMethodEvent.AttributeType.Cursor:
            return max(0, attribute.start), attribute.length != 0
    return default_position, True


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


__all__ = [
    "CubeAliasInputMethodController",
    "CubeAliasInputMethodHost",
    "CubeAliasPreeditState",
]
