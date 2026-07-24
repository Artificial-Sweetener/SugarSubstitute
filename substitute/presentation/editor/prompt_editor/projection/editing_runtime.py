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

"""Define construction-time editing collaborators required by projection input."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from ..commands.execution import PromptEditExecution
from ..commands.source_service import PromptSourceCommandService
from ..interactions.clipboard_history_controller import PromptClipboardHistoryActions
from ..interactions.undo_coalescing import PromptUndoCoalescingActions

THost_contra = TypeVar("THost_contra", contravariant=True)
TPayload = TypeVar("TPayload")


@dataclass(frozen=True, slots=True)
class PromptProjectionEditingRuntime(Generic[TPayload]):
    """Carry the focused editing services consumed by projection input."""

    execution: PromptEditExecution[TPayload]
    source_commands: PromptSourceCommandService[TPayload]
    clipboard_history: PromptClipboardHistoryActions
    undo_coalescing: PromptUndoCoalescingActions


class PromptProjectionEditingRuntimeFactory(
    Protocol[THost_contra, TPayload],
):
    """Build projection editing services once the concrete surface exists."""

    def __call__(
        self,
        host: THost_contra,
    ) -> PromptProjectionEditingRuntime[TPayload]:
        """Return fully wired editing services during surface construction."""


__all__ = [
    "PromptProjectionEditingRuntime",
    "PromptProjectionEditingRuntimeFactory",
]
