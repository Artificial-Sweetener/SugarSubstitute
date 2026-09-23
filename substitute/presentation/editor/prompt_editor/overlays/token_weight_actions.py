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

"""Coordinate token-weight commands and their mounted feedback transaction."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QPointF

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)

from .token_weight_gestures import (
    PromptTokenWeightControl,
    PromptTokenWeightGestureController,
    PromptTokenWeightStepIntent,
    PromptTokenWeightWheelStepIntent,
)


class PromptTokenWeightActionHost(Protocol):
    """Expose mounted feedback operations required around one weight command."""

    def set_pointer_from_global(self, global_position: QPointF) -> None:
        """Store a global pointer in mounted host coordinates."""
        ...

    def refresh_geometry(self) -> None:
        """Refresh mounted control geometry after a prompt mutation."""
        ...

    def resolve_post_action_preview_token(
        self,
        source_token: PromptProjectionToken,
    ) -> PromptProjectionToken | None:
        """Resolve the current token that should own mutation feedback."""
        ...

    def show_weight_preview_for_token(
        self,
        token: PromptProjectionToken | None,
        *,
        pointer_global_position: QPointF,
    ) -> None:
        """Show pointer-owned feedback for an updated token."""
        ...

    def clear_weight_preview(self) -> None:
        """Clear mounted pointer-owned mutation feedback."""
        ...


class PromptTokenWeightActionCoordinator:
    """Own typed step dispatch and the command-to-feedback transaction."""

    def __init__(
        self,
        host: PromptTokenWeightActionHost,
        *,
        gestures: PromptTokenWeightGestureController,
        emit_control_step: Callable[[PromptTokenWeightStepIntent], None],
        emit_wheel_step: Callable[[PromptTokenWeightWheelStepIntent], None],
    ) -> None:
        """Bind command publication to transient gesture and mounted feedback owners."""

        self._host = host
        self._gestures = gestures
        self._emit_control_step = emit_control_step
        self._emit_wheel_step = emit_wheel_step

    def emit_control_step(
        self,
        control: PromptTokenWeightControl,
        *,
        pointer_global_position: QPointF,
        source_token: PromptProjectionToken,
        show_weight_preview: bool,
    ) -> None:
        """Dispatch one typed arrow step and reconcile mounted feedback."""

        self.commit(
            lambda: self._emit_control_step(
                PromptTokenWeightStepIntent(
                    token=source_token,
                    control=control,
                    pointer_global_position=QPointF(pointer_global_position),
                    show_weight_preview=show_weight_preview,
                )
            ),
            pointer_global_position=pointer_global_position,
            source_token=source_token,
            show_weight_preview=show_weight_preview,
        )

    def emit_wheel_step(
        self,
        angle_delta_y: int,
        *,
        pointer_global_position: QPointF,
        source_token: PromptProjectionToken,
        show_weight_preview: bool,
    ) -> None:
        """Dispatch one typed wheel step and reconcile mounted feedback."""

        self.commit(
            lambda: self._emit_wheel_step(
                PromptTokenWeightWheelStepIntent(
                    token=source_token,
                    angle_delta_y=angle_delta_y,
                    pointer_global_position=QPointF(pointer_global_position),
                    show_weight_preview=show_weight_preview,
                )
            ),
            pointer_global_position=pointer_global_position,
            source_token=source_token,
            show_weight_preview=show_weight_preview,
        )

    def commit(
        self,
        command: Callable[[], None],
        *,
        pointer_global_position: QPointF,
        source_token: PromptProjectionToken | None,
        show_weight_preview: bool,
    ) -> None:
        """Run one weight command and atomically reconcile mounted feedback."""

        self._gestures.begin_action(pointer_global_position)
        self._host.set_pointer_from_global(pointer_global_position)
        try:
            command()
        finally:
            self._gestures.finish_action()
            self._host.refresh_geometry()
            if show_weight_preview and source_token is not None:
                self._host.show_weight_preview_for_token(
                    self._host.resolve_post_action_preview_token(source_token),
                    pointer_global_position=pointer_global_position,
                )
            else:
                self._host.clear_weight_preview()


__all__ = ["PromptTokenWeightActionCoordinator", "PromptTokenWeightActionHost"]
