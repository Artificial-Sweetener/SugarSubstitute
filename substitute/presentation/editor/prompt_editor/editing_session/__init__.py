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

"""Expose prompt editing-session state and undo primitives."""

from .clipboard_controller import (
    PromptClipboardController,
    PromptClipboardCopyResult,
    PromptClipboardCutResult,
    PromptClipboardPasteResult,
)
from .cursor_adapter import (
    PromptCursorAdapter,
    PromptCursorAdapterHost,
    PromptCursorSelectionAdapter,
)
from .cursor_session import PromptCursorSession
from .cursor_state import PromptCursorState
from .edit_transaction import (
    PromptEditTransaction,
    PromptUndoAvailability,
    PromptUndoAvailabilityChange,
    PromptUndoRestoreResult,
    PromptUndoSnapshot,
)
from .selection_state import PromptSelection
from .session import (
    PromptEditingSession,
    PromptEditingSessionRestoreResult,
    PromptEditingSessionSourceChange,
)
from .source_buffer import PromptSourceBuffer, PromptSourceSnapshot
from .source_edit_commands import (
    PromptSourceEditResult,
    PromptSourceEditOrigin,
    PromptSourceEditSession,
    PromptSourceNormalizer,
    PromptSourceNormalizationResult,
    PromptSourceTextEdit,
    source_text_edit_between,
)
from .undo_stack import PromptUndoStack

__all__ = [
    "PromptCursorState",
    "PromptClipboardController",
    "PromptClipboardCopyResult",
    "PromptClipboardCutResult",
    "PromptClipboardPasteResult",
    "PromptCursorAdapter",
    "PromptCursorAdapterHost",
    "PromptCursorSelectionAdapter",
    "PromptCursorSession",
    "PromptEditTransaction",
    "PromptEditingSession",
    "PromptEditingSessionRestoreResult",
    "PromptEditingSessionSourceChange",
    "PromptSelection",
    "PromptSourceBuffer",
    "PromptSourceEditResult",
    "PromptSourceEditOrigin",
    "PromptSourceEditSession",
    "PromptSourceNormalizer",
    "PromptSourceNormalizationResult",
    "PromptSourceSnapshot",
    "PromptSourceTextEdit",
    "PromptUndoAvailability",
    "PromptUndoAvailabilityChange",
    "PromptUndoRestoreResult",
    "PromptUndoSnapshot",
    "PromptUndoStack",
    "source_text_edit_between",
]
