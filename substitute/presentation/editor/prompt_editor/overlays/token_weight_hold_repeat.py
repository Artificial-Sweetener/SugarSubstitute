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

"""Own press-and-hold timing for prompt token-weight arrows."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QElapsedTimer, QObject, QPointF, QTimer, Qt
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)

from .token_weight_actions import PromptTokenWeightActionCoordinator
from .token_weight_gestures import (
    PromptTokenWeightControl,
    PromptTokenWeightGestureController,
)


class PromptTokenWeightHoldRepeater(QObject):
    """Repeat one pressed arrow without adding a release step afterward."""

    INITIAL_DELAY_MS = 400
    REPEAT_INTERVAL_MS = 120
    ACCELERATED_INTERVAL_MS = 80
    ACCELERATION_AFTER_MS = 2000

    def __init__(
        self,
        overlay: QWidget,
        *,
        visible_token: Callable[[], PromptProjectionToken | None],
        control_at_local_position: Callable[[QPointF], PromptTokenWeightControl | None],
        gestures: PromptTokenWeightGestureController,
        actions: PromptTokenWeightActionCoordinator,
    ) -> None:
        """Bind one repeat timer to the lifetime of its mounted overlay."""

        super().__init__(overlay)
        self._overlay = overlay
        self._visible_token = visible_token
        self._control_at_local_position = control_at_local_position
        self._gestures = gestures
        self._actions = actions
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._repeat)
        self._elapsed = QElapsedTimer()
        self._control: PromptTokenWeightControl | None = None
        self._source_token: PromptProjectionToken | None = None
        self._global_position: QPointF | None = None
        self._repeated = False

    def start(
        self,
        control: PromptTokenWeightControl,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Arm repetition while retaining the original pressed token target."""

        self.cancel()
        self._repeated = False
        self._control = control
        self._source_token = token
        self._global_position = QPointF(global_position)
        self._elapsed.start()
        self._timer.start(self.INITIAL_DELAY_MS)

    def finish(self) -> bool:
        """End the press and report whether repeating already emitted steps."""

        repeated = self._repeated
        self.cancel()
        self._repeated = False
        return repeated

    def cancel(self) -> None:
        """Stop the held gesture without dispatching another weight step."""

        self._timer.stop()
        self._control = None
        self._source_token = None
        self._global_position = None

    def _repeat(self) -> None:
        """Dispatch one validated step and arm the next bounded interval."""

        control = self._control
        token = self._source_token
        global_position = self._global_position
        if control is None or token is None or global_position is None:
            self.cancel()
            return
        if not self._emit_step(control, token, global_position):
            self.cancel()
            return
        if self._control != control or self._source_token is not token:
            return
        self._repeated = True
        self._timer.start(self.interval_for_elapsed_ms(self._elapsed.elapsed()))

    @classmethod
    def interval_for_elapsed_ms(cls, elapsed_ms: int) -> int:
        """Return the bounded repeat pace for one hold duration."""

        return (
            cls.ACCELERATED_INTERVAL_MS
            if elapsed_ms >= cls.ACCELERATION_AFTER_MS
            else cls.REPEAT_INTERVAL_MS
        )

    def _emit_step(
        self,
        control: PromptTokenWeightControl,
        source_token: PromptProjectionToken,
        global_position: QPointF,
    ) -> bool:
        """Dispatch only while the original arrow still owns the held point."""

        current_token = self._visible_token()
        local_position = QPointF(self._overlay.mapFromGlobal(global_position.toPoint()))
        if (
            not self._overlay.isVisible()
            or self._gestures.pressed_control != control
            or self._control_at_local_position(local_position) != control
            or current_token is None
            or current_token.kind is not source_token.kind
            or current_token.display_text != source_token.display_text
        ):
            return False
        self._actions.emit_control_step(
            control,
            pointer_global_position=global_position,
            source_token=current_token,
            show_weight_preview=(control == "increase"),
        )
        return True


__all__ = ["PromptTokenWeightHoldRepeater"]
