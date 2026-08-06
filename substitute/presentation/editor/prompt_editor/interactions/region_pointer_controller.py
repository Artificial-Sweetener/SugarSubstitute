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

"""Own regional separator hit testing, naming, and transient hover intent."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QInputDialog, QWidget
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionSeparatorView,
)
from substitute.application.prompt_editor.editing.region_naming import (
    PromptRegionNamingService,
)
from substitute.presentation.editor.prompt_editor.core.editing.source_commands import (
    PromptSourceEditOrigin,
)
from substitute.presentation.editor.prompt_editor.projection.prepared_frame import (
    PromptProjectionPreparedFrame,
)


class PromptRegionSourceCommands(Protocol):
    """Expose the source mutation needed by regional name authoring."""

    def replace_source_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str = "replace_source_range",
        record_undo: bool = True,
        finish_pending_key_edits: bool = False,
    ) -> object:
        """Commit one source-backed replacement."""


PromptRegionNamePrompt = Callable[[QWidget, str], tuple[str, bool]]
PromptRegionHoverSink = Callable[[int | None], None]


class PromptRegionPointerController:
    """Translate separator pointer gestures into source-backed region intent."""

    def __init__(
        self,
        *,
        parent: QWidget,
        document_view: Callable[[], PromptDocumentView],
        source_commands: PromptRegionSourceCommands,
        scroll_offset: Callable[[], float],
        cursor_position: Callable[[], int],
        name_prompt: PromptRegionNamePrompt | None = None,
        hover_sink: PromptRegionHoverSink | None = None,
    ) -> None:
        """Store focused owners for hit testing, naming, and hover publication."""

        self._parent = parent
        self._document_view = document_view
        self._source_commands = source_commands
        self._scroll_offset = scroll_offset
        self._cursor_position = cursor_position
        self._name_prompt = name_prompt or _prompt_for_region_name
        self._hover_sink = hover_sink
        self._naming = PromptRegionNamingService()
        self._hovered_region_index: int | None = None

    def handle_double_click(
        self,
        position: QPointF,
        frame: PromptProjectionPreparedFrame,
    ) -> bool:
        """Rename the separator row beneath one double click."""

        hit = self._separator_hit(position, frame)
        if hit is None:
            return False
        _index, separator = hit
        return self._rename(separator)

    def handle_keyboard_rename(self) -> bool:
        """Rename the separator adjacent to the current source caret."""

        cursor_position = self._cursor_position()
        for separator in self._document_view().region_structure.separators:
            if separator.token_start <= cursor_position <= separator.token_end:
                return self._rename(separator)
        return False

    def _rename(self, separator: PromptRegionSeparatorView) -> bool:
        """Prompt for and commit one separator name through the source owner."""

        authored_name, accepted = self._name_prompt(
            self._parent,
            "" if separator.name is None else separator.name,
        )
        if not accepted:
            return True
        try:
            replacement = self._naming.replacement_for(separator, authored_name)
        except ValueError:
            return True
        self._source_commands.replace_source_range(
            start=replacement.source_start,
            end=replacement.source_end,
            replacement_text=replacement.replacement_text,
            origin=PromptSourceEditOrigin.PROGRAMMATIC,
            command_name="rename_prompt_region",
            finish_pending_key_edits=True,
        )
        return True

    def handle_hover(
        self,
        position: QPointF | None,
        frame: PromptProjectionPreparedFrame,
    ) -> None:
        """Publish a changed separator hover without changing selection."""

        hit = None if position is None else self._separator_hit(position, frame)
        next_index = None if hit is None else hit[0]
        if next_index == self._hovered_region_index:
            return
        self._hovered_region_index = next_index
        if self._hover_sink is not None:
            self._hover_sink(next_index)

    def _separator_hit(
        self,
        position: QPointF,
        frame: PromptProjectionPreparedFrame,
    ) -> tuple[int, PromptRegionSeparatorView] | None:
        """Return the regional index and separator owning one structural row."""

        source_y = position.y() + self._scroll_offset()
        document = self._document_view()
        lines = frame.output.snapshot.lines
        for index, separator in enumerate(document.region_structure.separators):
            for line in lines:
                if line.source_start > separator.line_start:
                    break
                if (
                    line.source_start == separator.line_start
                    and line.source_end == separator.line_end
                    and line.top <= source_y <= line.top + line.height
                ):
                    return index, separator
        return None


def _prompt_for_region_name(parent: QWidget, current_name: str) -> tuple[str, bool]:
    """Ask for an authored name using existing localized application text."""

    return QInputDialog.getText(
        parent,
        app_text("Rename"),
        app_text("Name"),
        text=current_name,
    )


__all__ = ["PromptRegionPointerController"]
