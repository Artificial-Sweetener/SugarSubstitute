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

"""Dispatch configured control bindings through authoritative shell actions."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent
from PySide6.QtGui import QKeyEvent

from substitute.application.controls import GenerationControlCommand
from substitute.presentation.controls import (
    KeyboardBindingValidationError,
    keyboard_binding_from_event,
)
from substitute.presentation.shell.generation_action_projection import (
    project_generation_actions,
)


class ControlBindingDispatcher:
    """Consume configured controls before focused widgets receive matching input."""

    def __init__(self, shell: Any) -> None:
        """Store the shell that owns current action availability and callbacks."""

        self._shell = shell

    def handle_event(self, event: object) -> bool | None:
        """Dispatch a matching key press or leave unrelated Qt input untouched."""

        if getattr(self._shell, "controls_keyboard_capture_active", False):
            return None
        if not isinstance(event, QKeyEvent) or event.type() != QEvent.Type.KeyPress:
            return None
        try:
            binding = keyboard_binding_from_event(event)
        except KeyboardBindingValidationError:
            return None
        command_id = self._command_for_binding(binding)
        if command_id is None:
            return None
        self._dispatch(command_id)
        event.accept()
        return True

    def _command_for_binding(self, binding: str) -> GenerationControlCommand | None:
        """Return the configured generation command for one exact keyboard binding."""

        service = getattr(self._shell, "control_binding_service", None)
        if service is None:
            return None
        for command in GenerationControlCommand:
            if service.binding_for(command.value) == binding:
                return command
        return None

    def _dispatch(self, command: GenerationControlCommand) -> None:
        """Invoke an available command through the same callbacks as titlebar buttons."""

        controller = self._shell.generation_action_controller
        presentation = project_generation_actions(controller.generation_action_state())
        actions = self._shell.workspace_generation_actions
        if command is GenerationControlCommand.ACTIVATE:
            if presentation.play_enabled:
                actions.on_generate_clicked()
            return
        if command is GenerationControlCommand.TOGGLE_MODE:
            if presentation.mode_menu_enabled:
                current_mode = getattr(
                    self._shell, "_current_generate_mode", "generate"
                )
                controller.set_generation_selected_mode(
                    "continuous" if current_mode == "generate" else "generate"
                )
            return
        if command is GenerationControlCommand.SKIP:
            if presentation.skip_enabled:
                actions.on_skip_generation_clicked()
            return
        if command is GenerationControlCommand.STOP and presentation.stop_enabled:
            actions.on_stop_generation_clicked()


__all__ = ["ControlBindingDispatcher"]
