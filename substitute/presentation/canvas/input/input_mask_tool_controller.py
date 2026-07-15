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
from typing import Callable, Protocol, cast
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


class _InputPaneToolPort(Protocol):
    """Describe QPane tool and mask catalog APIs used by the controller."""

    def setControlMode(self, mode: object) -> None:  # noqa: N802
        """Set the active QPane control mode."""

    def catalog(self) -> object:
        """Return QPane's catalog facade."""


class InputMaskToolController:
    """Coordinate Input mask tool modes from authorized pane state."""

    def __init__(
        self,
        *,
        input_pane: _InputPaneToolPort,
        current_image_id_provider: Callable[[], UUID | None],
        menu_state_sink: Callable[[InputMaskToolMenuState], None] | None = None,
    ) -> None:
        """Store QPane and view-state collaborators for mask tool decisions."""

        self._input_pane = input_pane
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

        qpane_mode = self._qpane_mode_for_intent(mode)
        if qpane_mode is None:
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
        self._input_pane.setControlMode(qpane_mode)
        log_debug(_LOGGER, "Applied input mask tool mode", requested_mode=mode)
        return True

    def request_brush_mode_after_authorized_mask_activation(self) -> bool:
        """Switch to brush mode after Input state has activated an owned mask."""

        return self.request_tool_mode(InputMaskToolMode.BRUSH)

    def _active_image_has_masks(self) -> bool:
        """Return whether the authorized active Input image has mask layers."""

        image_id = self._current_image_id_provider()
        if image_id is None:
            return False
        catalog = self._input_pane.catalog()
        mask_manager_factory = getattr(catalog, "maskManager", None)
        mask_manager = (
            mask_manager_factory() if callable(mask_manager_factory) else None
        )
        get_masks_for_image = getattr(mask_manager, "get_masks_for_image", None)
        if not callable(get_masks_for_image):
            return False
        return bool(get_masks_for_image(image_id))

    @staticmethod
    def _qpane_mode_for_intent(mode: str) -> object | None:
        """Return the QPane control mode constant for one Input tool intent."""

        from qpane import QPane

        if mode == InputMaskToolMode.PAN_ZOOM:
            return cast(object, QPane.CONTROL_MODE_PANZOOM)
        if mode == InputMaskToolMode.BRUSH:
            return cast(object, QPane.CONTROL_MODE_DRAW_BRUSH)
        if mode == InputMaskToolMode.SMART_SELECT:
            return cast(object, QPane.CONTROL_MODE_SMART_SELECT)
        return None


__all__ = [
    "InputMaskToolController",
    "InputMaskToolMenuState",
    "InputMaskToolMode",
]
