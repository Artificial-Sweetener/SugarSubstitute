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

"""Verify searchable popup placement, capacity, and reveal completion."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest
from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import substitute.presentation.widgets.searchable_combo_popup as popup_module
from substitute.presentation.widgets.searchable_combo_helpers import (
    AttachedPopupPlacement,
)
from substitute.presentation.widgets.searchable_combo_popup import (
    SearchableComboPopup,
)
from tests.presentation.widgets.combo_box.support import MountedCombo
from tests.support.qt.lifecycle import ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_popup_clamps_to_ten_visible_rows(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Large result sets should expose ten rows and retain scrolling for all items."""

    mounted = combo_mount(
        items=tuple(f"Choice {index:02d}" for index in range(30)),
        host_size=(520, 640),
        host_position=QPoint(40, 40),
    )
    popup = _open_popup(mounted)
    _wait_for_reveal(popup)
    expected_view_height = popup._view_height_for_visible_rows(10)
    margins = popup.layout().contentsMargins()

    assert (
        popup.list_global_top()
        == mounted.combo.mapToGlobal(QPoint(0, mounted.combo.height())).y()
    )
    assert popup.view.height() == expected_view_height
    assert popup.height() == expected_view_height + margins.top() + margins.bottom()
    assert popup.visible_texts()[0] == "Choice 00"
    assert popup.visible_texts()[-1] == "Choice 29"


def test_popup_opens_above_near_screen_bottom(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """A low combo should open upward while remaining within available geometry."""

    application = ensure_qt_application()
    available = _available_geometry(application)
    mounted = combo_mount(
        items=tuple(f"Choice {index:02d}" for index in range(12)),
        host_size=(480, 180),
        host_position=QPoint(
            available.left() + 40,
            max(available.top(), available.bottom() - 190),
        ),
        combo_position=QPoint(40, 142),
    )
    popup = _open_popup(mounted)
    _wait_for_reveal(popup)
    combo_top = mounted.combo.mapToGlobal(QPoint()).y()

    assert popup.list_global_bottom() == combo_top
    assert popup.geometry().top() >= available.top()


def test_popup_reveal_uses_qfluent_motion_contract(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Opening should use the expected QFluent duration, easing, and offset."""

    mounted = combo_mount(
        items=tuple(f"Choice {index:02d}" for index in range(12)),
        host_size=(520, 640),
        host_position=QPoint(40, 40),
    )
    popup = _open_popup(mounted)
    animation = popup._reveal_animation
    assert animation is not None
    start_position = animation.startValue()
    end_position = animation.endValue()
    assert isinstance(start_position, QPoint)
    assert isinstance(end_position, QPoint)

    reveal_offset = QPoint(0, int((popup.height() + 5) / 2))
    assert animation.duration() == 250
    assert animation.easingCurve().type() == QEasingCurve.Type.OutQuad
    assert animation.state() == QAbstractAnimation.State.Running
    assert start_position == end_position - reveal_offset

    _wait_for_reveal(popup)

    assert popup.pos() == end_position


def test_popup_shrinks_and_stays_attached_when_space_is_tight(
    combo_mount: Callable[..., MountedCombo],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A starved popup should reduce visible rows without detaching."""

    def forced_starved_placement(**kwargs: object) -> AttachedPopupPlacement:
        """Return a deterministic three-row downward placement."""

        field_global_rect = cast(QRect, kwargs["field_global_rect"])
        row_height = cast(int, kwargs["row_height"])
        vertical_chrome_height = cast(int, kwargs["vertical_chrome_height"])
        return AttachedPopupPlacement(
            geometry=QRect(
                field_global_rect.left(),
                field_global_rect.top() + field_global_rect.height(),
                260,
                3 * row_height + vertical_chrome_height,
            ),
            opens_down=True,
            visible_row_count=3,
            requires_scroll=True,
        )

    monkeypatch.setattr(
        popup_module,
        "attached_combo_popup_placement",
        forced_starved_placement,
    )
    mounted = combo_mount(
        items=tuple(f"Choice {index:02d}" for index in range(30)),
        host_size=(460, 120),
        host_position=QPoint(40, 40),
        combo_position=QPoint(40, 62),
    )
    popup = _open_popup(mounted)
    _wait_for_reveal(popup)
    combo_bottom = mounted.combo.mapToGlobal(QPoint(0, mounted.combo.height())).y()
    margins = popup.layout().contentsMargins()

    assert popup.list_global_top() == combo_bottom
    assert popup.view.height() == popup._view_height_for_visible_rows(3)
    assert popup.height() == (
        popup._view_height_for_visible_rows(3) + margins.top() + margins.bottom()
    )


def _open_popup(mounted: MountedCombo) -> SearchableComboPopup:
    """Open one popup and return it after visible state is observable."""

    QTest.mouseClick(mounted.combo, Qt.MouseButton.LeftButton)
    popup = mounted.combo._popup
    assert popup is not None
    wait_for_qt_condition(popup.isVisible)
    return popup


def _wait_for_reveal(popup: SearchableComboPopup) -> None:
    """Wait for the owning animation to reach its terminal state."""

    animation = popup._reveal_animation
    if animation is None:
        return
    wait_for_qt_condition(lambda: animation.state() == QAbstractAnimation.State.Stopped)


def _available_geometry(application: QApplication) -> QRect:
    """Return the primary screen's available geometry."""

    screen = application.primaryScreen()
    assert screen is not None
    return screen.availableGeometry()
