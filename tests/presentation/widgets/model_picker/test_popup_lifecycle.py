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

"""Verify model picker popup lifecycle contracts."""

from __future__ import annotations


from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import EditableComboBox  # type: ignore[import-untyped]

from substitute.presentation.widgets.model_picker import (
    ModelPickerField,
    ModelPickerPopupPlacementMode,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    _ModelPickerComboSurface,
)
from substitute.presentation.widgets.text_caret import TEXT_CARET_WIDTH
from tests.support.qt.lifecycle import destroy_qt_object
from tests.support.qt.semantic_wait import wait_for_qt_condition


from tests.presentation.widgets.model_picker.catalog_fixtures import (
    _FakeModelCatalog,
    _FailingRefreshChoiceSource,
    _item,
)
from tests.presentation.widgets.model_picker.support import (
    _exclusive_bottom,
    _open_picker_surface,
    _screen_available_geometry,
    ensure_qapp,
)


def test_model_picker_field_popup_activation_emits_backend_value() -> None:
    """Activating a popup item should select its backend value and close the popup."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    catalog = _FakeModelCatalog(
        (
            _item("models/alpha.safetensors", "Alpha", None),
            _item("models/beta.safetensors", "Beta", None),
        )
    )
    field = ModelPickerField(
        host,
        choice_source=catalog,
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.show()
    changed: list[str] = []
    field.currentTextChanged.connect(changed.append)

    field.open_picker()
    app.processEvents()
    assert field._popup is not None
    field._popup._view.move_current_right()
    assert field._popup._view.activate_current() is True
    app.processEvents()

    assert field.currentText() == "models/beta.safetensors"
    assert changed == ["models/beta.safetensors"]
    assert field._popup.isVisible() is False
    assert catalog.refresh_calls == ["checkpoints"]
    destroy_qt_object(host)


def test_model_picker_field_refresh_failure_opens_empty_without_clearing_value() -> (
    None
):
    """Backend refresh failure should not show stale choices or erase field values."""

    ensure_qapp()
    source = _FailingRefreshChoiceSource(
        (_item("models/alpha.safetensors", "Alpha", None),)
    )
    field = ModelPickerField(
        choice_source=source,
        current_value="models/alpha.safetensors",
    )
    field.resize(320, field.sizeHint().height())
    field.show()

    field.open_picker()
    wait_for_qt_condition(field._surface.search_focus_active)

    assert source.refresh_calls == 1
    assert field.currentText() == "models/alpha.safetensors"
    assert field._popup is not None
    assert field._popup._view.items() == ()
    field._dismiss_popup()
    assert field.displayText() == "alpha"
    destroy_qt_object(field)


def test_model_picker_field_popup_search_filters_without_changing_value() -> None:
    """Typing in the field search should filter without selecting a backend value."""

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

    field.open_picker()
    app.processEvents()
    assert field._popup is not None
    surface = field.findChild(EditableComboBox, "modelPickerComboSurface")
    assert surface is not None

    QTest.keyClicks(surface, "beta")
    app.processEvents()

    assert [item.title for item in field._popup._view.items()] == ["Beta"]
    assert field.currentText() == "models/alpha.safetensors"
    assert field.displayText() == "beta"

    QTest.keyClick(surface, Qt.Key.Key_Escape)
    app.processEvents()

    assert field._popup.isVisible() is False
    assert field.currentText() == "models/alpha.safetensors"
    assert field.displayText() == "Alpha"
    destroy_qt_object(host)


def test_model_picker_field_opens_above_when_below_would_cover_field() -> None:
    """Low fields should open above instead of clamping the popup over the field."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 220)
    screen = _screen_available_geometry()
    host.move(screen.left() + 40, screen.top() + max(0, screen.height() - 230))
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/alpha.safetensors", "Alpha", None),)
        ),
        current_value="models/alpha.safetensors",
    )
    field.resize(220, 34)
    field.move(100, host.height() - 40)
    field.show()

    field.open_picker()
    app.processEvents()

    popup = field._popup
    assert popup is not None
    field_top = field.mapToGlobal(QPoint(0, 0)).y()
    field_bottom = field_top + field.height()
    popup_geometry = popup.geometry()

    assert popup.isVisible() is True
    assert popup._placement_mode is ModelPickerPopupPlacementMode.ABOVE
    assert _exclusive_bottom(popup_geometry) <= field_top
    assert not (
        popup_geometry.top() < field_bottom
        and _exclusive_bottom(popup_geometry) > field_top
    )
    destroy_qt_object(host)


def test_model_picker_field_open_search_shows_text_caret() -> None:
    """Opening the picker should show a caret that follows native cursor geometry."""

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

    assert surface.search_focus_active() is True
    assert surface.isReadOnly() is False
    assert surface.cursor().shape() == Qt.CursorShape.IBeamCursor
    assert surface.cursorRect().height() > 0
    assert surface.cursorPosition() == 0
    assert surface._should_paint_search_caret() is True
    assert surface._current_search_caret_rect().width() == TEXT_CARET_WIDTH

    initial_cursor_left = surface._current_search_caret_rect().left()
    QTest.keyClicks(surface, "be")
    app.processEvents()

    assert surface.text() == "be"
    assert surface.cursorPosition() == 2
    assert surface._should_paint_search_caret() is True
    assert surface._current_search_caret_rect().left() > initial_cursor_left
    destroy_qt_object(host)


def test_model_picker_field_screen_popup_survives_search_focus_transfer() -> None:
    """Opening a screen popup should keep combo-surface search focus usable."""

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
    surface = field.findChild(_ModelPickerComboSurface, "modelPickerComboSurface")
    popup = field._popup
    assert surface is not None
    assert popup is not None

    assert popup.isVisible() is True
    assert surface.search_focus_active() is True

    QTest.keyClicks(surface, "beta")
    app.processEvents()

    assert popup.isVisible() is True
    assert [item.title for item in popup._view.items()] == ["Beta"]
    assert field.currentText() == "models/alpha.safetensors"
    assert changed == []
    destroy_qt_object(host)


def test_model_picker_field_click_opens_attached_popup() -> None:
    """Clicking the closed field should reveal the attached model picker popup."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    field = ModelPickerField(
        host,
        choice_source=_FakeModelCatalog(
            (_item("models/base.safetensors", "Base", None),)
        ),
        current_value="models/base.safetensors",
    )
    field.resize(220, 34)
    field.show()

    surface = field.findChild(EditableComboBox, "modelPickerComboSurface")
    assert surface is not None

    QTest.mouseClick(surface, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
    app.processEvents()

    assert field._popup is not None
    assert field._popup.isVisible() is True
    destroy_qt_object(host)


def test_model_picker_field_chevron_click_closes_open_popup() -> None:
    """Clicking the drop chevron again should close the open picker popup."""

    app = ensure_qapp()
    host, field, surface = _open_picker_surface(
        (_item("models/base.safetensors", "Civit Base", "v2.0"),),
        current_value="models/base.safetensors",
    )
    popup = field._popup
    assert popup is not None
    assert popup.isVisible() is True

    QTest.mouseClick(surface.dropButton, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert popup.isVisible() is False
    assert field._popup is popup
    assert surface.isReadOnly() is True
    assert field.displayText() == "Civit Base - v2.0"
    destroy_qt_object(host)
