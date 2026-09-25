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

"""Drive and capture hidden Qt video qualification surfaces on Windows."""

from __future__ import annotations

from collections.abc import Callable
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QSlider, QWidget

from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas
from substitute.presentation.widgets.anchored_row_picker import AnchoredRowPickerView

_TIMEOUT_SECONDS = 10.0


def find_button(parent: QWidget, accessible_name: str) -> QPushButton:
    """Find one public accessibility-labeled playback control."""

    for button in parent.findChildren(QPushButton):
        if button.accessibleName() == accessible_name:
            return button
    raise RuntimeError(f"Playback control is unavailable: {accessible_name}")


def find_slider(parent: QWidget, accessible_name: str) -> QSlider:
    """Find one public accessibility-labeled playback slider."""

    for slider in parent.findChildren(QSlider):
        if slider.accessibleName() == accessible_name:
            return slider
    raise RuntimeError(f"Playback slider is unavailable: {accessible_name}")


def open_source_picker(
    canvas: OutputCanvas,
    window: QWidget,
    application: QApplication,
) -> tuple[QWidget, AnchoredRowPickerView]:
    """Open the real compact source picker through native Windows input."""

    native_click(window, canvas.source_selector_button, application)
    wait_until(
        application,
        canvas._source_picker.is_visible,
        label="compact source picker",
    )
    picker_owner = getattr(canvas._source_picker, "_picker", None)
    popup = getattr(picker_owner, "_flyout", None)
    if not isinstance(popup, QWidget):
        raise RuntimeError("Compact source picker did not create its flyout.")
    view = popup.findChild(AnchoredRowPickerView)
    if view is None:
        raise RuntimeError("Compact source picker did not create its row view.")
    return popup, view


def native_click(
    window: QWidget,
    target: QWidget,
    application: QApplication,
) -> None:
    """Route one Windows left click from top-level coordinates to Qt hit-testing."""

    point = target.mapTo(window, target.rect().center())
    send_mouse_message(window, 0x0200, 0, point.x(), point.y())
    send_mouse_message(window, 0x0201, 0x0001, point.x(), point.y())
    send_mouse_message(window, 0x0202, 0, point.x(), point.y())
    pump_events(application, 0.08)


def native_click_fraction(
    window: QWidget,
    target: QWidget,
    fraction: float,
    application: QApplication,
) -> None:
    """Click a horizontal control at one normalized position via native routing."""

    bounded = min(max(fraction, 0.0), 1.0)
    local_x = round((target.width() - 1) * bounded)
    point = target.mapTo(window, QPoint(local_x, target.height() // 2))
    send_mouse_message(window, 0x0200, 0, point.x(), point.y())
    send_mouse_message(window, 0x0201, 0x0001, point.x(), point.y())
    send_mouse_message(window, 0x0202, 0, point.x(), point.y())
    pump_events(application, 0.08)


def native_click_vertical_fraction(
    window: QWidget,
    target: QWidget,
    fraction: float,
    application: QApplication,
) -> None:
    """Click a vertical control at one normalized top-origin position."""

    bounded = min(max(fraction, 0.0), 1.0)
    local_y = round((target.height() - 1) * bounded)
    point = target.mapTo(window, QPoint(target.width() // 2, local_y))
    send_mouse_message(window, 0x0200, 0, point.x(), point.y())
    send_mouse_message(window, 0x0201, 0x0001, point.x(), point.y())
    send_mouse_message(window, 0x0202, 0, point.x(), point.y())
    pump_events(application, 0.08)


def native_wheel(
    window: QWidget,
    target: QWidget,
    delta: int,
    application: QApplication,
    *,
    horizontal_fraction: float = 0.5,
    vertical_fraction: float = 0.5,
    shift: bool = False,
) -> None:
    """Route one Win32 wheel gesture through the top-level platform window."""

    local = QPoint(
        round((target.width() - 1) * horizontal_fraction),
        round((target.height() - 1) * vertical_fraction),
    )
    client = target.mapTo(window, local)
    screen = window.mapToGlobal(client)
    root_handle = int(window.winId())
    scale = window.devicePixelRatioF()
    send_message = ctypes.windll.user32.SendMessageW
    send_message.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    send_message.restype = wintypes.LPARAM
    wheel_state = (delta & 0xFFFF) << 16 | (0x0004 if shift else 0)
    physical_x = round(screen.x() * scale)
    physical_y = round(screen.y() * scale)
    screen_point = (physical_y & 0xFFFF) << 16 | (physical_x & 0xFFFF)
    send_message(root_handle, 0x020A, wheel_state, screen_point)
    pump_events(application, 0.08)


def pointer_move(
    window: QWidget,
    target: QWidget,
    application: QApplication,
) -> None:
    """Route pointer motion through Qt's top-level window-system event path."""

    handle = window.windowHandle()
    if handle is None:
        raise RuntimeError("Qualification window has no native window handle.")
    point = target.mapTo(window, target.rect().center())
    QTest.mouseMove(handle, point)
    pump_events(application, 0.08)


def send_mouse_message(
    window: QWidget,
    message: int,
    key_state: int,
    x: int,
    y: int,
) -> None:
    """Send one Win32 client mouse message to Qt's real platform event bridge."""

    if sys.platform != "win32":
        raise RuntimeError("Native pointer qualification currently requires Windows.")
    root_handle = int(window.winId())
    scale = window.devicePixelRatioF()
    target_handle, target_point = deepest_native_child(
        root_handle,
        round(x * scale),
        round(y * scale),
    )
    packed = (target_point.y & 0xFFFF) << 16 | (target_point.x & 0xFFFF)
    send_message = ctypes.windll.user32.SendMessageW
    send_message.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    send_message.restype = wintypes.LPARAM
    result = send_message(
        target_handle,
        wintypes.UINT(message),
        wintypes.WPARAM(key_state),
        wintypes.LPARAM(packed),
    )
    del result


def deepest_native_child(
    root_handle: int,
    x: int,
    y: int,
) -> tuple[int, wintypes.POINT]:
    """Resolve the deepest visible native child at one root-client coordinate."""

    user32 = ctypes.windll.user32
    child_from_point = user32.ChildWindowFromPointEx
    child_from_point.argtypes = (
        wintypes.HWND,
        wintypes.POINT,
        wintypes.UINT,
    )
    child_from_point.restype = wintypes.HWND
    map_points = user32.MapWindowPoints
    map_points.argtypes = (
        wintypes.HWND,
        wintypes.HWND,
        ctypes.POINTER(wintypes.POINT),
        wintypes.UINT,
    )
    map_points.restype = ctypes.c_int
    handle = root_handle
    point = wintypes.POINT(x, y)
    flags = 0x0001 | 0x0002 | 0x0004
    while True:
        child = child_from_point(handle, point, flags)
        if not child or child == handle:
            return handle, point
        next_point = wintypes.POINT(point.x, point.y)
        map_points(handle, child, ctypes.byref(next_point), 1)
        handle = int(child)
        point = next_point


def capture(widget: QWidget, path: Path) -> None:
    """Capture the exact Qt-composited qualification target off screen."""

    pixmap = widget.grab()
    if pixmap.isNull() or not pixmap.save(str(path)):
        raise RuntimeError(f"Could not capture rendered output: {path.name}")


def render_capture(widget: QWidget, path: Path) -> None:
    """Force an exact QWidget render when hidden backing-store grabs stay stale."""

    ratio = widget.devicePixelRatioF()
    image = QImage(
        max(1, round(widget.width() * ratio)),
        max(1, round(widget.height() * ratio)),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    widget.render(painter, QPoint())
    painter.end()
    if not image.save(str(path)):
        raise RuntimeError(f"Could not save rendered output: {path.name}")


def capture_with_popup(window: QWidget, popup: QWidget, path: Path) -> None:
    """Capture one exact Qt window and its independently hosted picker flyout."""

    window_pixmap = window.grab()
    popup_pixmap = popup.grab()
    if window_pixmap.isNull() or popup_pixmap.isNull():
        raise RuntimeError("Could not capture Output navigation picker evidence.")
    window_rect = QRect(window.mapToGlobal(QPoint()), window.size())
    popup_rect = QRect(popup.mapToGlobal(QPoint()), popup.size())
    union = window_rect.united(popup_rect)
    ratio = window.devicePixelRatioF()
    composite = QPixmap(
        max(1, round(union.width() * ratio)),
        max(1, round(union.height() * ratio)),
    )
    composite.setDevicePixelRatio(ratio)
    composite.fill(Qt.GlobalColor.transparent)
    painter = QPainter(composite)
    painter.drawPixmap(window_rect.topLeft() - union.topLeft(), window_pixmap)
    painter.drawPixmap(popup_rect.topLeft() - union.topLeft(), popup_pixmap)
    painter.end()
    if not composite.save(str(path)):
        raise RuntimeError(f"Could not save picker evidence: {path.name}")


def images_differ(first: Path, second: Path) -> bool:
    """Return whether two rendered PNGs contain different pixels."""

    first_image = QImage(str(first))
    second_image = QImage(str(second))
    if first_image.isNull() or second_image.isNull():
        raise RuntimeError("Could not load rendered qualification evidence.")
    return first_image != second_image


def native_target_is_root(window: QWidget, target: QWidget) -> bool:
    """Return whether no native child window occludes one Qt control coordinate."""

    point = target.mapTo(window, target.rect().center())
    root_handle = int(window.winId())
    scale = window.devicePixelRatioF()
    target_handle, _native_point = deepest_native_child(
        root_handle,
        round(point.x() * scale),
        round(point.y() * scale),
    )
    return target_handle == root_handle


def wait_until(
    application: QApplication,
    predicate: Callable[[], bool],
    *,
    label: str,
) -> None:
    """Wait for one Qt/native state transition with a bounded timeout."""

    deadline = time.monotonic() + _TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        application.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise TimeoutError(f"Timed out waiting for {label}.")


def pump_events(application: QApplication, seconds: float) -> None:
    """Keep the Qt/native event queues moving for one bounded render interval."""

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.01)


__all__ = [
    "capture",
    "capture_with_popup",
    "find_button",
    "find_slider",
    "images_differ",
    "native_click",
    "native_click_fraction",
    "native_click_vertical_fraction",
    "native_target_is_root",
    "native_wheel",
    "open_source_picker",
    "pointer_move",
    "pump_events",
    "render_capture",
    "wait_until",
]
