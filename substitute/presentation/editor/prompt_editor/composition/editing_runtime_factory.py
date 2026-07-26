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

"""Construct the prompt surface's complete editing runtime in one phase."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtWidgets import QApplication

from substitute.application.prompt_editor.editing.structured_text import (
    PromptStructuredTextMutationService,
)

from ..commands.execution import PromptEditExecution
from ..commands.paste_import_commands import PromptPasteImportCommandService
from ..commands.source_service import PromptSourceCommandService
from ..core.editing.session import PromptEditingSession
from ..core.editing.source_commands import PromptSourceNormalizer
from ..danbooru_paste_import import DanbooruUrlImportDispatcher
from ..features.paste_import_controller import PromptDanbooruPasteImportController
from ..interactions.clipboard_history_controller import (
    PromptClipboardHistoryController,
)
from ..interactions.undo_coalescing import (
    DELETE_UNDO_COALESCE_IDLE_MS,
    TYPING_UNDO_COALESCE_IDLE_MS,
    PromptUndoCoalescingController,
)
from ..interactions.undo_coalescing_timer import PromptQtUndoCoalescingTimer
from ..projection.editing_runtime import (
    PromptProjectionEditingRuntime,
    PromptProjectionEditingRuntimeFactory,
)
from ..projection.surface import PromptProjectionSurface
from ..projection.undo_payload import PromptProjectionUndoPayload


class QtPromptTextClipboard:
    """Adapt the application clipboard to the prompt clipboard port."""

    def text(self) -> str:
        """Return current system clipboard text."""

        return QApplication.clipboard().text()

    def set_text(self, text: str) -> None:
        """Replace current system clipboard text."""

        QApplication.clipboard().setText(text)


@dataclass(slots=True)
class PromptProjectionEditingRuntimeBuilder(
    PromptProjectionEditingRuntimeFactory[
        PromptProjectionSurface,
        PromptProjectionUndoPayload,
    ]
):
    """Build all editing services against one newly constructed surface."""

    session: PromptEditingSession[PromptProjectionUndoPayload]
    normalizer: PromptSourceNormalizer
    structured_text_mutations: PromptStructuredTextMutationService
    danbooru_dispatcher: DanbooruUrlImportDispatcher
    paste_completed: Callable[[str], None]
    _danbooru_controller: (
        PromptDanbooruPasteImportController[PromptProjectionUndoPayload] | None
    ) = field(default=None, init=False)

    def __call__(
        self,
        surface: PromptProjectionSurface,
    ) -> PromptProjectionEditingRuntime[PromptProjectionUndoPayload]:
        """Create the runtime once, after the surface can serve as its sinks."""

        if self._danbooru_controller is not None:
            raise RuntimeError("Prompt editing runtime was already constructed.")
        execution = PromptEditExecution[PromptProjectionUndoPayload](
            session=self.session,
            undo_payload_provider=surface,
            availability_signal_sink=surface,
            commit_sink=surface,
        )
        source_commands = PromptSourceCommandService(
            execution=execution,
            normalizer=self.normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
        )
        undo_coalescing = PromptUndoCoalescingController(
            edit_execution=execution,
            typing_timer=PromptQtUndoCoalescingTimer(
                parent=surface,
                interval_ms=TYPING_UNDO_COALESCE_IDLE_MS,
            ),
            delete_timer=PromptQtUndoCoalescingTimer(
                parent=surface,
                interval_ms=DELETE_UNDO_COALESCE_IDLE_MS,
            ),
            cursor_position=lambda: surface.cursor_position,
            selection_empty=lambda: not surface.textCursor().hasSelection(),
        )
        execution.set_pending_key_flusher(undo_coalescing)
        paste_import_commands = PromptPasteImportCommandService(
            execution=execution,
            normalizer=self.normalizer,
            exact_source_enabled=surface.exact_source_editing_enabled,
            structured_text_mutations=self.structured_text_mutations,
        )
        danbooru_controller = PromptDanbooruPasteImportController(
            edit_execution=execution,
            source_commands=source_commands,
            import_commands=paste_import_commands,
            dispatcher=self.danbooru_dispatcher,
        )
        clipboard_history = PromptClipboardHistoryController(
            edit_execution=execution,
            clipboard=QtPromptTextClipboard(),
            cursor_sink=surface,
            source_commands=source_commands,
            danbooru_paste_scheduler=danbooru_controller,
            editing_enabled=surface.editing_enabled,
            paste_completed=self.paste_completed,
        )
        self._danbooru_controller = danbooru_controller
        return PromptProjectionEditingRuntime(
            execution=execution,
            source_commands=source_commands,
            clipboard_history=clipboard_history,
            undo_coalescing=undo_coalescing,
        )

    @property
    def danbooru_controller(
        self,
    ) -> PromptDanbooruPasteImportController[PromptProjectionUndoPayload]:
        """Return the controller created during surface construction."""

        controller = self._danbooru_controller
        if controller is None:
            raise RuntimeError("Prompt editing runtime has not been constructed.")
        return controller


__all__ = [
    "PromptProjectionEditingRuntimeBuilder",
    "QtPromptTextClipboard",
]
