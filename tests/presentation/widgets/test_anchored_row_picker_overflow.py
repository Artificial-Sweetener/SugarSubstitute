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

"""Test anchored row picker overflow and rendered anchor alignment."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import SingleDirectionScrollArea  # type: ignore[import-untyped]

from substitute.presentation.widgets.anchored_row_picker import (
    AnchoredRowPicker,
    AnchoredRowPickerView,
)
from substitute.presentation.widgets.anchored_row_picker_row import (
    AnchoredRowPickerItem,
    AnchoredRowPickerRow,
    AnchoredRowPickerTextMode,
)
from tests.support.qt.lifecycle import destroy_widget_roots


@pytest.fixture()
def owned_widgets() -> Iterator[list[QWidget]]:
    """Synchronously destroy widgets created by one overflow contract."""

    widgets: list[QWidget] = []
    yield widgets
    destroy_widget_roots(widgets)
    widgets.clear()


def test_anchored_row_picker_view_scrolls_only_when_rows_exceed_height(
    owned_widgets: list[QWidget],
    qt_application_owner: QApplication,
) -> None:
    """Oversized pickers should expose QFluent scrolling without changing short lists."""

    application = qt_application_owner
    short_view = AnchoredRowPickerView(
        items=tuple(
            AnchoredRowPickerItem(str(index), f"Scene {index}") for index in range(3)
        ),
        active_key="0",
        anchor_size=QSize(100, 28),
        maximum_height=180,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )
    overflowing_view = AnchoredRowPickerView(
        items=tuple(
            AnchoredRowPickerItem(str(index), f"Scene {index}") for index in range(20)
        ),
        active_key="10",
        anchor_size=QSize(100, 28),
        maximum_height=180,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )
    owned_widgets.extend((short_view, overflowing_view))
    short_view.setUpdatesEnabled(False)
    overflowing_view.setUpdatesEnabled(False)
    short_view.show()
    overflowing_view.show()
    application.processEvents()

    short_scroll = short_view.findChild(SingleDirectionScrollArea)
    overflowing_scroll = overflowing_view.findChild(SingleDirectionScrollArea)

    assert short_scroll is not None
    assert short_view.requires_scroll() is False
    assert short_scroll.vScrollBar.isVisible() is False
    assert overflowing_scroll is not None
    assert overflowing_view.height() <= 180
    assert overflowing_view.requires_scroll() is True
    assert overflowing_scroll.vScrollBar.isVisible() is True
    assert overflowing_view.width() == short_view.width()
    visible_handle_right = (
        overflowing_scroll.vScrollBar.x()
        + overflowing_scroll.vScrollBar.handle.geometry().right()
    )
    assert visible_handle_right == overflowing_scroll.rect().right()


def test_anchored_row_picker_view_reveals_active_and_keyboard_rows(
    owned_widgets: list[QWidget],
    qt_application_owner: QApplication,
) -> None:
    """Opening and keyboard movement should keep the highlighted row in view."""

    application = qt_application_owner
    view = AnchoredRowPickerView(
        items=tuple(
            AnchoredRowPickerItem(str(index), f"Source {index}") for index in range(20)
        ),
        active_key="18",
        anchor_size=QSize(120, 28),
        maximum_height=180,
        active_text_mode="anchor_center",
        inactive_text_mode="row_left",
    )
    owned_widgets.append(view)
    view.setUpdatesEnabled(False)
    view.show()
    application.processEvents()
    view.reveal_active_row()
    application.processEvents()

    scroll = view.findChild(SingleDirectionScrollArea)
    active_row = view.row_for_key("18")
    assert scroll is not None
    assert active_row is not None
    assert view.requires_scroll() is True
    assert scroll.verticalScrollBar().value() > 0
    _assert_row_is_visible(active_row, scroll)

    view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
    )
    application.processEvents()

    next_row = view.row_for_key("19")
    assert view.active_key() == "19"
    assert next_row is not None
    _assert_row_is_visible(next_row, scroll)


@pytest.mark.parametrize(
    ("anchor_width", "row_width", "active_text_mode"),
    [
        (64, 64, "row_center"),
        (96, 260, "anchor_center"),
    ],
)
def test_anchored_row_picker_preserves_button_text_overlay_after_flyout_layout(
    owned_widgets: list[QWidget],
    qt_application_owner: QApplication,
    anchor_width: int,
    row_width: int,
    active_text_mode: AnchoredRowPickerTextMode,
) -> None:
    """QFluent flyout minimum sizing must not displace the selected row slot."""

    application = qt_application_owner
    parent = QWidget()
    parent.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    parent.setGeometry(80, 80, 640, 480)
    anchor = QWidget(parent)
    anchor.setGeometry(220, 224, anchor_width, 28)
    parent.show()
    application.processEvents()
    owned_widgets.append(parent)
    picker = AnchoredRowPicker(parent)

    try:
        picker.show_for(
            anchor,
            items=tuple(
                AnchoredRowPickerItem(str(index), f"Item {index}")
                for index in range(100)
            ),
            active_key="50",
            row_width=row_width,
            active_text_mode=active_text_mode,
            inactive_text_mode="row_left",
            selected_callback=lambda _key: None,
        )
        flyout = picker._flyout
        assert flyout is not None
        flyout.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        flyout.setUpdatesEnabled(False)
        application.processEvents()
        view = flyout.findChild(AnchoredRowPickerView)
        assert view is not None
        active_row = view.row_for_key("50")
        assert active_row is not None
        active_text_rect = active_row.text_rect_for_paint()
        active_text_global = QRect(
            active_row.mapToGlobal(active_text_rect.topLeft()),
            active_text_rect.size(),
        )
        anchor_global = QRect(
            anchor.mapToGlobal(anchor.rect().topLeft()),
            anchor.size(),
        )

        assert active_text_global == anchor_global
    finally:
        picker.close()


def _assert_row_is_visible(
    row: AnchoredRowPickerRow,
    scroll: SingleDirectionScrollArea,
) -> None:
    """Assert that one picker row is fully inside the scroll viewport."""

    row_top = row.mapTo(scroll.viewport(), QPoint()).y()
    assert row_top >= 0
    assert row_top + row.height() <= scroll.viewport().height()
