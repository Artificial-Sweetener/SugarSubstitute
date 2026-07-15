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

"""Schedule Danbooru URL paste imports outside the projection surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from substitute.application.danbooru import (
    DanbooruPromptImportResult,
    DanbooruUrlImportService,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    log_prompt_async_warning,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceRange,
    PromptPasteImportCommandResult,
    PromptPreparedDanbooruImportRequest,
    normalized_clipboard_paste_text,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceNormalizer,
    PromptUndoSnapshot,
)
from substitute.shared.logging.logger import get_logger, log_debug

TPayload = TypeVar("TPayload")
_LOGGER = get_logger("presentation.editor.prompt_editor.danbooru_paste_import")


class DanbooruUrlImportDispatcher(Protocol):
    """Run Danbooru URL imports away from the GUI thread and report later."""

    def submit(
        self,
        lookup: Callable[[], DanbooruPromptImportResult],
        *,
        completed: Callable[[DanbooruPromptImportResult], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Run one Danbooru import lookup and deliver the result later."""


@dataclass(frozen=True, slots=True)
class PromptDanbooruPasteRequest(Generic[TPayload]):
    """Track one pasted URL slice while background Danbooru import resolves."""

    pasted_text: str
    start: int
    end: int
    pasted_undo_state: PromptUndoSnapshot[TPayload]


class PromptDanbooruPasteExecutor(Protocol[TPayload]):
    """Insert literal pasted URLs through the command/edit-controller boundary."""

    def execute_danbooru_url_paste(
        self,
        text: str,
        *,
        pasted_text: str,
    ) -> PromptDanbooruPasteRequest[TPayload] | None:
        """Insert one pasted URL and return the slice tracked by async import."""


class PromptPreparedDanbooruImportExecutor(Protocol[TPayload]):
    """Execute prepared Danbooru import commands outside the paste scheduler."""

    def execute_prepared_danbooru_import(
        self,
        request: PromptPreparedDanbooruImportRequest[TPayload],
    ) -> PromptPasteImportCommandResult[TPayload]:
        """Execute a prepared Danbooru import command."""


class PromptDanbooruPasteImportHandler(Generic[TPayload]):
    """Own Danbooru URL import readiness, scheduling, and result publication."""

    def __init__(
        self,
        paste_executor: PromptDanbooruPasteExecutor[TPayload],
        *,
        import_executor: PromptPreparedDanbooruImportExecutor[TPayload],
        normalizer: PromptSourceNormalizer,
        exact_source_enabled: Callable[[], bool],
        dispatcher: DanbooruUrlImportDispatcher,
    ) -> None:
        """Bind paste/import scheduling to command-backed host operations."""

        self._paste_executor = paste_executor
        self._import_executor = import_executor
        self._normalizer = normalizer
        self._exact_source_enabled = exact_source_enabled
        self._dispatcher = dispatcher
        self._service: DanbooruUrlImportService | None = None
        self._enabled = False

    def configure(
        self,
        service: DanbooruUrlImportService | None,
        *,
        enabled: bool,
        dispatcher: DanbooruUrlImportDispatcher | None = None,
    ) -> None:
        """Configure Danbooru URL-import behavior for prompt paste actions."""

        self._service = service
        self._enabled = enabled
        if dispatcher is not None:
            self._dispatcher = dispatcher

    def try_schedule_url_import(self, text: str) -> bool:
        """Paste supported Danbooru URLs immediately and replace them later."""

        service = self._service
        if not self._enabled or service is None or not text.strip():
            return False
        classification = service.classify_url(text)
        if classification is None:
            return False

        pasted_text = self.normalized_paste_text(text)
        request = self._paste_executor.execute_danbooru_url_paste(
            text,
            pasted_text=pasted_text,
        )
        if request is None:
            return False
        log_debug(
            _LOGGER,
            "Prompt paste scheduled Danbooru URL import.",
            url_kind=classification.kind.value,
            lookup_value=classification.lookup_value,
            start=request.start,
            end=request.end,
        )
        self._dispatcher.submit(
            lambda: service.import_prompt_from_url(text),
            completed=lambda result: self.apply_import_result(request, result),
            failed=lambda error: self.handle_import_failure(request, error),
        )
        return True

    def apply_import_result(
        self,
        request: PromptDanbooruPasteRequest[TPayload],
        result: DanbooruPromptImportResult,
    ) -> None:
        """Replace the pasted URL slice only when it still matches the paste."""

        if not result.succeeded or result.imported_prompt is None:
            log_debug(
                _LOGGER,
                "Prompt paste kept literal Danbooru URL after lookup failure.",
                failure_reason=(
                    "" if result.failure_reason is None else result.failure_reason.value
                ),
                start=request.start,
                end=request.end,
            )
            return

        command_result = self._import_executor.execute_prepared_danbooru_import(
            PromptPreparedDanbooruImportRequest(
                source_range=PromptCommandSourceRange(request.start, request.end),
                expected_pasted_text=request.pasted_text,
                import_text=result.imported_prompt.display_text,
                pasted_undo_snapshot=request.pasted_undo_state,
            )
        )
        if command_result.status != "applied":
            if command_result.reason == "pasted_text_changed":
                log_debug(
                    _LOGGER,
                    "Prompt paste skipped Danbooru replacement after later edits.",
                    start=request.start,
                    end=request.end,
                )
            return

        if command_result.source_change is not None:
            log_debug(
                _LOGGER,
                "Prompt paste replaced Danbooru URL with imported tags.",
                post_id=result.imported_prompt.source_post_id,
                included_tag_count=len(result.imported_prompt.included_tags),
            )

    def handle_import_failure(
        self,
        request: PromptDanbooruPasteRequest[TPayload],
        error: BaseException,
    ) -> None:
        """Leave the literal pasted URL in place when background import errors occur."""

        log_prompt_async_warning(
            _LOGGER,
            "Prompt paste Danbooru import failed unexpectedly.",
            error=error,
            operation="danbooru_url_import",
            reason="paste_import",
            source_length=len(request.pasted_text),
        )

    def normalized_paste_text(self, text: str) -> str:
        """Return the literal text form that a normal paste inserts for matching."""

        return normalized_clipboard_paste_text(
            text,
            normalizer=self._normalizer,
            exact_source=self._exact_source_enabled(),
        )


__all__ = [
    "DanbooruUrlImportDispatcher",
    "PromptDanbooruPasteImportHandler",
    "PromptDanbooruPasteExecutor",
    "PromptDanbooruPasteRequest",
    "PromptPreparedDanbooruImportExecutor",
]
