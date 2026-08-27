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

"""Verify model picker search interaction contracts."""

from __future__ import annotations


from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import EditableComboBox, Theme  # type: ignore[import-untyped]

from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from substitute.presentation.widgets.text_caret import TEXT_CARET_WIDTH
from tests.support.qt.lifecycle import destroy_qt_object
from tests.presentation.theme.support import fluent_theme


from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _FakeModelCatalog,
    _item,
)
from tests.presentation.widgets.model_picker.support import (
    _open_picker_surface_by_click,
    _visible_model_picker_titles,
    ensure_qapp,
)


def test_model_picker_field_typing_still_filters_after_wall_focus() -> None:
    """Typing should keep using the field search after the wall receives focus."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface_by_click(
        (
            _item("models/alpha.safetensors", "Alpha", None),
            _item("models/beta.safetensors", "Beta", None),
        ),
        current_value="models/alpha.safetensors",
    )
    popup = field._popup
    assert popup is not None
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)
    app.processEvents()

    assert QApplication.focusWidget() is surface

    QTest.mouseClick(popup._view, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    focus_widget = QApplication.focusWidget()
    assert focus_widget is not None
    QTest.keyClicks(focus_widget, "be")
    app.processEvents()

    assert QApplication.focusWidget() is surface
    assert surface.text() == "be"
    assert _visible_model_picker_titles(field) == ["Beta"]
    assert field.currentText() == "models/alpha.safetensors"
    assert changed == []
    destroy_qt_object(host)


def test_model_picker_field_typing_still_filters_after_route_focus() -> None:
    """Typing should keep using the field search after route controls take focus."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface_by_click(
        (
            _item("models/alpha.safetensors", "Alpha", None),
            _item("models/beta.safetensors", "Beta", None),
        ),
        current_value="models/alpha.safetensors",
    )
    popup = field._popup
    assert popup is not None
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)
    app.processEvents()

    assert QApplication.focusWidget() is surface
    route_buttons = popup._route_bar.child_route_buttons()
    assert route_buttons

    QTest.mouseClick(route_buttons[0], Qt.MouseButton.LeftButton)
    focus_widget = QApplication.focusWidget()
    assert focus_widget is not None
    QTest.keyClicks(focus_widget, "be")
    app.processEvents()

    assert surface.text() == "be"
    assert _visible_model_picker_titles(field) == ["Beta"]
    assert field.currentText() == "models/alpha.safetensors"
    assert changed == []
    destroy_qt_object(host)


def test_model_picker_field_route_click_survives_delayed_release() -> None:
    """Route clicks should complete even when the event loop runs before release."""

    app = ensure_qapp()
    host, field, _surface = _open_picker_surface_by_click(
        (
            _item("illustrious/alpha.safetensors", "Alpha", None, folder="illustrious"),
            _item("realistic/beta.safetensors", "Beta", None, folder="realistic"),
        ),
        current_value="illustrious/alpha.safetensors",
    )
    popup = field._popup
    assert popup is not None
    route_buttons = popup._route_bar.child_route_buttons()
    target_button = next(
        button for button in route_buttons if button.text() == "realistic (1)"
    )

    QTest.mousePress(target_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    QTest.mouseRelease(target_button, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert popup._route_bar.current_route() == ("realistic",)
    assert _visible_model_picker_titles(field) == ["Beta"]
    destroy_qt_object(host)


def test_model_picker_field_click_enters_native_text_editing() -> None:
    """Mouse opening should still let the native line edit initialize caret state."""

    with fluent_theme(Theme.DARK):
        app = ensure_qapp()
        host = QWidget()
        host.resize(640, 480)
        host.show()
        field = ModelPickerField(
            host,
            choice_source=_FakeModelCatalog(
                (_item("models/alpha.safetensors", "Alpha", None),)
            ),
            current_value="models/alpha.safetensors",
        )
        field.resize(220, 34)
        field.show()
        surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
        assert surface is not None

        QTest.mouseClick(surface, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
        app.processEvents()

        assert surface.search_focus_active() is True
        assert surface.isReadOnly() is False
        assert surface.cursor().shape() == Qt.CursorShape.IBeamCursor
        assert surface.palette().text().color().name() == "#ffffff"
        assert surface._should_paint_search_caret() is True

        initial_caret_left = surface._current_search_caret_rect().left()
        QTest.keyClicks(surface, "al")
        app.processEvents()

        assert surface.text() == "al"
        assert surface.cursorPosition() == 2
        assert surface._current_search_caret_rect().left() > initial_caret_left
        destroy_qt_object(host)


def test_model_picker_field_search_caret_renders_on_surface() -> None:
    """The search caret should paint visibly over the editable combo surface."""

    with fluent_theme(Theme.DARK):
        app = ensure_qapp()
        host = QWidget()
        host.resize(640, 480)
        host.show()
        field = ModelPickerField(
            host,
            choice_source=_FakeModelCatalog(
                (_item("models/alpha.safetensors", "Alpha", None),)
            ),
            current_value="models/alpha.safetensors",
        )
        field.resize(220, 34)
        field.show()

        field.open_picker()
        app.processEvents()
        surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
        assert surface is not None

        surface._show_search_caret()
        image = QImage(surface.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        surface.render(image)

        caret_rect = surface._current_search_caret_rect()
        assert caret_rect.width() == TEXT_CARET_WIDTH
        line_x = int(round(caret_rect.center().x()))
        painted_pixels = [
            image.pixelColor(line_x, y)
            for y in range(int(caret_rect.top()) + 2, int(caret_rect.bottom()) - 2)
        ]

        assert any(
            pixel.red() > 230
            and pixel.green() > 230
            and pixel.blue() > 230
            and pixel.alpha() > 180
            for pixel in painted_pixels
        )
        destroy_qt_object(host)


def test_model_picker_field_typing_does_not_emit_backend_value_signal() -> None:
    """Search text is transient UI state and must not write through widget wiring."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (
                _item("models/alpha.safetensors", "Alpha", None),
                _item("models/beta.safetensors", "Beta", None),
            )
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    field.open_picker()
    app.processEvents()
    surface = field.findChild(EditableComboBox, "modelPickerComboSurface")
    assert surface is not None

    QTest.keyClicks(surface, "beta")
    app.processEvents()

    assert changed == []
    assert field.currentText() == "models/alpha.safetensors"
    destroy_qt_object(host)
