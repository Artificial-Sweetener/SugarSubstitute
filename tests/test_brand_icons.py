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

"""Contract tests for third-party brand icons used in the UI."""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from substitute.presentation.resources.brand_icons import qt_logo_icon_path


def test_qt_logo_icon_path_points_to_loadable_asset() -> None:
    """The PySide6 About link should use a loadable vendored Qt logo asset."""

    _app()
    icon_path = qt_logo_icon_path()
    icon = QIcon(str(icon_path))

    assert icon_path.name == "QtLogoNeon.png"
    assert icon_path.is_file()
    assert not icon.isNull()


def _app() -> QApplication:
    """Return the active QApplication or create one for icon loading checks."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
