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

"""Verify model picker popup filtering contracts."""

from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import SearchLineEdit  # type: ignore[import-untyped]

from substitute.presentation.widgets.folder_route import FolderRouteBar
from substitute.presentation.widgets.model_picker import (
    ModelPickerItem,
    ModelPickerPopup,
)
from tests.support.qt.lifecycle import destroy_qt_object


from tests.presentation.widgets.model_picker.popup_fixtures import (
    _CountingAssetRepository,
    ensure_qapp,
    _item,
    _click_route_button,
    _top_screen_anchor_rect,
)


def test_model_picker_filter_rebuilds_wall_without_thumbnail_loads() -> None:
    """Filtering should use search text and avoid thumbnail asset reads."""

    ensure_qapp()
    asset_repository = _CountingAssetRepository()
    popup = ModelPickerPopup(
        (_item("Checkpoint A", "alpha"), _item("Checkpoint B", "beta")),
        asset_repository=asset_repository,
    )

    popup._search.setText("alpha")

    assert [item.title for item in popup._view.items()] == ["Checkpoint A"]
    assert asset_repository.reads == 0
    destroy_qt_object(popup)


def test_model_picker_popup_shows_search_field_by_default() -> None:
    """Default popup construction should preserve the LoRA-style embedded search."""

    ensure_qapp()
    popup = ModelPickerPopup((_item("Checkpoint A", "alpha"),))
    layout = popup._frame.content_layout()

    assert isinstance(popup._search, SearchLineEdit)
    assert popup._search.isHidden() is False
    first_item = layout.itemAt(0)
    assert first_item is not None
    assert first_item.widget() is popup._search
    destroy_qt_object(popup)


def test_model_picker_popup_can_filter_from_hidden_external_search() -> None:
    """Field-driven picker use should hide embedded search while keeping filtering."""

    ensure_qapp()
    popup = ModelPickerPopup(
        (_item("Checkpoint A", "alpha"), _item("Checkpoint B", "beta")),
        show_search_field=False,
    )
    layout = popup._frame.content_layout()

    assert popup._search.isHidden() is True
    first_item = layout.itemAt(0)
    assert first_item is not None
    assert isinstance(first_item.widget(), FolderRouteBar)

    popup.set_search_text("beta")

    assert popup.search_text() == "beta"
    assert [item.title for item in popup._view.items()] == ["Checkpoint B"]
    destroy_qt_object(popup)


def test_model_picker_route_and_search_filters_compose() -> None:
    """Folder routes and search text should narrow the same visible wall state."""

    app = ensure_qapp()
    popup = ModelPickerPopup(
        (
            _item("Midna", "character midna", folder="illustrious/characters"),
            _item("Style", "style illustrious", folder="illustrious/style"),
            _item("Pony Style", "style pony", folder="pony"),
        )
    )
    popup.show()
    app.processEvents()

    _click_route_button(popup, "illustrious (2)")
    popup._search.setText("style")
    app.processEvents()

    assert popup._route_bar.current_route() == ("illustrious",)
    assert [item.title for item in popup._view.items()] == ["Style"]

    breadcrumb = popup._route_bar._breadcrumb
    QTest.mouseClick(breadcrumb.itemAt(0), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert [item.title for item in popup._view.items()] == ["Style", "Pony Style"]
    destroy_qt_object(popup)


def test_model_picker_route_and_external_search_filters_compose() -> None:
    """Hidden-search mode should keep route and field query as one filter state."""

    app = ensure_qapp()
    popup = ModelPickerPopup(
        (
            _item("Midna", "character midna", folder="illustrious/characters"),
            _item("Style", "style illustrious", folder="illustrious/style"),
            _item("Pony Style", "style pony", folder="pony"),
        ),
        show_search_field=False,
    )
    popup.show()
    app.processEvents()

    _click_route_button(popup, "illustrious (2)")
    popup.set_search_text("style")
    app.processEvents()

    assert popup._route_bar.current_route() == ("illustrious",)
    assert [item.title for item in popup._view.items()] == ["Style"]

    breadcrumb = popup._route_bar._breadcrumb
    QTest.mouseClick(breadcrumb.itemAt(0), Qt.MouseButton.LeftButton)
    app.processEvents()

    assert [item.title for item in popup._view.items()] == ["Style", "Pony Style"]
    destroy_qt_object(popup)


def test_model_picker_popup_emits_payload_from_wall_activation() -> None:
    """Popup activation should emit the selected picker item's payload."""

    ensure_qapp()
    payload = object()
    popup = ModelPickerPopup((_item("Model", "model", payload=payload),))
    activated: list[object] = []
    popup.modelActivated.connect(activated.append)

    assert popup._view.activate_current() is True

    assert activated == [payload]
    destroy_qt_object(popup)


def test_model_picker_popup_exposes_current_model_item() -> None:
    """External search owners should read current item through a typed popup API."""

    ensure_qapp()
    popup = ModelPickerPopup(
        (
            _item("Alpha", "alpha"),
            _item("Beta", "beta"),
        ),
        show_search_field=False,
    )

    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Alpha"

    popup.set_search_text("beta")

    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Beta"
    destroy_qt_object(popup)


def test_model_picker_popup_embedded_search_routes_arrow_keys_to_wall() -> None:
    """Embedded-search popups should navigate picker tiles with arrow keys."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = ModelPickerPopup(
        tuple(_item(f"Model {index}", f"model {index}") for index in range(12)),
        parent=host,
    )
    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(popup._search, Qt.Key.Key_Right)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 1"

    QTest.keyClick(popup._search, Qt.Key.Key_Left)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title == "Model 0"

    QTest.keyClick(popup._search, Qt.Key.Key_Down)
    app.processEvents()
    current_item = popup.current_item()
    assert current_item is not None
    assert current_item.title != "Model 0"

    destroy_qt_object(popup)
    destroy_qt_object(host)


def test_model_picker_popup_embedded_search_enter_activates_current_item() -> None:
    """Embedded-search popups should activate the keyboard-selected tile."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = ModelPickerPopup(
        (
            _item("Alpha", "alpha"),
            _item("Beta", "beta"),
        ),
        parent=host,
    )
    activated: list[object] = []
    popup.itemActivated.connect(activated.append)
    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    QTest.keyClick(popup._search, Qt.Key.Key_Right)
    QTest.keyClick(popup._search, Qt.Key.Key_Return)
    app.processEvents()

    assert len(activated) == 1
    assert isinstance(activated[0], ModelPickerItem)
    assert activated[0].title == "Beta"
    assert popup.isVisible() is False
    destroy_qt_object(popup)
    destroy_qt_object(host)
