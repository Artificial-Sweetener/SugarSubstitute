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

"""Own token-weight overlay gesture state and typed interaction intents."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Literal

from PySide6.QtCore import QObject, QPointF, QRectF, QTimer

from ..projection.model import PromptProjectionToken

PromptTokenWeightControl = Literal["increase", "decrease"]


@dataclass(frozen=True, slots=True)
class PromptTokenWeightStepIntent:
    """Request one token-weight step through the interaction command owner."""

    token: PromptProjectionToken
    control: PromptTokenWeightControl
    pointer_global_position: QPointF
    show_weight_preview: bool


@dataclass(frozen=True, slots=True)
class PromptTokenWeightWheelStepIntent:
    """Request one wheel-driven token-weight step through the interaction owner."""

    token: PromptProjectionToken
    angle_delta_y: int
    pointer_global_position: QPointF
    show_weight_preview: bool


@dataclass(frozen=True, slots=True)
class PromptTokenWeightGestureSnapshot:
    """Describe transient token-weight gesture state consumed by the overlay."""

    hovered_control: PromptTokenWeightControl | None
    pressed_control: PromptTokenWeightControl | None
    pointer_host_position: QPointF | None
    weight_preview_text: str | None
    weight_preview_rect: QRectF | None
    action_in_progress: bool
    action_pointer_global_position: QPointF | None
    hide_linger_active: bool


class PromptTokenWeightGestureController(QObject):
    """Coordinate token-weight pointer gestures without building commands."""

    def __init__(
        self,
        parent: QObject,
        *,
        hide_delay_ms: int,
        preview_delay_ms: int,
    ) -> None:
        """Create timers and transient state for token-weight gestures."""

        super().__init__(parent)
        self._hovered_control: PromptTokenWeightControl | None = None
        self._pressed_control: PromptTokenWeightControl | None = None
        self._pointer_host_position: QPointF | None = None
        self._weight_preview_text: str | None = None
        self._weight_preview_rect: QRectF | None = None
        self._last_weight_click_token_id: str | None = None
        self._last_weight_click_time: float | None = None
        self._action_in_progress = False
        self._action_pointer_global_position: QPointF | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(hide_delay_ms)
        self._weight_preview_timer = QTimer(self)
        self._weight_preview_timer.setSingleShot(True)
        self._weight_preview_timer.setInterval(preview_delay_ms)

    @property
    def hide_timeout(self) -> QTimer:
        """Return the timer that ends hover hide linger."""

        return self._hide_timer

    @property
    def preview_timeout(self) -> QTimer:
        """Return the timer that clears pointer-owned preview feedback."""

        return self._weight_preview_timer

    @property
    def hovered_control(self) -> PromptTokenWeightControl | None:
        """Return the currently hovered arrow control."""

        return self._hovered_control

    @hovered_control.setter
    def hovered_control(self, control: PromptTokenWeightControl | None) -> None:
        """Set the currently hovered arrow control."""

        self._hovered_control = control

    @property
    def pressed_control(self) -> PromptTokenWeightControl | None:
        """Return the currently pressed arrow control."""

        return self._pressed_control

    @pressed_control.setter
    def pressed_control(self, control: PromptTokenWeightControl | None) -> None:
        """Set the currently pressed arrow control."""

        self._pressed_control = control

    @property
    def pointer_host_position(self) -> QPointF | None:
        """Return the latest host-local pointer position."""

        return self._pointer_host_position

    @pointer_host_position.setter
    def pointer_host_position(self, position: QPointF | None) -> None:
        """Set the latest host-local pointer position and stop hide linger."""

        self._pointer_host_position = None if position is None else QPointF(position)
        if position is not None:
            self.stop_hide_linger()

    @property
    def weight_preview_text(self) -> str | None:
        """Return the visible preview label text, if any."""

        return self._weight_preview_text

    @property
    def weight_preview_rect(self) -> QRectF | None:
        """Return the host-local preview label rect, if any."""

        return self._weight_preview_rect

    @property
    def action_in_progress(self) -> bool:
        """Return whether a command commit is currently rebuilding geometry."""

        return self._action_in_progress

    @property
    def action_pointer_global_position(self) -> QPointF | None:
        """Return the pointer position that owns current command-driven refresh."""

        return self._action_pointer_global_position

    def snapshot(self) -> PromptTokenWeightGestureSnapshot:
        """Return a read-only snapshot of current token-weight gesture state."""

        return PromptTokenWeightGestureSnapshot(
            hovered_control=self._hovered_control,
            pressed_control=self._pressed_control,
            pointer_host_position=self._pointer_host_position,
            weight_preview_text=self._weight_preview_text,
            weight_preview_rect=self._weight_preview_rect,
            action_in_progress=self._action_in_progress,
            action_pointer_global_position=self._action_pointer_global_position,
            hide_linger_active=self._hide_timer.isActive(),
        )

    def clear_transient_state(self) -> None:
        """Clear hover, press, pointer, preview, action, and click state."""

        self._hovered_control = None
        self._pressed_control = None
        self._pointer_host_position = None
        self._last_weight_click_token_id = None
        self._last_weight_click_time = None
        self._action_in_progress = False
        self._action_pointer_global_position = None
        self.clear_weight_preview()
        self.stop_hide_linger()

    def clear_click_candidate(self) -> None:
        """Forget any pending weight click waiting for a second click."""

        self._last_weight_click_token_id = None
        self._last_weight_click_time = None

    def weight_click_starts_exact_edit(
        self,
        token: PromptProjectionToken,
        *,
        double_click_interval_ms: int,
    ) -> bool:
        """Return whether this click completes the exact-edit click gesture."""

        current_time = time.monotonic()
        if (
            self._last_weight_click_token_id == token.token_id
            and self._last_weight_click_time is not None
            and (current_time - self._last_weight_click_time)
            <= (double_click_interval_ms / 1000.0)
        ):
            self.clear_click_candidate()
            return True
        self._last_weight_click_token_id = token.token_id
        self._last_weight_click_time = current_time
        return token.synthetic

    def begin_action(self, pointer_global_position: QPointF) -> None:
        """Latch pointer ownership while a token-weight command runs."""

        self._action_in_progress = True
        self._action_pointer_global_position = QPointF(pointer_global_position)

    def finish_action(self) -> None:
        """Release pointer ownership after a token-weight command finishes."""

        self._action_in_progress = False
        self._action_pointer_global_position = None

    def start_hide_linger(self, *, visible_token: PromptProjectionToken | None) -> None:
        """Delay hiding while pointer travel into the controls is still plausible."""

        if self._pressed_control is not None or visible_token is None:
            return
        self._hide_timer.start()

    def stop_hide_linger(self) -> None:
        """Stop the delayed-hide timer."""

        self._hide_timer.stop()

    def show_weight_preview(self, *, text: str, rect: QRectF) -> None:
        """Publish a short-lived pointer-owned weight preview."""

        self._weight_preview_text = text
        self._weight_preview_rect = QRectF(rect)
        self._weight_preview_timer.start()

    def clear_weight_preview(self) -> bool:
        """Clear preview feedback and return whether visible state changed."""

        if self._weight_preview_text is None and self._weight_preview_rect is None:
            self._weight_preview_timer.stop()
            return False
        self._weight_preview_timer.stop()
        self._weight_preview_text = None
        self._weight_preview_rect = None
        return True


__all__ = [
    "PromptTokenWeightControl",
    "PromptTokenWeightGestureController",
    "PromptTokenWeightGestureSnapshot",
    "PromptTokenWeightStepIntent",
    "PromptTokenWeightWheelStepIntent",
]
