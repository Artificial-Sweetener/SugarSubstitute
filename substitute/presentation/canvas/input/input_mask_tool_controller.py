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

"""Own Input canvas mask tool mode policy outside the widget."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID

from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_mask_tool_controller")


class InputMaskToolMode:
    """Name supported Input mask tool intents."""

    PAN_ZOOM = "pan_zoom"
    BRUSH = "brush"
    SMART_SELECT = "smart_select"


@dataclass(frozen=True)
class InputMaskToolMenuState:
    """Describe the currently available Input mask tool actions."""

    brush_enabled: bool = False
    smart_select_enabled: bool = False


class InputMaskToolDocumentPort(Protocol):
    """Describe source-neutral Input document mask availability queries."""

    def image_has_masks(self, image_id: UUID | None) -> bool:
        """Return whether one application image contains at least one mask."""


class InputMaskToolController:
    """Coordinate Input mask tool modes from authorized document state."""

    def __init__(
        self,
        *,
        input_document: InputMaskToolDocumentPort,
        control_mode_setter: Callable[[str], None],
        current_image_id_provider: Callable[[], UUID | None],
        menu_state_sink: Callable[[InputMaskToolMenuState], None] | None = None,
    ) -> None:
        """Store document and view-state collaborators for mask tool decisions."""

        self._input_document = input_document
        self._control_mode_setter = control_mode_setter
        self._current_image_id_provider = current_image_id_provider
        self._menu_state_sink = menu_state_sink

    def refresh_tool_menu_state(self) -> InputMaskToolMenuState:
        """Publish and return the current mask tool availability state."""

        state = InputMaskToolMenuState(
            brush_enabled=self._active_image_has_masks(),
            smart_select_enabled=self._active_image_has_masks(),
        )
        if self._menu_state_sink is not None:
            self._menu_state_sink(state)
        log_debug(
            _LOGGER,
            "Refreshed input mask tool menu state",
            brush_enabled=state.brush_enabled,
            smart_select_enabled=state.smart_select_enabled,
        )
        return state

    def request_tool_mode(self, mode: str) -> bool:
        """Apply one user-requested tool mode when current state permits it."""

        if mode not in {
            InputMaskToolMode.PAN_ZOOM,
            InputMaskToolMode.BRUSH,
            InputMaskToolMode.SMART_SELECT,
        }:
            log_warning(
                _LOGGER,
                "Rejected unknown input mask tool mode",
                requested_mode=mode,
            )
            return False
        if mode in {InputMaskToolMode.BRUSH, InputMaskToolMode.SMART_SELECT}:
            if not self._active_image_has_masks():
                log_warning(
                    _LOGGER,
                    "Rejected input mask tool mode without active masks",
                    requested_mode=mode,
                )
                return False
        self._control_mode_setter(mode)
        log_debug(_LOGGER, "Applied input mask tool mode", requested_mode=mode)
        return True

    def request_brush_mode_after_authorized_mask_activation(self) -> bool:
        """Switch to brush mode after Input state has activated an owned mask."""

        return self.request_tool_mode(InputMaskToolMode.BRUSH)

    def _active_image_has_masks(self) -> bool:
        """Return whether the authorized active Input image has mask layers."""

        return self._input_document.image_has_masks(self._current_image_id_provider())


__all__ = [
    "InputMaskToolController",
    "InputMaskToolMenuState",
    "InputMaskToolMode",
]
