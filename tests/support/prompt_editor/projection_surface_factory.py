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

"""Construct directly tested prompt projection surfaces and editing owners."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.editing.source_normalization import (
    PromptSourceNormalizationService,
)
from substitute.presentation.editor.prompt_editor.commands.execution import (
    PromptEditExecution,
)
from substitute.presentation.editor.prompt_editor.commands.source_service import (
    PromptSourceCommandService,
)
from substitute.presentation.editor.prompt_editor.core.editing.cursor_state import (
    PromptCursorState,
)
from substitute.presentation.editor.prompt_editor.core.editing.session import (
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.interactions.text_mutation_controller import (
    PromptProjectionTextMutationController,
)
from substitute.presentation.editor.prompt_editor.interactions.undo_coalescing import (
    PromptUndoCoalescingController,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.projection.editing_runtime import (
    PromptProjectionEditingRuntime,
    PromptProjectionEditingRuntimeFactory,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.projection.undo_payload import (
    PromptProjectionUndoPayload,
)


class ManualUndoCoalescingTimer:
    """Provide deterministic timer hooks for directly composed surface tests."""

    def __init__(self) -> None:
        """Create an idle manual timer."""

        self._handler: Callable[[], None] | None = None

    def set_timeout_handler(self, handler: Callable[[], None]) -> None:
        """Store the callback that a test may trigger manually."""

        self._handler = handler

    def start(self) -> None:
        """Record timer start without scheduling real time."""

    def stop(self) -> None:
        """Record timer stop without scheduling real time."""


class NoopClipboardHistoryActions:
    """Satisfy clipboard shortcuts for directly composed surfaces."""

    def copy(self) -> None:
        """Ignore copy in bare-surface tests."""

    def cut(self) -> None:
        """Ignore cut in bare-surface tests."""

    def paste(self) -> None:
        """Ignore paste in bare-surface tests."""

    def select_all(self) -> None:
        """Ignore select-all in bare-surface tests."""

    def undo(self) -> None:
        """Ignore undo in bare-surface tests."""

    def redo(self) -> None:
        """Ignore redo in bare-surface tests."""


class TestProjectionEditingRuntimeFactory(
    PromptProjectionEditingRuntimeFactory[
        PromptProjectionSurface,
        PromptProjectionUndoPayload,
    ]
):
    """Build focused editing services for directly constructed surfaces."""

    def __init__(
        self,
        session: PromptEditingSession[PromptProjectionUndoPayload],
    ) -> None:
        """Store the session used by the surface under construction."""

        self._session = session

    def __call__(
        self,
        surface: PromptProjectionSurface,
    ) -> PromptProjectionEditingRuntime[PromptProjectionUndoPayload]:
        """Return a deterministic runtime without external integrations."""

        execution = PromptEditExecution(
            session=self._session,
            undo_payload_provider=surface,
            availability_signal_sink=surface,
            commit_sink=surface,
        )
        source_commands = PromptSourceCommandService(
            execution=execution,
            normalizer=PromptSourceNormalizationService(),
            exact_source_enabled=surface.exact_source_editing_enabled,
        )
        text_mutations = PromptProjectionTextMutationController(
            context_provider=surface,
            source_commands=source_commands,
        )
        coalescing = PromptUndoCoalescingController(
            edit_execution=execution,
            typing_timer=ManualUndoCoalescingTimer(),
            delete_timer=ManualUndoCoalescingTimer(),
            cursor_position=lambda: surface.cursor_position,
            selection_empty=lambda: not surface.textCursor().hasSelection(),
        )
        execution.set_pending_key_flusher(coalescing)
        return PromptProjectionEditingRuntime(
            execution=execution,
            source_commands=source_commands,
            text_mutations=text_mutations,
            clipboard_history=NoopClipboardHistoryActions(),
            undo_coalescing=coalescing,
        )


def new_projection_surface(
    parent: QWidget | None = None,
    *,
    lora_thumbnail_cache: PromptLoraThumbnailCache | None = None,
) -> PromptProjectionSurface:
    """Create a surface with composition-owned mutation collaborators."""

    session = PromptEditingSession[PromptProjectionUndoPayload](
        source_text="",
        source_revision=0,
        cursor_state=PromptCursorState(cursor_position=0, anchor_position=0),
        max_undo_states=100,
        max_redo_states=100,
    )
    return PromptProjectionSurface(
        parent,
        editing_session=session,
        editing_runtime_factory=TestProjectionEditingRuntimeFactory(session),
        lora_thumbnail_cache=lora_thumbnail_cache,
    )


def surface_source_commands(
    surface: PromptProjectionSurface,
) -> PromptSourceCommandService[PromptProjectionUndoPayload]:
    """Return the source command owner composed with one surface."""

    return surface.source_commands


def surface_edit_execution(
    surface: PromptProjectionSurface,
) -> PromptEditExecution[PromptProjectionUndoPayload]:
    """Return the editing execution owner composed with one surface."""

    return surface.edit_execution


__all__ = [
    "ManualUndoCoalescingTimer",
    "NoopClipboardHistoryActions",
    "TestProjectionEditingRuntimeFactory",
    "new_projection_surface",
    "surface_edit_execution",
    "surface_source_commands",
]
