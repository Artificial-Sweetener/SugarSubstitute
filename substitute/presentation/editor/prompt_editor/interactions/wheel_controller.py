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

"""Route prompt-editor wheel intent through narrow interaction protocols."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from PySide6.QtCore import QElapsedTimer, QPointF, QTimer
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QScrollBar, QWidget
from shiboken6 import isValid

from substitute.presentation.widgets.wheel_intent import DEFAULT_WHEEL_GESTURE_IDLE_MS

from ..projection.model import PromptProjectionToken


@dataclass(frozen=True, slots=True)
class _PromptWheelBoundarySpill:
    """Track one prompt-local wheel burst that reached a scroll boundary."""

    direction: int
    boundary_value: int
    last_scroll_at_ms: int


class PromptWheelScrollResult(Enum):
    """Describe how prompt-local wheel routing handled one wheel event."""

    CONSUMED = "consumed"
    BUBBLE = "bubble"
    IGNORED = "ignored"


class PromptTokenWeightWheelIntentController:
    """Own token-weight wheel dwell, activation, and accent publication."""

    def __init__(self) -> None:
        """Create token-wheel state without binding external policy callbacks."""

        self._token_pointer_moved: (
            Callable[[PromptProjectionToken, QPointF], None] | None
        ) = None
        self._token_wheel_ready: (
            Callable[[PromptProjectionToken, QPointF], bool] | None
        ) = None
        self._token_wheel_allowed: (
            Callable[[PromptProjectionToken, QWheelEvent], bool] | None
        ) = None
        self._token_activated: (
            Callable[[PromptProjectionToken, QPointF], None] | None
        ) = None
        self._token_range_changed: Callable[[tuple[int, int] | None], None] | None = (
            None
        )
        self._candidate_token: PromptProjectionToken | None = None
        self._candidate_global_position: QPointF | None = None
        self._ready_token: PromptProjectionToken | None = None
        self._refresh_timer = QTimer()
        self._refresh_timer.setInterval(50)
        self._refresh_timer.timeout.connect(self._refresh_ready_token)

    def set_handlers(
        self,
        *,
        token_pointer_moved: Callable[[PromptProjectionToken, QPointF], None] | None,
        token_wheel_ready: Callable[[PromptProjectionToken, QPointF], bool] | None,
        token_wheel_allowed: Callable[[PromptProjectionToken, QWheelEvent], bool]
        | None,
        token_wheel_activated: Callable[[PromptProjectionToken, QPointF], None] | None,
        token_range_changed: Callable[[tuple[int, int] | None], None] | None,
    ) -> None:
        """Install callbacks supplied by the editor-level wheel-intent owner."""

        self._token_pointer_moved = token_pointer_moved
        self._token_wheel_ready = token_wheel_ready
        self._token_wheel_allowed = token_wheel_allowed
        self._token_activated = token_wheel_activated
        self._token_range_changed = token_range_changed
        self.clear_candidate()

    @property
    def candidate_token(self) -> PromptProjectionToken | None:
        """Return the token currently considered for wheel dwell readiness."""

        return self._candidate_token

    def refresh_ready_token(self) -> None:
        """Refresh token-wheel readiness for tests and host-triggered repaints."""

        self._refresh_ready_token()

    def record_token_pointer_move(
        self,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record pointer movement over one numeric token."""

        self._candidate_token = token
        self._candidate_global_position = QPointF(global_position)
        if self._token_pointer_moved is not None:
            self._token_pointer_moved(token, global_position)
        self._refresh_ready_token()
        if self._token_wheel_ready is not None:
            self._refresh_timer.start()

    def activate_token(
        self,
        token: PromptProjectionToken,
        global_position: QPointF,
    ) -> None:
        """Record explicit token activation for focus-required wheel mode."""

        if self._token_activated is not None:
            self._token_activated(token, global_position)

    def token_wheel_is_allowed(
        self,
        token: PromptProjectionToken,
        event: QWheelEvent,
    ) -> bool:
        """Return whether one token may consume wheel input."""

        if self._token_wheel_allowed is None:
            return True
        return self._token_wheel_allowed(token, event)

    def refresh_candidate_from_pointer(
        self,
        candidate: tuple[PromptProjectionToken, QPointF] | None,
    ) -> None:
        """Refresh dwell accent state from the current overlay pointer candidate."""

        if candidate is None:
            self.clear_candidate()
            return
        token, global_position = candidate
        self._candidate_token = token
        self._candidate_global_position = QPointF(global_position)
        self._refresh_ready_token()
        if self._token_wheel_ready is not None:
            self._refresh_timer.start()

    def clear_candidate(self) -> None:
        """Clear token-wheel dwell and accent state."""

        self._candidate_token = None
        self._candidate_global_position = None
        self._refresh_timer.stop()
        self._set_ready_token(None)

    def _refresh_ready_token(self) -> None:
        """Publish the token range that becomes wheel-ready from pointer dwell."""

        token = self._candidate_token
        global_position = self._candidate_global_position
        if token is None or global_position is None or self._token_wheel_ready is None:
            self._set_ready_token(None)
            return
        if self._token_wheel_ready(token, global_position):
            self._set_ready_token(token)
            self._refresh_timer.stop()
            return
        self._set_ready_token(None)

    def _set_ready_token(self, token: PromptProjectionToken | None) -> None:
        """Publish ready-token range changes for projection accent state."""

        previous_range = self._outer_range_for_token(self._ready_token)
        next_range = self._outer_range_for_token(token)
        self._ready_token = token
        if previous_range == next_range or self._token_range_changed is None:
            return
        self._token_range_changed(next_range)

    @staticmethod
    def _outer_range_for_token(
        token: PromptProjectionToken | None,
    ) -> tuple[int, int] | None:
        """Return one token outer source range."""

        if token is None:
            return None
        return (token.source_start, token.source_end)


class PromptSurfaceWheelHost(Protocol):
    """Expose bounded surface operations needed by interim wheel routing."""

    def verticalScrollBar(self) -> QScrollBar:  # noqa: N802
        """Return the internal viewport scrollbar owned by QAbstractScrollArea."""

    def viewport(self) -> QWidget:
        """Return the viewport widget that should repaint after scroll changes."""

    def _sync_layout_state(self) -> None:
        """Synchronize scrollbar range and projection layout state."""


class PromptSurfaceWheelHandler:
    """Route prompt surface scrolling without making the surface own wheel policy."""

    def __init__(self, host: PromptSurfaceWheelHost) -> None:
        """Bind wheel routing to the surface operations it may perform."""

        self._host = host
        self._external_scroll_bar: QScrollBar | None = None
        self._scroll_permission: Callable[[QWheelEvent], bool] | None = None
        self._boundary_spill: _PromptWheelBoundarySpill | None = None
        self._spill_clock = QElapsedTimer()
        self._spill_clock.start()

    def attach_external_scroll_bar(self, scroll_bar: QScrollBar) -> None:
        """Mirror layout range and scroll offset onto one host-owned scrollbar."""

        self._external_scroll_bar = scroll_bar
        scroll_bar.valueChanged.connect(self._handle_external_scroll_value_changed)
        scroll_bar.destroyed.connect(self._handle_external_scroll_bar_destroyed)
        self._host.verticalScrollBar().hide()
        self._host._sync_layout_state()

    def refresh_scroll(self) -> None:
        """Repaint after the host scrollbar moves the visible projection window."""

        self._host.viewport().update()

    def set_wheel_scroll_permission(
        self,
        permission: Callable[[QWheelEvent], bool] | None,
    ) -> None:
        """Install the host policy that decides whether prompt scrolling is armed."""

        self._scroll_permission = permission

    def clear_boundary_spill(self) -> None:
        """Forget any active prompt-local boundary-spill burst."""

        self._boundary_spill = None

    def handle_prompt_wheel_scroll(
        self,
        event: QWheelEvent,
    ) -> PromptWheelScrollResult:
        """Handle policy-aware prompt surface scrolling."""

        scroll_bar = self.visible_scroll_bar()
        if scroll_bar.maximum() <= scroll_bar.minimum():
            return PromptWheelScrollResult.IGNORED
        scroll_delta = self._wheel_scroll_delta(event, scroll_bar=scroll_bar)
        if scroll_delta == 0:
            return PromptWheelScrollResult.IGNORED
        direction = self._wheel_scroll_direction(scroll_delta)
        now_ms = self._spill_now_ms()
        next_value = scroll_bar.value() - scroll_delta
        clamped_value = max(scroll_bar.minimum(), min(scroll_bar.maximum(), next_value))
        if clamped_value == scroll_bar.value():
            if self._should_consume_boundary_spill(
                direction=direction,
                boundary_value=scroll_bar.value(),
                timestamp_ms=now_ms,
            ):
                return PromptWheelScrollResult.CONSUMED
            return PromptWheelScrollResult.BUBBLE
        if self._scroll_permission is not None and not self._scroll_permission(event):
            return PromptWheelScrollResult.BUBBLE
        scroll_bar.setValue(clamped_value)
        self._record_scroll_success(
            direction=direction,
            boundary_value=clamped_value,
            timestamp_ms=now_ms,
            scroll_bar=scroll_bar,
        )
        return PromptWheelScrollResult.CONSUMED

    def sync_external_scroll_range(self, *, page_step: int, scroll_range: int) -> None:
        """Mirror the internal viewport range onto the external scrollbar if present."""

        external_scroll_bar = self._external_scroll_bar_or_none()
        if external_scroll_bar is None:
            return
        external_scroll_bar.setPageStep(page_step)
        external_scroll_bar.setRange(0, scroll_range)
        external_scroll_bar.setValue(min(external_scroll_bar.value(), scroll_range))

    def visible_scroll_bar(self) -> QScrollBar:
        """Return the scrollbar that currently owns the visible scroll offset."""

        external_scroll_bar = self._external_scroll_bar_or_none()
        if external_scroll_bar is not None:
            return external_scroll_bar
        return self._host.verticalScrollBar()

    def scroll_offset(self) -> float:
        """Return the active vertical scroll offset used by layout and paint."""

        return float(self.visible_scroll_bar().value())

    def _wheel_scroll_delta(
        self,
        event: QWheelEvent,
        *,
        scroll_bar: QScrollBar,
    ) -> int:
        """Translate one wheel event into the pixel delta expected by the scroll bar."""

        pixel_delta = event.pixelDelta().y()
        if pixel_delta != 0:
            return pixel_delta
        angle_delta = event.angleDelta().y()
        if angle_delta == 0:
            return 0
        step_size = max(1, scroll_bar.singleStep())
        wheel_lines = max(1, QApplication.wheelScrollLines())
        return int(round((angle_delta / 120.0) * step_size * wheel_lines))

    def _wheel_scroll_direction(self, scroll_delta: int) -> int:
        """Return the scrollbar movement direction implied by one wheel delta."""

        if scroll_delta < 0:
            return 1
        if scroll_delta > 0:
            return -1
        return 0

    def _spill_now_ms(self) -> int:
        """Return the prompt-local timestamp used for boundary spill suppression."""

        return int(self._spill_clock.elapsed())

    def _record_scroll_success(
        self,
        *,
        direction: int,
        boundary_value: int,
        timestamp_ms: int,
        scroll_bar: QScrollBar,
    ) -> None:
        """Remember successful prompt scrolls that ended at a boundary."""

        if boundary_value not in {scroll_bar.minimum(), scroll_bar.maximum()}:
            self._boundary_spill = None
            return
        self._boundary_spill = _PromptWheelBoundarySpill(
            direction=direction,
            boundary_value=boundary_value,
            last_scroll_at_ms=timestamp_ms,
        )

    def _should_consume_boundary_spill(
        self,
        *,
        direction: int,
        boundary_value: int,
        timestamp_ms: int,
    ) -> bool:
        """Return whether a boundary wheel event belongs to the current prompt burst."""

        spill = self._boundary_spill
        if spill is None:
            return False
        if spill.direction != direction or spill.boundary_value != boundary_value:
            self._boundary_spill = None
            return False
        if timestamp_ms - spill.last_scroll_at_ms >= DEFAULT_WHEEL_GESTURE_IDLE_MS:
            self._boundary_spill = None
            return False
        self._boundary_spill = _PromptWheelBoundarySpill(
            direction=spill.direction,
            boundary_value=spill.boundary_value,
            last_scroll_at_ms=timestamp_ms,
        )
        return True

    def _handle_external_scroll_value_changed(self, value: int) -> None:
        """Mirror host scrollbar movement into the internal viewport state."""

        scroll_bar = self._host.verticalScrollBar()
        scroll_bar.setValue(value)
        self._host.viewport().update()

    def _handle_external_scroll_bar_destroyed(self) -> None:
        """Clear the cached host scrollbar once Qt destroys it."""

        self._external_scroll_bar = None

    def _external_scroll_bar_or_none(self) -> QScrollBar | None:
        """Return the cached host scrollbar only while the Qt object remains valid."""

        external_scroll_bar = self._external_scroll_bar
        if external_scroll_bar is None:
            return None
        if not isValid(external_scroll_bar):
            self._external_scroll_bar = None
            return None
        return external_scroll_bar


class PromptWheelHost(Protocol):
    """Expose prompt-editor wheel event routes without leaking widget internals."""

    def prompt_surface_handle_wheel_scroll(
        self,
        event: QWheelEvent,
    ) -> PromptWheelScrollResult:
        """Route one wheel event to prompt surface scrolling."""

    def prompt_surface_wheel_event_is_allowed(self, event: QWheelEvent) -> bool:
        """Return whether the prompt surface may consume one wheel event."""

    def forward_wheel_event_to_editor_panel(self, event: QWheelEvent) -> None:
        """Forward intentionally bubbled prompt wheel input to the editor panel."""


class PromptWheelController:
    """Arbitrate prompt wheel intent between overlays, surface scroll, and panel."""

    def __init__(
        self,
        host: PromptWheelHost,
        *,
        token_weight_wheel_intent: PromptTokenWeightWheelIntentController,
        token_weight_wheel_handler: Callable[[QWheelEvent], bool],
    ) -> None:
        """Bind wheel arbitration to the prompt editor host protocol."""

        self._host = host
        self._token_weight_wheel_intent = token_weight_wheel_intent
        self._token_weight_wheel_handler = token_weight_wheel_handler

    @property
    def token_weight_wheel_intent(self) -> PromptTokenWeightWheelIntentController:
        """Return the owner for token-weight wheel dwell and accent state."""

        return self._token_weight_wheel_intent

    def set_token_weight_handlers(
        self,
        *,
        token_pointer_moved: Callable[[PromptProjectionToken, QPointF], None] | None,
        token_wheel_ready: Callable[[PromptProjectionToken, QPointF], bool] | None,
        token_wheel_allowed: Callable[[PromptProjectionToken, QWheelEvent], bool]
        | None,
        token_wheel_activated: Callable[[PromptProjectionToken, QPointF], None] | None,
        token_range_changed: Callable[[tuple[int, int] | None], None] | None,
    ) -> None:
        """Install token-weight wheel-intent callbacks on the wheel owner."""

        self._token_weight_wheel_intent.set_handlers(
            token_pointer_moved=token_pointer_moved,
            token_wheel_ready=token_wheel_ready,
            token_wheel_allowed=token_wheel_allowed,
            token_wheel_activated=token_wheel_activated,
            token_range_changed=token_range_changed,
        )

    def allow_surface_wheel_scroll(self, event: QWheelEvent) -> bool:
        """Return whether prompt-local surface scrolling is currently permitted."""

        return self._host.prompt_surface_wheel_event_is_allowed(event)

    def handle_viewport_wheel_event(self, event: QWheelEvent) -> bool:
        """Route one host viewport wheel event through prompt-local owners."""

        if self._token_weight_wheel_handler(event):
            event.accept()
            return True
        result = self._host.prompt_surface_handle_wheel_scroll(event)
        if result is PromptWheelScrollResult.CONSUMED:
            event.accept()
            return True
        if result is PromptWheelScrollResult.BUBBLE:
            self._host.forward_wheel_event_to_editor_panel(event)
            return True
        event.ignore()
        return True


__all__ = [
    "PromptSurfaceWheelHandler",
    "PromptSurfaceWheelHost",
    "PromptTokenWeightWheelIntentController",
    "PromptWheelController",
    "PromptWheelHost",
    "PromptWheelScrollResult",
]
