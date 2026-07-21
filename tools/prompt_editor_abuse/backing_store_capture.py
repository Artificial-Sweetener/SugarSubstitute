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

"""Capture actual prompt-editor backing-store frames without forced rendering."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QApplication, QWidget


def capture_editor_backing_store(
    editor: object,
    *,
    event_cycles: int = 1,
) -> QImage | None:
    """Return pixels users receive after bounded queued production painting."""

    for _cycle in range(max(0, event_cycles)):
        QApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.UpdateRequest)
    prompt_editor = cast(Any, editor)
    window = cast(QWidget, prompt_editor.window())
    screen = window.screen() or QGuiApplication.primaryScreen()
    if screen is None:
        return None
    editor_origin = prompt_editor.mapTo(window, QPoint())
    pixmap = screen.grabWindow(
        int(window.winId()),
        editor_origin.x(),
        editor_origin.y(),
        max(1, int(prompt_editor.width())),
        max(1, int(prompt_editor.height())),
    )
    if pixmap.isNull():
        return None
    image = pixmap.toImage()
    expected_size = prompt_editor.size()
    if image.size() != expected_size:
        image = image.scaled(
            expected_size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return image


__all__ = ["capture_editor_backing_store"]
