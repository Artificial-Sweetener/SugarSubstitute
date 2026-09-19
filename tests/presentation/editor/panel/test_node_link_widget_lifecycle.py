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

"""Verify node-link selector cleanup tolerates platform-owned Qt teardown."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import delete, isValid

from substitute.presentation.editor.panel.node_link_widget_controller import (
    NodeLinkWidgetController,
)


def test_delete_widget_tolerates_already_deleted_qt_selector(
    qt_application_owner: QApplication,
) -> None:
    """Cancelled projection cleanup must ignore a selector Qt already deleted."""

    del qt_application_owner
    selector = QWidget()
    delete(selector)
    assert not isValid(selector)

    NodeLinkWidgetController._delete_widget(selector)
