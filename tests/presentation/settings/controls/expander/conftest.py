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

"""Own native widget lifetime for Settings expander tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QAbstractAnimation, QTimer
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from tests.support.qt.lifecycle import destroy_widget_roots


@pytest.fixture
def owned_widgets() -> Iterator[list[QWidget]]:
    """Synchronously destroy every widget registered by the current test."""

    widgets: list[QWidget] = []
    yield widgets
    for widget in reversed(widgets):
        if isValid(widget):
            for animation in widget.findChildren(QAbstractAnimation):
                animation.stop()
            for timer in widget.findChildren(QTimer):
                timer.stop()
    destroy_widget_roots(widgets)
    widgets.clear()
