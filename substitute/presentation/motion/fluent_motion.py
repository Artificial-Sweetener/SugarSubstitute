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

"""Centralize Fluent-style motion tokens and reduced-motion policy."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from typing import Any, Protocol

from PySide6.QtCore import QEasingCurve, QPointF
from PySide6.QtWidgets import QApplication


def _build_cubic_bezier_curve(
    control_x1: float,
    control_y1: float,
    control_x2: float,
    control_y2: float,
) -> QEasingCurve:
    """Return a Qt easing curve for one CSS-style cubic Bezier segment."""

    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(
        QPointF(control_x1, control_y1),
        QPointF(control_x2, control_y2),
        QPointF(1.0, 1.0),
    )
    return curve


ACCORDION_EXPAND_DURATION_MS = 333
ACCORDION_COLLAPSE_DURATION_MS = 167
REVEAL_FADE_DURATION_MS = 120
HIGHLIGHT_SETTLE_DURATION_MS = 220
SCROLL_DURATION_MS = 220
INPUT_SCROLL_DURATION_MS = 220
CUBE_STACK_INDICATOR_DURATION_MS = 220
CUBE_STACK_MODE_DURATION_MS = 220
SIDE_PANEL_DURATION_MS = 220
SETTINGS_PAGE_TRANSITION_DURATION_MS = 180
SETTINGS_PAGE_TRANSITION_OFFSET = 24
SETTINGS_NAV_INDICATOR_DURATION_MS = 180
ENTER_EASING_CURVE = QEasingCurve.Type.OutCubic
EXIT_EASING_CURVE = QEasingCurve.Type.InCubic
TRANSFORM_EASING_CURVE = QEasingCurve.Type.InOutCubic
ACCORDION_EXPAND_EASING_CURVE = _build_cubic_bezier_curve(0.0, 0.0, 0.0, 1.0)
ACCORDION_COLLAPSE_EASING_CURVE = _build_cubic_bezier_curve(1.0, 1.0, 0.0, 1.0)
_SPI_GETCLIENTAREAANIMATION = 0x1042
_REDUCED_MOTION_PROPERTY = "substitute.reduce_motion"


class _ConfigurablePropertyAnimation(Protocol):
    """Describe the animation surface used by shared property helpers."""

    def setDuration(self, duration: int) -> None:
        """Apply the resolved duration in milliseconds."""

    def setEasingCurve(self, curve: QEasingCurve.Type | QEasingCurve) -> None:
        """Apply the easing curve used for the transition."""

    def setStartValue(self, value: Any) -> None:
        """Configure the current animation start value."""

    def setEndValue(self, value: Any) -> None:
        """Configure the target animation end value."""

    def start(self) -> None:
        """Start the animation."""

    def stop(self) -> None:
        """Stop the animation."""


def _read_reduced_motion_override() -> bool | None:
    """Return one application override when tests or settings have provided it."""

    app = QApplication.instance()
    if app is None:
        return None
    override = app.property(_REDUCED_MOTION_PROPERTY)
    return bool(override) if override is not None else None


def _read_windows_client_area_animation_enabled() -> bool | None:
    """Return the Windows animation policy when the platform API is available."""

    user32 = getattr(ctypes, "windll", None)
    if user32 is None or not hasattr(user32, "user32"):
        return None
    enabled = wintypes.BOOL()
    result = user32.user32.SystemParametersInfoW(
        _SPI_GETCLIENTAREAANIMATION,
        0,
        ctypes.byref(enabled),
        0,
    )
    if result == 0:
        return None
    return bool(enabled.value)


def is_reduced_motion_enabled() -> bool:
    """Return whether presentation motion should collapse to near-immediate updates."""

    override = _read_reduced_motion_override()
    if override is not None:
        return override
    if os.environ.get("QT_QPA_PLATFORM", "").casefold() == "offscreen":
        return False
    enabled = _read_windows_client_area_animation_enabled()
    if enabled is None:
        return False
    return not enabled


def resolve_motion_duration(duration_ms: int) -> int:
    """Resolve one duration through the centralized reduced-motion policy."""

    return 0 if is_reduced_motion_enabled() else duration_ms


def stop_animation(animation: _ConfigurablePropertyAnimation | None) -> None:
    """Stop one in-flight animation when it exists."""

    if animation is not None:
        animation.stop()


def restart_property_animation(
    animation: _ConfigurablePropertyAnimation,
    *,
    start_value: Any,
    end_value: Any,
    duration_ms: int,
    easing_curve: QEasingCurve.Type | QEasingCurve,
) -> int:
    """Restart one property animation with shared reduced-motion handling."""

    resolved_duration = resolve_motion_duration(duration_ms)
    animation.stop()
    animation.setStartValue(start_value)
    animation.setEndValue(end_value)
    animation.setDuration(resolved_duration)
    animation.setEasingCurve(easing_curve)
    animation.start()
    return resolved_duration


__all__ = [
    "ACCORDION_COLLAPSE_DURATION_MS",
    "ACCORDION_COLLAPSE_EASING_CURVE",
    "ACCORDION_EXPAND_DURATION_MS",
    "ACCORDION_EXPAND_EASING_CURVE",
    "CUBE_STACK_INDICATOR_DURATION_MS",
    "CUBE_STACK_MODE_DURATION_MS",
    "ENTER_EASING_CURVE",
    "EXIT_EASING_CURVE",
    "HIGHLIGHT_SETTLE_DURATION_MS",
    "INPUT_SCROLL_DURATION_MS",
    "REVEAL_FADE_DURATION_MS",
    "SCROLL_DURATION_MS",
    "SETTINGS_NAV_INDICATOR_DURATION_MS",
    "SETTINGS_PAGE_TRANSITION_DURATION_MS",
    "SETTINGS_PAGE_TRANSITION_OFFSET",
    "SIDE_PANEL_DURATION_MS",
    "TRANSFORM_EASING_CURVE",
    "is_reduced_motion_enabled",
    "resolve_motion_duration",
    "restart_property_animation",
    "stop_animation",
]
