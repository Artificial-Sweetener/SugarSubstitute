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

"""Verify native search-surface interaction while the picker is open."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.presentation.widgets.model_picker import ModelPickerField
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _FakeModelCatalog,
    _item,
)
from tests.presentation.widgets.model_picker.support import ensure_qapp
from tests.support.qt.lifecycle import destroy_qt_object


def test_model_picker_field_open_clicks_do_not_clear_search_text() -> None:
    """Keep one open picker and its search text when its surface is clicked."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = _open_field(host)
    field.open_picker()
    app.processEvents()
    popup = field._popup
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert popup is not None
    assert surface is not None

    QTest.keyClicks(surface, "alpha")
    app.processEvents()
    QTest.mouseClick(
        surface,
        Qt.MouseButton.LeftButton,
        pos=QPoint(surface.width() // 2, surface.height() // 2),
    )
    app.processEvents()

    assert field._popup is popup
    assert popup.isVisible() is True
    assert surface.isReadOnly() is False
    assert surface.text() == "alpha"
    destroy_qt_object(host)


def test_model_picker_field_mouse_drag_can_select_search_text() -> None:
    """Keep native drag selection inside the open editable search surface."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = _open_field(host)
    field.open_picker()
    app.processEvents()
    popup = field._popup
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    assert popup is not None
    assert surface is not None

    QTest.keyClicks(surface, "alpha")
    app.processEvents()
    y_position = surface.height() // 2
    QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=QPoint(12, y_position))
    QTest.mouseMove(surface, QPoint(surface.width() - 48, y_position))
    QTest.mouseRelease(
        surface,
        Qt.MouseButton.LeftButton,
        pos=QPoint(surface.width() - 48, y_position),
    )
    app.processEvents()

    assert field._popup is popup
    assert popup.isVisible() is True
    assert surface.text() == "alpha"
    assert surface.hasSelectedText() is True
    assert surface._should_paint_search_caret() is False
    destroy_qt_object(host)


def _open_field(host: QWidget) -> ModelPickerField:
    """Create one visible picker field with a deterministic catalog."""

    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha", None),)
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()
    return field
