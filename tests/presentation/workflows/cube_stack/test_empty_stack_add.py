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

"""Keep the Add Cube affordance available after the final Cube closes."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.presentation.workflows.cube_stack_view import CubeStack
from tests.support.qt.lifecycle import destroy_qt_object


def test_closing_every_cube_preserves_visible_usable_add_card(
    qt_application_owner: QApplication,
) -> None:
    """Keep the empty workflow capable of opening the Cube picker."""

    stack = CubeStack()
    try:
        stack.addTab("first", "First")
        stack.addTab("second", "Second")
        stack.cubeCloseRequested.connect(stack.removeTab)
        add_requests: list[bool] = []
        stack.cubeAddRequested.connect(lambda: add_requests.append(True))
        stack.show()
        qt_application_owner.processEvents()

        for _ in range(2):
            QTest.mouseClick(stack.tabItem(0).closeButton, Qt.MouseButton.LeftButton)
            qt_application_owner.processEvents()

        add_card = stack.addPlaceholder
        assert stack.count() == 0
        assert add_card.isVisibleTo(stack)
        assert (
            stack.viewport()
            .rect()
            .contains(add_card.mapTo(stack.viewport(), add_card.rect().center()))
        )

        QTest.mouseClick(add_card, Qt.MouseButton.LeftButton)
        assert add_requests == [True]
    finally:
        stack.close()
        destroy_qt_object(cast(QObject, stack))
