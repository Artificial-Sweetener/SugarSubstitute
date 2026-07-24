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

"""Coordinate Danbooru paste/import source mutations outside projection."""

from __future__ import annotations

from typing import Generic, TypeVar

from substitute.application.danbooru import (
    DanbooruPromptImportResult,
    DanbooruUrlImportService,
)

from ..commands.execution import PromptEditExecution
from ..commands.paste_import_commands import PromptPasteImportCommandService
from ..commands.source_service import PromptSourceCommandService
from ..core.editing.source_commands import PromptSourceEditOrigin
from ..danbooru_paste_import import (
    DanbooruUrlImportDispatcher,
    PromptDanbooruPasteExecutor,
    PromptDanbooruPasteImportHandler,
    PromptDanbooruPasteRequest,
)

TPayload = TypeVar("TPayload")


class PromptDanbooruPasteImportController(
    Generic[TPayload],
    PromptDanbooruPasteExecutor[TPayload],
):
    """Own Danbooru paste/import scheduling around focused editing services."""

    def __init__(
        self,
        *,
        edit_execution: PromptEditExecution[TPayload],
        source_commands: PromptSourceCommandService[TPayload],
        import_commands: PromptPasteImportCommandService[TPayload],
        dispatcher: DanbooruUrlImportDispatcher,
    ) -> None:
        """Bind Danbooru paste/import behavior to command-backed editors."""

        self._edit_execution = edit_execution
        self._source_commands = source_commands
        self._handler = PromptDanbooruPasteImportHandler(
            self,
            import_executor=import_commands,
            normalize_paste_text=source_commands.normalized_paste_text,
            dispatcher=dispatcher,
        )

    def configure_danbooru_url_import(
        self,
        service: DanbooruUrlImportService | None,
        *,
        enabled: bool,
        dispatcher: DanbooruUrlImportDispatcher | None = None,
    ) -> None:
        """Configure Danbooru URL-import behavior for prompt paste actions."""

        self._handler.configure(service, enabled=enabled, dispatcher=dispatcher)

    def try_schedule_clipboard_danbooru_paste(self, text: str) -> bool:
        """Return whether the pasted text was scheduled as a Danbooru import."""

        return self._handler.try_schedule_url_import(text)

    def execute_danbooru_url_paste(
        self,
        text: str,
        *,
        pasted_text: str,
    ) -> PromptDanbooruPasteRequest[TPayload] | None:
        """Insert a literal Danbooru URL and return its async replacement request."""

        selection = self._edit_execution.session.selection()
        command_result = self._source_commands.replace_source_range(
            start=selection.start,
            end=selection.end,
            replacement_text=text,
            origin=PromptSourceEditOrigin.PASTE,
            command_name="danbooru_url_paste",
        )
        cursor_state = command_result.cursor_state
        if cursor_state is None:
            return None
        end = cursor_state.cursor_position
        return PromptDanbooruPasteRequest(
            pasted_text=pasted_text,
            start=end - len(pasted_text),
            end=end,
            pasted_undo_state=self._edit_execution.current_undo_snapshot(),
        )

    def apply_import_result(
        self,
        request: PromptDanbooruPasteRequest[TPayload],
        result: DanbooruPromptImportResult,
    ) -> None:
        """Apply one completed Danbooru URL import result."""

        self._handler.apply_import_result(request, result)

    def handle_import_failure(
        self,
        request: PromptDanbooruPasteRequest[TPayload],
        error: BaseException,
    ) -> None:
        """Log one failed Danbooru URL import and keep the literal paste."""

        self._handler.handle_import_failure(request, error)

    def normalized_paste_text(self, text: str) -> str:
        """Return the literal text form that a normal paste inserts for matching."""

        return self._handler.normalized_paste_text(text)


__all__ = [
    "PromptDanbooruPasteImportController",
]
