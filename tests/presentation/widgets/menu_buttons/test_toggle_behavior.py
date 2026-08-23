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

"""Verify toggle menu buttons through the real Qt and QFluent owners."""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QHideEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import RoundMenu  # type: ignore[import-untyped]
from shiboken6 import isValid

import substitute.presentation.widgets.menu_buttons as menu_buttons
from substitute.presentation.widgets.menu_buttons import (
    ToggleDropDownToolButton,
    TogglePrimarySplitPushButton,
    ToggleSplitToolButton,
    ToggleTransparentDropDownToolButton,
    _PopupToggleMixin,
)
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _RecordingRoundMenu(RoundMenu):  # type: ignore[misc]
    """Expose real menu geometry while recording nonblocking open requests."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a parent-owned menu with empty content."""

        super().__init__(parent=parent)
        self.exec_calls = 0
        self.hidden_calls = 0

    def exec(self, *_args: object, **_kwargs: object) -> None:
        """Record and show the menu without an animation clock."""

        self.exec_calls += 1
        self.show()

    def hide(self) -> None:
        """Record explicit toggle hides before delegating to Qt."""

        self.hidden_calls += 1
        super().hide()


class _RecordingPopup(QWidget):
    """Provide the minimal real QWidget boundary accepted by split buttons."""

    closedSignal = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a parent-owned popup with deterministic counters."""

        super().__init__(parent, Qt.WindowType.Tool)
        self.exec_calls = 0
        self.hidden_calls = 0
        self.isHideBySystem = False

    def exec(self, _position: QPoint) -> None:
        """Record and show one split-button popup request."""

        self.exec_calls += 1
        self.show()

    def hide(self) -> None:
        """Record explicit toggle hides before delegating to Qt."""

        self.hidden_calls += 1
        super().hide()

    def hideEvent(self, event: QHideEvent) -> None:
        """Publish the popup lifecycle event used by the production tracker."""

        super().hideEvent(event)
        self.closedSignal.emit()


def test_transparent_dropdown_second_click_closes_and_third_reopens() -> None:
    """Repeated real trigger clicks should alternate the attached menu state."""

    ensure_qt_application()
    button = ToggleTransparentDropDownToolButton()
    menu = _RecordingRoundMenu(button)
    button.setMenu(menu)
    button.show()

    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(menu.isVisible)
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(lambda: not menu.isVisible())
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_for_qt_condition(menu.isVisible)

    assert menu.exec_calls == 2
    assert menu.hidden_calls == 1
    destroy_qt_object(button)


def test_split_tool_drop_arrow_preserves_signal_and_toggles_flyout() -> None:
    """The real drop arrow should retain its public signal while toggling."""

    ensure_qt_application()
    button = ToggleSplitToolButton()
    popup = _RecordingPopup(button)
    drop_clicks: list[str] = []
    button.dropDownClicked.connect(lambda: drop_clicks.append("drop"))
    button.setFlyout(popup)

    button.dropButton.clicked.emit()
    button.dropButton.clicked.emit()
    button.dropButton.clicked.emit()

    assert drop_clicks == ["drop", "drop", "drop"]
    assert popup.exec_calls == 2
    assert popup.hidden_calls == 1
    destroy_qt_object(button)


def test_primary_split_button_preserves_primary_action() -> None:
    """The real primary child should remain independent of flyout toggling."""

    ensure_qt_application()
    button = TogglePrimarySplitPushButton()
    popup = _RecordingPopup(button)
    primary_clicks: list[str] = []
    button.clicked.connect(lambda: primary_clicks.append("primary"))
    button.setFlyout(popup)

    button.button.clicked.emit()
    button.dropButton.clicked.emit()

    assert primary_clicks == ["primary"]
    assert popup.exec_calls == 1
    destroy_qt_object(button)


def test_external_popup_close_clears_tracked_open_state() -> None:
    """An externally hidden real menu should reopen on the next trigger."""

    ensure_qt_application()
    button = ToggleDropDownToolButton()
    menu = _RecordingRoundMenu(button)
    button.setMenu(menu)

    button._toggle_attached_popup(button._showMenu)
    menu.isHideBySystem = False
    menu.hide()
    button._toggle_attached_popup(button._showMenu)

    assert menu.exec_calls == 2
    assert menu.hidden_calls == 1
    destroy_qt_object(button)


def test_same_close_action_does_not_reopen_popup_on_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A system close over the trigger should consume the matching release."""

    ensure_qt_application()
    button = ToggleTransparentDropDownToolButton()
    menu = _RecordingRoundMenu(button)
    button.setMenu(menu)
    button._toggle_attached_popup(button._showMenu)
    monkeypatch.setattr(button, "_should_suppress_next_popup_show", lambda _popup: True)

    menu.hide()
    button._toggle_attached_popup(button._showMenu)
    button._toggle_attached_popup(button._showMenu)

    assert menu.exec_calls == 2
    destroy_qt_object(button)


def test_cursor_hit_test_rejects_destroyed_qt_widget() -> None:
    """A synchronously destroyed wrapper should short-circuit hit testing."""

    ensure_qt_application()
    widget = QWidget()
    destroy_qt_object(widget)

    assert isValid(widget) is False
    assert _PopupToggleMixin._widget_contains_cursor(widget) is False


def test_cursor_hit_test_logs_runtime_teardown_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wrapper race should retain structured diagnostic context."""

    debug_calls: list[tuple[str, dict[str, object]]] = []

    def record_debug(
        _logger: object,
        message: str,
        **context: object,
    ) -> None:
        """Record one structured production debug event."""

        debug_calls.append((message, context))

    monkeypatch.setattr(menu_buttons, "log_debug", record_debug)

    class _BrokenWidget:
        """Raise from the native geometry boundary during teardown."""

        def rect(self) -> object:
            """Simulate a wrapper whose C++ geometry owner is gone."""

            raise RuntimeError("already deleted")

        def mapFromGlobal(self, point: object) -> object:
            """Preserve the supplied point when geometry remains callable."""

            return point

    assert _PopupToggleMixin._widget_contains_cursor(_BrokenWidget()) is False
    assert debug_calls == [
        (
            "Popup trigger cursor hit-test failed during teardown",
            {
                "widget_type": "_BrokenWidget",
                "error": "RuntimeError('already deleted')",
            },
        )
    ]


def test_late_popup_close_tolerates_destroyed_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Late lifecycle signals should clear state without touching dead Qt state."""

    ensure_qt_application()
    monkeypatch.setattr(sys, "platform", "win32")
    debug_calls: list[tuple[str, dict[str, object]]] = []

    def record_debug(
        _logger: object,
        message: str,
        **context: object,
    ) -> None:
        """Record one structured production debug event."""

        debug_calls.append((message, context))

    monkeypatch.setattr(menu_buttons, "log_debug", record_debug)

    class _RuntimeOwner(_PopupToggleMixin, QWidget):
        """Mount the production tracker on a real Qt lifetime owner."""

        def __init__(self) -> None:
            """Prime tracker state before QWidget construction."""

            self._prime_popup_toggle_state()
            super().__init__()

    owner = _RuntimeOwner()
    popup = _RecordingPopup()
    owner._track_attached_popup(popup)
    owner._attached_popup_marked_open = True
    destroy_qt_object(owner)

    assert isValid(owner) is False
    popup.closedSignal.emit()

    assert owner._attached_popup_marked_open is False
    assert owner._suppress_next_popup_show is False
    assert (
        "Skipped popup-close suppression recompute for invalid owner",
        {
            "owner_type": "_RuntimeOwner",
            "popup_type": "_RecordingPopup",
            "suppress_next_popup_show": False,
        },
    ) in debug_calls
    destroy_qt_object(popup)
