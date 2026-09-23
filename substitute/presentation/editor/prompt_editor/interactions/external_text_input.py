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

"""Own external plain-text insertion and prompt drag/drop acceptance."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QMimeData, QPoint

from ..mime_data_policy import (
    mime_data_has_prompt_plain_text,
    prompt_plain_text_from_mime_data,
)

_DROP_COMMAND_NAME = "drop_plain_text"
_MIME_COMMAND_NAME = "mime_plain_text"


class PromptExternalTextInsertion(Protocol):
    """Insert accepted external text through the mounted editing boundary."""

    def __call__(
        self,
        text: str,
        *,
        command_name: str,
        viewport_position: QPoint | None,
    ) -> None:
        """Insert text at an optional projection-viewport position."""


class PromptExternalTextEvent(Protocol):
    """Expose the Qt MIME-event operations required by external text input."""

    def mimeData(self) -> QMimeData:  # noqa: N802
        """Return the event MIME payload."""

    def acceptProposedAction(self) -> None:  # noqa: N802
        """Accept the event's proposed action."""

    def ignore(self) -> None:
        """Reject the event."""


class PromptExternalTextInputOwner:
    """Authorize and commit plain-text MIME input for any mounted prompt host."""

    def __init__(self, insertion: PromptExternalTextInsertion) -> None:
        """Retain the host-specific source insertion boundary."""
        self._insertion = insertion

    def can_insert(self, source: QMimeData) -> bool:
        """Return whether one external payload may become prompt source text."""
        return mime_data_has_prompt_plain_text(source)

    def insert(self, source: QMimeData) -> bool:
        """Insert one accepted non-positional MIME payload."""
        text = prompt_plain_text_from_mime_data(source)
        if text is None:
            return False
        self._insertion(
            text,
            command_name=_MIME_COMMAND_NAME,
            viewport_position=None,
        )
        return True

    def accept_or_ignore_drag(self, event: PromptExternalTextEvent) -> bool:
        """Accept a drag exactly when its payload is safe prompt text."""
        if not self.can_insert(event.mimeData()):
            event.ignore()
            return False
        event.acceptProposedAction()
        return True

    def drop(
        self,
        event: PromptExternalTextEvent,
        *,
        viewport_position: QPoint,
    ) -> bool:
        """Insert one accepted drop at its projection-viewport position."""
        text = prompt_plain_text_from_mime_data(event.mimeData())
        if text is None:
            event.ignore()
            return False
        self._insertion(
            text,
            command_name=_DROP_COMMAND_NAME,
            viewport_position=viewport_position,
        )
        event.acceptProposedAction()
        return True


__all__ = [
    "PromptExternalTextEvent",
    "PromptExternalTextInputOwner",
    "PromptExternalTextInsertion",
]
