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

"""Verify clipped video composition and cross-window GL rehosting."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from substitute.presentation.canvas.output.video_opengl_surface import (
    VideoOpenGLSurface,
    video_canvas_material_color,
)
from tests.support.qt.lifecycle import ensure_qt_application


def test_video_surface_is_opaque_and_clipped_to_its_canvas_region() -> None:
    """The OpenGL surface must not wash sibling editor or Cube regions."""

    ensure_qt_application()
    surface = VideoOpenGLSurface()
    try:
        assert surface.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        assert not surface.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    finally:
        surface.close()


def test_video_surface_clears_every_frame_with_canvas_material() -> None:
    """Untouched letterbox pixels must receive the Output material color."""

    ensure_qt_application()
    clears: list[QColor] = []
    surface = VideoOpenGLSurface(clear_framebuffer=clears.append)
    try:
        surface.paintGL()
        surface.paintGL()

        expected = video_canvas_material_color(surface)
        assert clears == [expected, expected]
        assert expected.alpha() == 255
        assert expected != QColor(Qt.GlobalColor.black)
    finally:
        surface.close()


@pytest.mark.platforms("windows")
def test_video_surface_does_not_wash_neighboring_application_panels() -> None:
    """Native GL composition must preserve Cube and editor sibling pixels."""

    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
    environment["QT_OPENGL"] = "software"
    result = subprocess.run(
        [sys.executable, "-m", "tests.support.video_opengl_clipping_probe"],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.platforms("windows")
def test_video_renderer_recovers_after_floating_and_redocked_rehosting() -> None:
    """Each top-level context should receive a live renderer for the same player."""

    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
    environment["QT_OPENGL"] = "software"
    result = subprocess.run(
        [sys.executable, "-m", "tests.support.video_opengl_rehosting_probe"],
        cwd=Path.cwd(),
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
