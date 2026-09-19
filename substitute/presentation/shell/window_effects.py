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

"""Own native backdrop identity and effects for frameless application windows."""

from __future__ import annotations

import ctypes
from enum import Enum
import sys
from typing import Any, cast

from PySide6.QtCore import Qt

from substitute.shared.logging.logger import get_logger, log_warning


_LOGGER = get_logger("presentation.shell.window_effects")
ACRYLIC_BLEND_COLOR = "A0A0A044"
_PLATFORM = sys.platform

if _PLATFORM == "win32":
    import win32con  # type: ignore[import-untyped]
    import win32gui  # type: ignore[import-untyped]

    _DWMAPI: Any | None = ctypes.WinDLL("dwmapi")
    _WINDOW_CORNER_ATTRIBUTE = 33
    _WINDOW_CORNER_ROUND = 2
    _WINDOWS_BUILD = int(sys.getwindowsversion().build)
else:  # pragma: no cover - non-Windows runtime guard
    win32con = None
    win32gui = None
    _DWMAPI = None
    _WINDOW_CORNER_ATTRIBUTE = 0
    _WINDOW_CORNER_ROUND = 0
    _WINDOWS_BUILD = 0


class ShellBackdropMode(Enum):
    """Identify the native backdrop material requested for a shell window."""

    MICA = "mica"
    MICA_ALT = "mica_alt"
    ACRYLIC = "acrylic"


def restore_rounded_window_corners(window_id: object) -> None:
    """Request Windows 11 rounded corners for a frameless acrylic window."""

    if _PLATFORM != "win32" or _DWMAPI is None or _WINDOWS_BUILD < 22000:
        return

    try:
        hwnd = int(cast(Any, window_id))
        corner_preference = ctypes.c_int(_WINDOW_CORNER_ROUND)
        _DWMAPI.DwmSetWindowAttribute(
            hwnd,
            _WINDOW_CORNER_ATTRIBUTE,
            ctypes.byref(corner_preference),
            4,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        log_warning(
            _LOGGER,
            "Failed to restore rounded acrylic window corners",
            window_id=repr(window_id),
            error=repr(error),
        )


def normalize_acrylic_frameless_chrome(window: Any) -> None:
    """Restore frameless acrylic chrome after the toolkit reapplies window chrome.

    On Qt 6.10+, ``AcrylicWindow`` switches to ``Qt.Window`` and its acrylic path
    reintroduces native caption visuals while the window is inactive or being
    captured. Reasserting ``Qt.FramelessWindowHint`` removes the ghost caption,
    and restoring the resize/minimize/maximize bits preserves the native behavior
    that qframelesswindow expects.
    """

    if _PLATFORM != "win32" or win32con is None or win32gui is None:
        return

    try:
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        hwnd = int(cast(Any, window.winId()))
        style = int(win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE))
        updated_style = style | int(win32con.WS_THICKFRAME)
        updated_style |= int(win32con.WS_MINIMIZEBOX)
        updated_style |= int(win32con.WS_MAXIMIZEBOX)
        updated_style &= ~int(win32con.WS_CAPTION)

        if updated_style != style:
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, updated_style)
        win32gui.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_FRAMECHANGED,
        )
        restore_rounded_window_corners(hwnd)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
        log_warning(
            _LOGGER,
            "Failed to normalize acrylic frameless chrome",
            window_id=repr(getattr(window, "winId", lambda: None)()),
            error=repr(error),
        )


def apply_acrylic_effect(window: Any) -> None:
    """Apply the configured acrylic blend and normalize frameless chrome."""

    window.windowEffect.setAcrylicEffect(window.winId(), ACRYLIC_BLEND_COLOR)
    normalize_acrylic_frameless_chrome(window)


__all__ = [
    "ACRYLIC_BLEND_COLOR",
    "ShellBackdropMode",
    "apply_acrylic_effect",
    "normalize_acrylic_frameless_chrome",
    "restore_rounded_window_corners",
]
