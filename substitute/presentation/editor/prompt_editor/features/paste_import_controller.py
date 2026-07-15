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

from collections.abc import Callable
from typing import Generic, Protocol, TypeVar

from substitute.application.danbooru import (
    DanbooruPromptImportResult,
    DanbooruUrlImportService,
)

from ..commands import (
    PromptCommandResult,
)
from ..danbooru_paste_import import (
    DanbooruUrlImportDispatcher,
    PromptDanbooruPasteExecutor,
    PromptDanbooruPasteImportHandler,
    PromptDanbooruPasteRequest,
    PromptPreparedDanbooruImportExecutor,
)
from ..editing_session import PromptSourceEditOrigin, PromptSourceNormalizer
from ..editing_session.edit_controller import PromptEditController

TPayload = TypeVar("TPayload")


class PromptDanbooruSourceReplacementExecutor(Protocol[TPayload]):
    """Replace source ranges for Danbooru paste/import scheduling."""

    def replace_source_range(
        self,
        *,
        start: int,
        end: int,
        replacement_text: str,
        origin: PromptSourceEditOrigin,
        command_name: str = "replace_source_range",
        record_undo: bool = True,
    ) -> PromptCommandResult[TPayload]:
        """Replace one source range through the edit-command router."""


class PromptDanbooruPasteImportController(
    Generic[TPayload],
    PromptDanbooruPasteExecutor[TPayload],
):
    """Own Danbooru paste/import scheduling and edit-controller callbacks."""

    def __init__(
        self,
        *,
        edit_controller: PromptEditController[TPayload],
        source_replacement_executor: PromptDanbooruSourceReplacementExecutor[TPayload],
        import_executor: PromptPreparedDanbooruImportExecutor[TPayload],
        normalizer: PromptSourceNormalizer,
        exact_source_enabled: Callable[[], bool],
        dispatcher: DanbooruUrlImportDispatcher,
    ) -> None:
        """Bind Danbooru paste/import behavior to command-backed editors."""

        self._edit_controller = edit_controller
        self._source_replacement_executor = source_replacement_executor
        self._handler = PromptDanbooruPasteImportHandler(
            self,
            import_executor=import_executor,
            normalizer=normalizer,
            exact_source_enabled=exact_source_enabled,
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

        selection = self._edit_controller.session.selection()
        command_result = self._source_replacement_executor.replace_source_range(
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
            pasted_undo_state=self._edit_controller.current_undo_snapshot(),
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
    "PromptDanbooruSourceReplacementExecutor",
]
