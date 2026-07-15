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

"""Bind prompt-editor collaborators without owning their runtime behavior."""

from __future__ import annotations

from typing import Any, Protocol, cast

from PySide6.QtCore import QObject
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget

from ..shell import (
    PromptShellQFluentChrome,
    PromptShellScrollDelegate,
    PromptShellSizingController,
)
from .collaborator_bundle import PromptEditorCollaborators


class PromptEditorSignalHost(Protocol):
    """Describe the public widget hooks needed for constructor-time signal wiring."""

    textChanged: Any
    cursorPositionChanged: Any
    _qfluent_chrome: PromptShellQFluentChrome
    _scroll_delegate: PromptShellScrollDelegate
    _sizing: PromptShellSizingController

    def installEventFilter(self, event_filter: QObject) -> None:  # noqa: N802
        """Install one event filter on the host editor."""

    def verticalScrollBar(self) -> Any:  # noqa: N802
        """Return the editor-visible vertical scrollbar."""

    def viewport(self) -> QWidget:
        """Return the projection viewport exposed by the editor."""

    def _shell_viewport(self) -> QWidget:
        """Return the QFluent shell viewport."""

    def _allow_surface_wheel_scroll(self, event: QWheelEvent) -> bool:
        """Return whether surface wheel scrolling may consume a wheel event."""

    def _handle_surface_text_changed(self) -> None:
        """Handle a source text change emitted by the projection surface."""

    def _handle_surface_syntax_action(self, action: object) -> None:
        """Handle a syntax action emitted by the projection surface."""

    def _handle_surface_mouse_release(self) -> None:
        """Handle completion of a mouse interaction on the surface."""


class PromptEditorDiagnosticsControllerBinding(Protocol):
    """Describe diagnostics controller slots used by prompt-editor signal wiring."""

    def handle_text_changed(self) -> None:
        """Refresh diagnostics after text changes."""

    def refresh_visible_diagnostics(self) -> None:
        """Refresh diagnostics visibility after cursor changes."""


class PromptLoraSourceChangeController(Protocol):
    """Observe authoritative prompt source changes for LoRA context refresh."""

    def handle_source_changed(self) -> None:
        """Invalidate actions and schedule current scheduled-LoRA context."""


def bind_prompt_editor_signals(
    editor: PromptEditorSignalHost,
    collaborators: PromptEditorCollaborators,
    *,
    lora_source_changes: PromptLoraSourceChangeController,
) -> None:
    """Connect constructor-time prompt-editor signals to existing owners."""

    surface = collaborators.surface
    token_weight_controls = collaborators.token_weight_controls
    interaction_controller = collaborators.interaction_controller

    surface.attach_focus_host(surface)
    surface.set_wheel_scroll_permission(editor._allow_surface_wheel_scroll)
    surface.installEventFilter(cast(QObject, editor))
    editor._scroll_delegate.bind_host_scroll_delegate_to_surface(surface)
    surface.contentHeightChanged.connect(
        editor._sizing.handle_surface_content_height_changed
    )
    surface.textChanged.connect(editor._handle_surface_text_changed)
    surface.cursorPositionChanged.connect(editor.cursorPositionChanged)
    surface.undoAvailableChanged.connect(cast(Any, editor).undoAvailableChanged)
    surface.redoAvailableChanged.connect(cast(Any, editor).redoAvailableChanged)
    surface.syntaxActionTriggered.connect(editor._handle_surface_syntax_action)
    surface.mouseInteractionFinished.connect(editor._handle_surface_mouse_release)
    surface.loraContextMenuRequested.connect(
        collaborators.inline_lora_menu_presenter.show_lora_context_menu
    )
    surface.backingFillInvalidated.connect(
        editor._qfluent_chrome.handle_surface_backing_fill_invalidated
    )

    editor.installEventFilter(token_weight_controls)
    surface.set_weight_click_handler(token_weight_controls.handle_exact_weight_click)
    surface.set_weight_double_click_handler(
        token_weight_controls.begin_exact_weight_edit_at_position
    )
    editor.textChanged.connect(interaction_controller.handle_text_changed)
    editor.textChanged.connect(lora_source_changes.handle_source_changed)
    editor.cursorPositionChanged.connect(
        interaction_controller.handle_cursor_position_changed
    )
    surface.emphasisShortcutTriggered.connect(interaction_controller.modify_emphasis)
    token_weight_controls.tokenWeightStepTriggered.connect(
        interaction_controller.apply_token_weight_step_intent
    )
    token_weight_controls.tokenWeightWheelStepTriggered.connect(
        interaction_controller.apply_token_weight_wheel_step_intent
    )
    token_weight_controls.visibleTokenRangeChanged.connect(
        interaction_controller.handle_overlay_visible_token_range_changed
    )
    token_weight_controls.visibleTokenContentRangeChanged.connect(
        interaction_controller.handle_overlay_visible_token_changed
    )
    editor.verticalScrollBar().valueChanged.connect(
        editor._scroll_delegate.handle_viewport_scroll_value_changed
    )
    editor._shell_viewport().installEventFilter(cast(QObject, editor))
    editor.viewport().installEventFilter(cast(QObject, editor))


def bind_prompt_editor_diagnostics_signals(
    editor: PromptEditorSignalHost,
    controller: PromptEditorDiagnosticsControllerBinding,
) -> None:
    """Connect deferred diagnostics controller slots to editor signals."""

    editor.textChanged.connect(controller.handle_text_changed)
    editor.cursorPositionChanged.connect(controller.refresh_visible_diagnostics)


__all__ = [
    "PromptEditorDiagnosticsControllerBinding",
    "PromptEditorSignalHost",
    "PromptLoraSourceChangeController",
    "bind_prompt_editor_diagnostics_signals",
    "bind_prompt_editor_signals",
]
