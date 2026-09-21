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

"""Coordinate exact token-weight editing independently of overlay geometry."""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)

from .token_weight_gestures import PromptTokenWeightGestureController


class PromptTokenWeightExactEditHost(Protocol):
    """Provide projection-owned exact weight editing to the overlay controller."""

    def begin_exact_weight_edit(self, token: PromptProjectionToken) -> None:
        """Start one projection-owned exact weight edit session."""
        ...

    def cancel_exact_weight_edit(self) -> None:
        """Cancel any active projection-owned exact weight edit session."""
        ...

    def finalize_exact_weight_edit(self) -> None:
        """Commit or cancel the active exact weight edit session."""
        ...

    def exact_weight_edit_token(self) -> PromptProjectionToken | None:
        """Return the projection token currently owning exact edit mode."""
        ...

    def exact_weight_edit_active(self) -> bool:
        """Return whether exact weight edit mode is currently active."""
        ...

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local painted weight rect for one weighted token."""
        ...

    def handle_exact_weight_mouse(self, event: QMouseEvent) -> None:
        """Route viewport input through the native numeric control."""
        ...

    def handle_exact_weight_key_press(self, event: QKeyEvent) -> bool:
        """Handle one exact-weight edit key press."""
        ...

    def clear_overlay_emphasis_session_for_exact_weight(self) -> None:
        """Clear overlay-owned emphasis state after controls lose ownership."""
        ...


class PromptTokenWeightExactEditPressResult(Enum):
    """Describe how active exact editing handles one viewport press."""

    CONSUMED = "consumed"
    UPDATED = "updated"
    FINALIZE = "finalize"


class PromptTokenWeightExactEditController:
    """Own exact-edit activation gestures and projection-host coordination."""

    def __init__(
        self,
        host: PromptTokenWeightExactEditHost,
        gestures: PromptTokenWeightGestureController,
    ) -> None:
        """Bind exact editing to its projection and transient gesture owners."""

        self._host = host
        self._gestures = gestures

    @property
    def active(self) -> bool:
        """Return whether projection-owned exact editing is active."""

        return self._host.exact_weight_edit_active()

    @property
    def token(self) -> PromptProjectionToken | None:
        """Return the token currently owning exact editing."""

        return self._host.exact_weight_edit_token()

    def start(self, token: PromptProjectionToken) -> bool:
        """Start exact editing after atomically retiring pointer affordances."""

        if (
            token.value_text is None
            or token.content_start is None
            or token.content_end is None
        ):
            return False
        self._gestures.stop_hide_linger()
        self._gestures.clear_weight_preview()
        self._gestures.pressed_control = None
        self._gestures.hovered_control = None
        self._host.begin_exact_weight_edit(token)
        return True

    def cancel(self) -> bool:
        """Cancel active exact editing and its pending activation gesture."""

        if not self.active:
            return False
        self._host.cancel_exact_weight_edit()
        self._gestures.clear_click_candidate()
        return True

    def click_starts_edit(
        self,
        token: PromptProjectionToken,
        *,
        double_click_interval_ms: int,
    ) -> bool:
        """Return whether one weight click completes the activation gesture."""

        return self._gestures.weight_click_starts_exact_edit(
            token,
            double_click_interval_ms=double_click_interval_ms,
        )

    def clear_click_candidate(self) -> None:
        """Forget a pending click that can no longer activate exact editing."""

        self._gestures.clear_click_candidate()

    def handle_viewport_press(
        self,
        event: QMouseEvent,
    ) -> PromptTokenWeightExactEditPressResult:
        """Route a viewport press to exact editing or request finalization."""

        if event.button() != Qt.MouseButton.LeftButton:
            return PromptTokenWeightExactEditPressResult.CONSUMED
        token = self.token
        weight_rect = (
            None if token is None else self._host.token_weight_text_rect(token)
        )
        if weight_rect is None or not weight_rect.contains(event.position()):
            return PromptTokenWeightExactEditPressResult.FINALIZE
        self._host.handle_exact_weight_mouse(event)
        return PromptTokenWeightExactEditPressResult.UPDATED

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Route a native number-editing key through the projection owner."""

        return self._host.handle_exact_weight_key_press(event)

    def finalize(self) -> None:
        """Commit valid exact weight input or cancel invalid input."""

        self._host.finalize_exact_weight_edit()

    def clear_overlay_emphasis_session(self) -> None:
        """Clear projection emphasis after the controls lose ownership."""

        self._host.clear_overlay_emphasis_session_for_exact_weight()


__all__ = [
    "PromptTokenWeightExactEditController",
    "PromptTokenWeightExactEditHost",
    "PromptTokenWeightExactEditPressResult",
]
