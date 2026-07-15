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

"""Present blocking startup failure reports before the shell exists."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.errors import ErrorReport
from substitute.presentation.errors.error_presenter import ErrorPresenter


def present_startup_failure_report(report: ErrorReport) -> None:
    """Show one blocking startup failure report in a temporary host widget."""

    host = QWidget()
    host.setWindowTitle("ComfyUI startup failed")
    host.setWindowFlag(Qt.WindowType.Tool, True)
    host.resize(1024, 768)
    screen = QApplication.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        host.move(
            geometry.left() + (geometry.width() - host.width()) // 2,
            geometry.top() + (geometry.height() - host.height()) // 2,
        )
    host.show()
    try:
        ErrorPresenter(parent=host).show_error_report(report)
    finally:
        host.close()
        host.deleteLater()


__all__ = ["present_startup_failure_report"]
