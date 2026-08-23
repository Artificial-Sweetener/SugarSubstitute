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

"""Verify model picker popup layout contracts."""

from __future__ import annotations


import pytest
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import SearchLineEdit  # type: ignore[import-untyped]

from substitute.presentation.widgets.fluent_popup_frame import AttachedFluentPopupFrame
from substitute.presentation.widgets.folder_route import FolderRouteBar
from substitute.presentation.widgets.model_picker import (
    MODEL_PICKER_POPUP_HEIGHT,
    MODEL_PICKER_POPUP_WIDTH,
    ModelPickerPopup,
    ModelPickerPopupPlacementMode,
    ModelPickerWallView,
)
import substitute.presentation.widgets.model_picker.model_picker_popup as model_picker_popup_module
from tests.support.qt.lifecycle import destroy_qt_object


from tests.presentation.widgets.model_picker.popup_fixtures import (
    ensure_qapp,
    _item,
    _anchor_rect,
    _top_screen_anchor_rect,
    _bottom_screen_anchor_rect,
    _screen_available_geometry,
    _visible_layout_widgets,
)


def test_model_picker_popup_uses_shared_controls_and_size() -> None:
    """The generic picker should own QFluent search, route, wall, and frame chrome."""

    ensure_qapp()
    popup = ModelPickerPopup((_item("Model", "model"),))
    layout = popup._frame.content_layout()

    assert isinstance(popup._search, SearchLineEdit)
    assert isinstance(popup._frame, AttachedFluentPopupFrame)
    route_item = layout.itemAt(1)
    wall_item = layout.itemAt(2)
    assert route_item is not None
    assert wall_item is not None
    assert isinstance(route_item.widget(), FolderRouteBar)
    assert isinstance(wall_item.widget(), ModelPickerWallView)
    assert popup.size().width() == MODEL_PICKER_POPUP_WIDTH
    assert popup.size().height() == MODEL_PICKER_POPUP_HEIGHT
    destroy_qt_object(popup)


def test_model_picker_popup_uses_manual_dismissal_window_type() -> None:
    """Model picker popup should not use Qt.Popup native outside-click dismissal."""

    app = ensure_qapp()
    popup = ModelPickerPopup((_item("Model", "model"),))
    flags = popup.windowFlags()
    window_type = flags & Qt.WindowType.WindowType_Mask

    assert window_type == Qt.WindowType.Tool
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.NoDropShadowWindowHint

    destroy_qt_object(popup)
    app.processEvents()


def test_model_picker_popup_below_order_keeps_controls_on_top() -> None:
    """Below placement should keep search and breadcrumbs above the wall."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(800, 1000)
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)

    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    assert popup._placement_mode is ModelPickerPopupPlacementMode.BELOW
    assert _visible_layout_widgets(popup) == [
        popup._search,
        popup._route_bar,
        popup._view,
    ]
    destroy_qt_object(popup)
    destroy_qt_object(host)


def test_model_picker_popup_above_order_keeps_controls_on_bottom() -> None:
    """Above placement should move search and breadcrumbs below the wall."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 720)
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)

    anchor = _bottom_screen_anchor_rect()

    popup.show_attached_to(anchor)
    app.processEvents()

    assert popup._placement_mode is ModelPickerPopupPlacementMode.ABOVE
    assert popup.geometry().top() + popup.geometry().height() <= anchor.top()
    assert _visible_layout_widgets(popup) == [
        popup._view,
        popup._route_bar,
        popup._search,
    ]
    destroy_qt_object(popup)
    destroy_qt_object(host)


def test_model_picker_popup_above_order_without_embedded_search_places_route_on_bottom() -> (
    None
):
    """Field-driven above placement should place breadcrumbs at the bottom edge."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 720)
    host.show()
    popup = ModelPickerPopup(
        (_item("Model", "model"),),
        show_search_field=False,
        parent=host,
    )

    popup.show_attached_to(_bottom_screen_anchor_rect())
    app.processEvents()

    assert popup._placement_mode is ModelPickerPopupPlacementMode.ABOVE
    assert popup._search.isHidden() is True
    assert _visible_layout_widgets(popup) == [popup._view, popup._route_bar]
    destroy_qt_object(popup)
    destroy_qt_object(host)


def test_model_picker_popup_starved_placement_stays_attached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starved placement should shrink below the anchor instead of detaching."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 400)
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)
    monkeypatch.setattr(
        model_picker_popup_module,
        "model_picker_screen_available_geometry",
        lambda _anchor_rect: QRect(0, 0, 640, 400),
    )

    popup.show_attached_to(_anchor_rect(100, 190))
    app.processEvents()

    assert popup._placement_mode is ModelPickerPopupPlacementMode.BELOW
    assert popup.geometry().top() == 191
    assert popup.geometry().height() == 400 - 8 - 191
    assert _visible_layout_widgets(popup) == [
        popup._search,
        popup._route_bar,
        popup._view,
    ]
    destroy_qt_object(popup)
    destroy_qt_object(host)


def test_model_picker_popup_can_extend_beyond_owner_widget() -> None:
    """Screen-attached popup geometry should not be constrained to owner size."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(320, 220)
    host.move(_screen_available_geometry().topLeft() + QPoint(24, 24))
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)

    host_bottom_global = host.mapToGlobal(QPoint(0, host.height())).y()
    popup.show_attached_to(
        QRect(host.mapToGlobal(QPoint(16, host.height() - 24)), QSize(1, 1))
    )
    app.processEvents()

    assert popup.isVisible() is True
    assert popup.geometry().height() > host.height()
    assert popup.geometry().top() + popup.geometry().height() > host_bottom_global
    destroy_qt_object(popup)
    destroy_qt_object(host)


def test_model_picker_popup_hides_on_escape_and_outside_click() -> None:
    """The attached picker should dismiss from keyboard or outside host clicks."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 480)
    host.show()
    popup = ModelPickerPopup((_item("Model", "model"),), parent=host)
    popup.show_attached_to(_top_screen_anchor_rect())
    app.processEvents()

    assert popup.isVisible() is True
    QTest.keyClick(popup._search, Qt.Key.Key_Escape)
    app.processEvents()
    assert popup.isVisible() is False

    popup.show_attached_to(_top_screen_anchor_rect(300))
    app.processEvents()
    QTest.mouseClick(host, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
    app.processEvents()

    assert popup.isVisible() is False
    destroy_qt_object(popup)
    destroy_qt_object(host)
