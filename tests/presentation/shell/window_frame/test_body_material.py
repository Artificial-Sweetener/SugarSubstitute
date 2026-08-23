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

"""Test shell frame body-material composition."""

from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtWidgets import QApplication, QWidget
import pytest

from substitute.presentation.shell.chrome_style import (
    BODY_MATERIAL_SURFACE_OBJECT_NAME,
    body_material_wash_rgba,
    workflow_chrome_wash_rgba,
)
from substitute.presentation.shell.window_frame import (
    ShellBackdropMode,
    SubstituteWindowFrame,
)
from tests.support.qt.lifecycle import ensure_qt_application


@pytest.fixture(scope="module", autouse=True)
def body_material_qt_application() -> Iterator[QApplication]:
    """Keep one worker-local Qt application alive for body-material tests."""

    application = ensure_qt_application()
    yield application


def _app() -> QApplication:
    """Return the shared QApplication used by frameless-window contract tests."""

    return ensure_qt_application()


def test_shell_frame_body_material_surface_owns_main_body_wash() -> None:
    """The optional body material surface should wrap body content below titlebar."""

    _app()
    frame = SubstituteWindowFrame(
        backdrop_mode=ShellBackdropMode.MICA_ALT,
        create_body_material_surface=True,
    )
    body_widget = QWidget()

    frame.add_body_widget(body_widget)

    assert frame.layout() is not None
    assert frame.layout().contentsMargins().top() == frame.titleBar.height()
    assert frame.bodyMaterialSurface is not None
    assert frame.bodyMaterialLayout is not None
    assert frame.bodyMaterialSurface.objectName() == BODY_MATERIAL_SURFACE_OBJECT_NAME
    assert body_material_wash_rgba() in frame.bodyMaterialSurface.styleSheet()
    assert workflow_chrome_wash_rgba().startswith("rgba(")
    assert body_widget.parent() is frame.bodyMaterialSurface
    assert frame.titleBar.parent() is frame

    frame.close()
