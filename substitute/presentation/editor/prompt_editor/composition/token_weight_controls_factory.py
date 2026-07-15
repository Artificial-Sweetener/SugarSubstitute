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

"""Create token-weight overlays from explicit final owners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from ..geometry import autocomplete_panel_host
from ..interactions import PromptTokenWeightWheelIntentController
from ..overlays.token_weight_controls import (
    PromptTokenWeightControls,
    PromptTokenWeightControlsSurface,
    PromptTokenWeightExactEditHost,
)
from ..overlays.token_weight_geometry import PromptTokenWeightGeometry
from ..overlays.token_weight_gestures import PromptTokenWeightGestureController
from ..overlays.token_weight_view import PromptTokenWeightView


@dataclass(frozen=True, slots=True)
class PromptTokenWeightControlsFactory:
    """Build token-weight overlay adapters from composition-owned collaborators."""

    surface: PromptTokenWeightControlsSurface
    exact_edit_host: PromptTokenWeightExactEditHost
    wheel_intent_owner: PromptTokenWeightWheelIntentController

    def create_token_weight_controls(self) -> PromptTokenWeightControls:
        """Return one token-weight overlay with explicit geometry and owners."""

        surface_widget = self._surface_widget()
        host = autocomplete_panel_host(surface_widget)
        geometry = PromptTokenWeightGeometry(
            self.surface,
            host=host,
            control_width=PromptTokenWeightControls.CONTROL_WIDTH,
            control_height=PromptTokenWeightControls.CONTROL_HEIGHT,
            control_gap=PromptTokenWeightControls.CONTROL_GAP,
            control_margin=PromptTokenWeightControls.CONTROL_MARGIN,
            overlay_padding=PromptTokenWeightControls.OVERLAY_PADDING,
        )
        return PromptTokenWeightControls(
            self.surface,
            host=host,
            geometry=geometry,
            view_factory=PromptTokenWeightView,
            gesture_controller_factory=self._create_gesture_controller,
            exact_edit_host=self.exact_edit_host,
            wheel_intent_owner=self.wheel_intent_owner,
        )

    def _surface_widget(self) -> QWidget:
        """Return the projection surface as its QWidget identity."""

        return cast(QWidget, self.surface)

    @staticmethod
    def _create_gesture_controller(
        parent: QObject,
    ) -> PromptTokenWeightGestureController:
        """Return the token-weight gesture controller for one overlay."""

        return PromptTokenWeightGestureController(
            parent,
            hide_delay_ms=PromptTokenWeightControls.HIDE_DELAY_MS,
            preview_delay_ms=PromptTokenWeightControls.WEIGHT_PREVIEW_MS,
        )


__all__ = ["PromptTokenWeightControlsFactory"]
