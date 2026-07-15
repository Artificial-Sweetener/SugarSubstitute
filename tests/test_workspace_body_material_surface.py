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

"""Contract tests for the workspace body material surface."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget
from pytest import MonkeyPatch

from substitute.presentation.shell.chrome_style import BODY_MATERIAL_SURFACE_OBJECT_NAME
import substitute.presentation.shell.workspace_body_material_surface as material_surface
from substitute.presentation.shell.workspace_body_material_surface import (
    WorkspaceBodyMaterialSurface,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _app() -> QApplication:
    """Return the QApplication required for material-surface widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_workspace_body_material_surface_initializes_material_contract() -> None:
    """The workspace material surface should expose the expected shell contract."""

    _app()
    surface = WorkspaceBodyMaterialSurface()

    assert surface.objectName() == BODY_MATERIAL_SURFACE_OBJECT_NAME
    assert surface.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert surface.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert surface.cube_stack_wash_opacity() == 1.0

    surface.close()


def test_workspace_body_material_surface_clamps_cube_stack_wash_opacity() -> None:
    """Cube-stack wash opacity should stay in the valid painter alpha range."""

    _app()
    surface = WorkspaceBodyMaterialSurface()

    surface.set_cube_stack_wash_opacity(-0.5)
    assert surface.cube_stack_wash_opacity() == 0.0

    surface.set_cube_stack_wash_opacity(1.5)
    assert surface.cube_stack_wash_opacity() == 1.0

    surface.close()


def test_workspace_body_material_surface_maps_cube_stack_region() -> None:
    """The registered cube-stack widget should define the faded material aperture."""

    _app()
    surface = WorkspaceBodyMaterialSurface()
    cube_stack = QWidget(surface)
    surface.resize(240, 180)
    cube_stack.setGeometry(0, 6, 58, 120)

    surface.set_cube_stack_region_widget(cube_stack)

    region = surface._cube_stack_region()
    assert region is not None
    assert region.getRect() == (0, 6, 58, 120)

    surface.set_cube_stack_region_widget(None)
    assert surface._cube_stack_region() is None

    surface.close()


def test_workspace_body_material_surface_owns_body_wash_paint_token() -> None:
    """The custom painter should use the shared body wash token directly."""

    source = (
        REPO_ROOT
        / "substitute"
        / "presentation"
        / "shell"
        / "workspace_body_material_surface.py"
    ).read_text(encoding="utf-8")

    assert "body_material_wash_color(self._backdrop_mode)" in source
    assert "body_material_wash_style" not in source


def test_workspace_body_material_surface_fades_only_cube_stack_region(
    monkeypatch: MonkeyPatch,
) -> None:
    """Rendering should dissolve the cube-stack wash without fading the editor body."""

    _app()
    monkeypatch.setattr(
        material_surface,
        "body_material_wash_color",
        lambda _backdrop_mode=None: (10, 20, 30, 200),
    )
    surface = WorkspaceBodyMaterialSurface()
    cube_stack = QWidget(surface)
    cube_stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    cube_stack.setStyleSheet("background: transparent;")
    surface.resize(120, 80)
    cube_stack.setGeometry(0, 0, 40, 80)
    surface.set_cube_stack_region_widget(cube_stack)

    surface.set_cube_stack_wash_opacity(0.0)
    compact_image = _render_surface(surface)

    surface.set_cube_stack_wash_opacity(1.0)
    expanded_image = _render_surface(surface)

    assert compact_image.pixelColor(20, 20).alpha() == 0
    assert compact_image.pixelColor(80, 20).alpha() == 200
    assert expanded_image.pixelColor(20, 20).alpha() == 200
    assert expanded_image.pixelColor(80, 20).alpha() == 200

    surface.close()


def _render_surface(surface: WorkspaceBodyMaterialSurface) -> QImage:
    """Render the material surface into a transparent image for pixel checks."""

    image = QImage(surface.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    surface.render(painter, QPoint(0, 0))
    painter.end()
    return image
