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

"""Prove native OpenGL composition cannot tint neighboring application panels."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

from substitute.presentation.canvas.output.video_opengl_surface import (
    VideoOpenGLSurface,
)
from tests.support.qt.lifecycle import destroy_widget_roots
from tests.support.qt.semantic_wait import wait_for_qt_condition


def _solid_panel(color: QColor) -> QWidget:
    """Create one opaque sibling panel with an exact diagnostic color."""

    panel = QWidget()
    palette = panel.palette()
    palette.setColor(QPalette.ColorRole.Window, color)
    panel.setPalette(palette)
    panel.setAutoFillBackground(True)
    return panel


def main() -> int:
    """Render Cube, editor, and video siblings and verify pixel containment."""

    application = QApplication([])
    cube_color = QColor(31, 67, 103)
    editor_color = QColor(109, 71, 37)
    root = QWidget()
    root.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    layout = QHBoxLayout(root)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    cube = _solid_panel(cube_color)
    editor = _solid_panel(editor_color)
    video = VideoOpenGLSurface()
    layout.addWidget(cube)
    layout.addWidget(editor)
    layout.addWidget(video)
    layout.setStretch(0, 1)
    layout.setStretch(1, 1)
    layout.setStretch(2, 1)
    try:
        root.resize(600, 300)
        root.show()
        wait_for_qt_condition(
            lambda: video.rendering_ready,
            description="clipped OpenGL surface",
        )
        video.update()
        application.processEvents()
        image = root.grab().toImage()
        samples = {
            "cube": image.pixelColor(100, 150),
            "editor": image.pixelColor(300, 150),
        }
        expected = {"cube": cube_color, "editor": editor_color}
        failures = {
            name: (sample.name(), expected[name].name())
            for name, sample in samples.items()
            if sample != expected[name]
        }
        if failures:
            raise AssertionError(
                f"OpenGL surface escaped its canvas region: {failures}"
            )
        return 0
    finally:
        destroy_widget_roots((root,))
        application.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
