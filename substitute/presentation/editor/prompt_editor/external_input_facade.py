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

"""Adapt host MIME and drop input to mounted prompt source editing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QMimeData, QPoint
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QWidget

from .interactions import PromptExternalTextInputOwner
from .interactions.clipboard_paste_completion import (
    PromptClipboardPasteCompletionOwner,
)
from .projection.surface import PromptProjectionSurface


@dataclass(frozen=True, slots=True)
class PromptEditorExternalInputBindings:
    """Declare mounted cursor, source, and drop-coordinate operations."""

    set_cursor_at_viewport_position: Callable[[QPoint], None]
    insert_external_text: Callable[[str, str], None]
    complete_paste: Callable[[str], None]
    viewport_position_for_drop: Callable[[QDropEvent], QPoint]


class PromptEditorExternalInputFacade:
    """Expose QFluent MIME compatibility through one insertion transaction."""

    def __init__(self, bindings: PromptEditorExternalInputBindings) -> None:
        """Bind host adaptation to the shared external-text policy owner."""

        self._bindings = bindings
        self._external_text = PromptExternalTextInputOwner(self._insert_external_text)

    def can_insert(self, source: QMimeData) -> bool:
        """Return whether external MIME data may become prompt source text."""

        return self._external_text.can_insert(source)

    def insert(self, source: QMimeData) -> None:
        """Insert prompt-safe non-positional MIME text."""

        self._external_text.insert(source)

    def accept_or_ignore_drag(
        self,
        event: QDragEnterEvent | QDragMoveEvent,
    ) -> None:
        """Accept only prompt-safe plain-text drag payloads."""

        self._external_text.accept_or_ignore_drag(event)

    def drop(self, event: QDropEvent) -> None:
        """Insert prompt-safe dropped text at its projection viewport position."""

        self._external_text.drop(
            event,
            viewport_position=self._bindings.viewport_position_for_drop(event),
        )

    def _insert_external_text(
        self,
        text: str,
        *,
        command_name: str,
        viewport_position: QPoint | None,
    ) -> None:
        """Commit accepted text and publish completion as one ordered operation."""

        if viewport_position is not None:
            self._bindings.set_cursor_at_viewport_position(viewport_position)
        self._bindings.insert_external_text(text, command_name)
        self._bindings.complete_paste(command_name)


def build_prompt_editor_external_input_facade(
    host: QWidget,
    surface: PromptProjectionSurface,
    paste_completion: PromptClipboardPasteCompletionOwner,
) -> PromptEditorExternalInputFacade:
    """Bind one QFluent host and projection surface to external input."""

    return PromptEditorExternalInputFacade(
        PromptEditorExternalInputBindings(
            set_cursor_at_viewport_position=(
                lambda position: surface.setTextCursor(
                    surface.cursorForPosition(position)
                )
            ),
            insert_external_text=(
                lambda text, command_name: surface.insert_external_text(
                    text,
                    command_name=command_name,
                )
            ),
            complete_paste=paste_completion.complete,
            viewport_position_for_drop=(
                lambda event: surface.viewport().mapFrom(
                    host,
                    event.position().toPoint(),
                )
            ),
        )
    )


__all__ = [
    "PromptEditorExternalInputBindings",
    "PromptEditorExternalInputFacade",
    "build_prompt_editor_external_input_facade",
]
