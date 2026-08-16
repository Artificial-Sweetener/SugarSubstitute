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

"""Own native installer backdrop and frameless-window integration."""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import Any, cast

from PySide6.QtCore import Qt
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]


_LOGGER = logging.getLogger(__name__)

if sys.platform == "win32":
    import win32con  # type: ignore[import-untyped]
    import win32gui  # type: ignore[import-untyped]

    _DWMAPI: Any | None = ctypes.WinDLL("dwmapi")
    _WINDOW_CORNER_ATTRIBUTE = 33
    _WINDOW_CORNER_ROUND = 2
    _WINDOWS_BUILD = int(sys.getwindowsversion().build)
else:
    win32con = None
    win32gui = None
    _DWMAPI = None
    _WINDOW_CORNER_ATTRIBUTE = 0
    _WINDOW_CORNER_ROUND = 0
    _WINDOWS_BUILD = 0


def apply_launcher_window_effects(window: Any) -> None:
    """Apply the installer backdrop and normalize native window chrome."""

    try:
        window.windowEffect.setMicaEffect(
            window.winId(),
            isDarkMode=isDarkTheme(),
            isAlt=False,
        )
        _normalize_acrylic_frameless_chrome(window)
    except (AttributeError, RuntimeError, OSError) as error:
        _LOGGER.warning("Failed to apply launcher backdrop: %r", error)


def _restore_rounded_window_corners(window_id: object) -> None:
    """Request Windows 11 rounded corners for the launcher window."""

    if sys.platform != "win32" or _DWMAPI is None or _WINDOWS_BUILD < 22000:
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
    except Exception as error:
        _LOGGER.debug("Failed to restore launcher rounded corners: %r", error)


def _normalize_acrylic_frameless_chrome(window: Any) -> None:
    """Remove Qt native caption remnants while preserving resizing."""

    if sys.platform != "win32" or win32con is None or win32gui is None:
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
        _restore_rounded_window_corners(hwnd)
    except Exception as error:
        _LOGGER.debug("Failed to normalize launcher frameless chrome: %r", error)
