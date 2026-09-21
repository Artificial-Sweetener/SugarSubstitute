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

"""Compose source-input controllers for the prompt projection surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from PySide6.QtCore import QObject, QRectF, Qt
from PySide6.QtWidgets import QWidget

from ..commands.execution import PromptEditExecution
from ..commands.source_service import PromptSourceCommandService
from ..core.editing.session import PromptEditingSession
from ..interactions import (
    PromptExternalTextInputOwner,
    PromptSurfaceKeyHandler,
    PromptSurfaceKeyHost,
    PromptSurfaceMouseHandler,
    PromptSurfaceWheelHandler,
    PromptSurfaceWheelHost,
)
from ..interactions.deletion_controller import (
    PromptDeletionContextProvider,
    PromptDeletionProjectionEffects,
    PromptSurfaceDeletionController,
)
from ..interactions.external_text_input import PromptExternalTextInsertion
from ..interactions.text_mutation_controller import (
    PromptProjectionTextMutationController,
)
from ..interactions.undo_coalescing import PromptUndoCoalescingController
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .editing_runtime import PromptProjectionEditingRuntimeFactory
from .caret_state_owner import PromptProjectionCaretStateOwner
from .frame_state import PromptProjectionEditorState
from .history_owner import PromptProjectionHistoryOwner
from .input_method_controller import PromptInputMethodController, PromptInputMethodHost
from .undo_payload import PromptProjectionUndoPayload
from .viewport_event_router import PromptProjectionViewportEventRouter
from .session import PromptProjectionSession

THost = TypeVar("THost")


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceInputBindings(Generic[THost]):
    """Declare editing services and host ports required by source input."""

    input_method_host: PromptInputMethodHost
    deletion_context_provider: PromptDeletionContextProvider
    deletion_projection_effects: PromptDeletionProjectionEffects
    key_host: PromptSurfaceKeyHost
    wheel_host: PromptSurfaceWheelHost
    editing_runtime_host: THost
    editing_runtime_factory: PromptProjectionEditingRuntimeFactory[
        THost,
        PromptProjectionUndoPayload,
    ]
    editing_session: PromptEditingSession[PromptProjectionUndoPayload]
    caret_state: PromptProjectionCaretStateOwner
    projection_session: PromptProjectionSession
    editor_state: PromptProjectionEditorState
    viewport: QWidget
    layout: PromptLayoutEditToFrameCoordinator
    mouse: PromptSurfaceMouseHandler
    set_cursor_positions: Callable[[int, int], object]
    publish_undo_available: Callable[[bool], None]
    publish_redo_available: Callable[[bool], None]
    external_text_insertion: PromptExternalTextInsertion
    finish_pending_key_edit_block: Callable[[str], None]
    publish_render_frame: Callable[[], None]
    request_update: Callable[[], None]
    input_method_hints: Callable[[], Qt.InputMethodHint]
    viewport_rect: Callable[[], QRectF]
    parent: QObject


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceInputRuntime:
    """Expose the complete controller graph for mounted source input."""

    edit_execution: PromptEditExecution[PromptProjectionUndoPayload]
    source_commands: PromptSourceCommandService[PromptProjectionUndoPayload]
    text_mutations: PromptProjectionTextMutationController[PromptProjectionUndoPayload]
    undo_coalescing: PromptUndoCoalescingController[PromptProjectionUndoPayload]
    history: PromptProjectionHistoryOwner
    input_method: PromptInputMethodController
    deletion: PromptSurfaceDeletionController[PromptProjectionUndoPayload]
    key: PromptSurfaceKeyHandler[PromptProjectionUndoPayload]
    wheel: PromptSurfaceWheelHandler
    external_text: PromptExternalTextInputOwner
    viewport_events: PromptProjectionViewportEventRouter


def build_prompt_projection_surface_input_runtime(
    bindings: PromptProjectionSurfaceInputBindings[THost],
) -> PromptProjectionSurfaceInputRuntime:
    """Build initialized input controllers around one editing runtime."""

    history = PromptProjectionHistoryOwner(
        editing_session=bindings.editing_session,
        caret_state=bindings.caret_state,
        projection_session=bindings.projection_session,
        editor_state=bindings.editor_state,
        layout=bindings.layout,
        set_cursor_positions=bindings.set_cursor_positions,
        publish_undo_available=bindings.publish_undo_available,
        publish_redo_available=bindings.publish_redo_available,
    )
    editing_runtime = bindings.editing_runtime_factory(
        bindings.editing_runtime_host,
        history,
    )
    history.bind_clipboard_history(editing_runtime.clipboard_history)
    input_method = PromptInputMethodController(
        bindings.input_method_host,
        text_mutations=editing_runtime.text_mutations,
        finish_pending_key_edit_block=bindings.finish_pending_key_edit_block,
        publish_render_frame=bindings.publish_render_frame,
        request_update=bindings.request_update,
        input_method_hints=bindings.input_method_hints,
        viewport_rect=bindings.viewport_rect,
    )
    deletion = PromptSurfaceDeletionController(
        context_provider=bindings.deletion_context_provider,
        projection_effects=bindings.deletion_projection_effects,
        source_commands=editing_runtime.source_commands,
    )
    key = PromptSurfaceKeyHandler(
        bindings.key_host,
        deletion_controller=deletion,
        text_mutations=editing_runtime.text_mutations,
        clipboard_history_actions=lambda: history.clipboard_history_actions,
        undo_coalescing_actions=lambda: editing_runtime.undo_coalescing,
    )
    wheel = PromptSurfaceWheelHandler(bindings.wheel_host)
    external_text = PromptExternalTextInputOwner(bindings.external_text_insertion)
    viewport_events = PromptProjectionViewportEventRouter(
        viewport=bindings.viewport,
        layout=bindings.layout,
        mouse=bindings.mouse,
        wheel=wheel,
        external_text=external_text,
        parent=bindings.parent,
    )
    return PromptProjectionSurfaceInputRuntime(
        edit_execution=editing_runtime.execution,
        source_commands=editing_runtime.source_commands,
        text_mutations=editing_runtime.text_mutations,
        undo_coalescing=editing_runtime.undo_coalescing,
        history=history,
        input_method=input_method,
        deletion=deletion,
        key=key,
        wheel=wheel,
        external_text=external_text,
        viewport_events=viewport_events,
    )


__all__ = [
    "PromptProjectionSurfaceInputBindings",
    "PromptProjectionSurfaceInputRuntime",
    "build_prompt_projection_surface_input_runtime",
]
