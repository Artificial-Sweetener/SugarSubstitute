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

"""Prove OpenGL surface promotion retains the shell's native DWM backdrop."""

from __future__ import annotations

from ctypes import WinDLL, byref, c_int, sizeof

from PySide6.QtCore import Qt
from PySide6.QtGui import QSurface
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication, QStackedWidget, QVBoxLayout, QWidget

from substitute.presentation.shell.window_effects import ShellBackdropMode
from substitute.presentation.shell.window_frame import SubstituteWindowFrame
from tests.support.qt.lifecycle import destroy_widget_roots
from tests.support.qt.semantic_wait import wait_for_qt_condition

_DWMWA_SYSTEMBACKDROP_TYPE = 38
_DWMSBT_MAINWINDOW = 2


def _system_backdrop_type(window: QWidget) -> int:
    """Read the native backdrop type attached to the window's current HWND."""

    value = c_int()
    result = WinDLL("dwmapi").DwmGetWindowAttribute(
        int(window.winId()),
        _DWMWA_SYSTEMBACKDROP_TYPE,
        byref(value),
        sizeof(value),
    )
    if result != 0:
        raise OSError(f"DwmGetWindowAttribute failed with HRESULT {result}")
    return value.value


def main() -> int:
    """Promote a live Mica shell to OpenGL and verify both presentation states."""

    application = QApplication([])
    frame = SubstituteWindowFrame(backdrop_mode=ShellBackdropMode.MICA)
    frame.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    stack = QStackedWidget(body)
    image_surface = QWidget(stack)
    stack.addWidget(image_surface)
    stack.setCurrentWidget(image_surface)
    body_layout.addWidget(stack)
    frame.add_body_widget(body)
    try:
        frame.resize(720, 480)
        frame.show()
        wait_for_qt_condition(
            lambda: _system_backdrop_type(frame) == _DWMSBT_MAINWINDOW,
            description="initial Mica backdrop",
        )
        raster_handle = int(frame.winId())

        video_surface = QOpenGLWidget(stack)
        stack.addWidget(video_surface)
        stack.setCurrentWidget(video_surface)
        wait_for_qt_condition(
            lambda: (
                video_surface.isValid()
                and frame.windowHandle().surfaceType()
                is QSurface.SurfaceType.OpenGLSurface
                and int(frame.winId()) != raster_handle
                and _system_backdrop_type(frame) == _DWMSBT_MAINWINDOW
            ),
            description="video OpenGL surface with restored Mica backdrop",
        )

        stack.setCurrentWidget(image_surface)
        application.processEvents()
        if _system_backdrop_type(frame) != _DWMSBT_MAINWINDOW:
            raise AssertionError("Image presentation lost the restored Mica backdrop")
        stack.setCurrentWidget(video_surface)
        application.processEvents()
        if _system_backdrop_type(frame) != _DWMSBT_MAINWINDOW:
            raise AssertionError("Video presentation lost the restored Mica backdrop")
        return 0
    finally:
        destroy_widget_roots((frame,))
        application.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
