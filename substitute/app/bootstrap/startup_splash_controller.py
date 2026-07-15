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

"""Own launch splash presentation policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from substitute.app.bootstrap.launch_splash import (
    LaunchSplashClient,
    ProcessPumpTaskFactory,
    SplashCancelCallback,
    start_launch_splash,
)
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.domain.appearance import AppearanceBackdropMode


class StartupCancelBridge(QObject):
    """Route helper-thread splash cancel events onto the Qt startup thread."""

    cancel_requested = Signal()


@dataclass(frozen=True, slots=True)
class StartupSplashPorts:
    """Group launch-splash presentation adapters for startup orchestration."""

    create_cancel_bridge: Callable[[], StartupCancelBridge]
    start_or_adopt_launch_splash: Callable[..., LaunchSplashClient]


def create_startup_cancel_bridge() -> StartupCancelBridge:
    """Create the Qt bridge for launch-splash cancel requests."""

    return StartupCancelBridge()


def launch_splash_backdrop_mode_value(resolved_appearance: Any) -> str:
    """Return the splash-specific backdrop value derived from resolved appearance.

    Splash intentionally uses plain Mica instead of Mica Alt. Acrylic remains
    opt-in when the user selected it.
    """

    backdrop_mode = getattr(resolved_appearance, "effective_backdrop_mode", None)
    if backdrop_mode is AppearanceBackdropMode.ACRYLIC:
        return AppearanceBackdropMode.ACRYLIC.value
    if backdrop_mode is None:
        return "none"
    return "mica"


def start_or_adopt_launch_splash(
    *,
    splash: LaunchSplashClient | None,
    startup_timer: StartupTimer,
    resolved_appearance: Any,
    on_cancel_requested: SplashCancelCallback,
    process_pump_task_factory: ProcessPumpTaskFactory,
    launch_splash: Callable[..., LaunchSplashClient] | None = None,
) -> LaunchSplashClient:
    """Start a new launch splash or adopt an existing one for ready startup."""

    if splash is None:
        launch_splash = start_launch_splash if launch_splash is None else launch_splash
        with trace_span("launch_splash.start"):
            splash = launch_splash(
                startup_timer=startup_timer,
                cwd=Path(__file__).resolve().parents[3],
                theme_mode=resolved_appearance.effective_theme_mode.value,
                accent_color=resolved_appearance.effective_accent_color,
                backdrop_mode=launch_splash_backdrop_mode_value(resolved_appearance),
                on_cancel_requested=on_cancel_requested,
                process_pump_task_factory=process_pump_task_factory,
            )
    else:
        trace_mark("launch_splash.adopted", splash_type=type(splash).__name__)
    trace_mark("launch_splash.started", splash_type=type(splash).__name__)
    return splash


def create_startup_splash_ports() -> StartupSplashPorts:
    """Create launch-splash ports for startup orchestration."""

    return StartupSplashPorts(
        create_cancel_bridge=create_startup_cancel_bridge,
        start_or_adopt_launch_splash=start_or_adopt_launch_splash,
    )


__all__ = [
    "StartupCancelBridge",
    "StartupSplashPorts",
    "create_startup_cancel_bridge",
    "create_startup_splash_ports",
    "launch_splash_backdrop_mode_value",
    "start_or_adopt_launch_splash",
]
