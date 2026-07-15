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

"""Contract tests for shared toggle-aware menu button wrappers."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Signal
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

REPO_ROOT = Path(__file__).resolve().parents[1]


class _Signal:
    """Provide a minimal Qt-like signal with connect, disconnect, and emit."""

    def __init__(self) -> None:
        """Initialize the empty callback list."""

        self._callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """Register one callback or signal relay."""

        self._callbacks.append(callback)

    def disconnect(self, callback: object | None = None) -> None:
        """Remove one callback or clear all callbacks when omitted."""

        if callback is None:
            self._callbacks.clear()
            return
        self._callbacks.remove(callback)

    def emit(self, *args: object) -> None:
        """Invoke all callbacks with the supplied arguments."""

        for callback in list(self._callbacks):
            relay = getattr(callback, "emit", None)
            if callable(relay):
                relay(*args)
                continue
            callback(*args)


class _QObject:
    """Provide the event-filter hooks used by the wrapper helpers."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Initialize the installed filter collection."""

        self._event_filters: list[object] = []

    def installEventFilter(self, event_filter: object) -> None:
        """Record one installed event filter."""

        self._event_filters.append(event_filter)

    def removeEventFilter(self, event_filter: object) -> None:
        """Remove one installed event filter when present."""

        if event_filter in self._event_filters:
            self._event_filters.remove(event_filter)

    def _dispatch_event(self, event: object) -> None:
        """Deliver one event object to installed filters."""

        for event_filter in list(self._event_filters):
            handler = getattr(event_filter, "eventFilter", None)
            if callable(handler):
                handler(self, event)

    def eventFilter(self, _watched: object, _event: object) -> bool:
        """Accept event-filter fallback calls without side effects."""

        return False


class _QEvent:
    """Provide the event constants consumed by the popup tracker."""

    Hide = 18
    Close = 19
    Destroy = 16

    class Type:
        """Mirror Qt's nested enum shape."""

        Hide = 18
        Close = 19
        Destroy = 16

    def __init__(self, event_type: int) -> None:
        """Store one event type."""

        self._event_type = event_type

    def type(self) -> int:
        """Return the stored event type."""

        return self._event_type


class _Widget(_QObject):
    """Provide a minimal QWidget-like base for wrapper tests."""

    def __init__(self, parent: object | None = None) -> None:
        """Initialize visibility, geometry, and lifecycle signals."""

        super().__init__()
        self._parent = parent
        self._visible = False
        self._width = 120
        self._height = 32
        self.hidden_calls = 0
        self.closedSignal = _Signal()
        self.destroyed = _Signal()

    def width(self) -> int:
        """Return the configured width."""

        return self._width

    def height(self) -> int:
        """Return the configured height."""

        return self._height

    def mapToGlobal(self, point: object) -> object:
        """Return the supplied point unchanged."""

        return point

    def hide(self) -> None:
        """Hide the widget, dispatch a hide event, and emit close state."""

        self._visible = False
        self.hidden_calls += 1
        self._dispatch_event(_QEvent(_QEvent.Hide))
        self.closedSignal.emit()

    def close(self) -> None:
        """Close the widget and emit the close lifecycle hooks."""

        self._visible = False
        self._dispatch_event(_QEvent(_QEvent.Close))
        self.closedSignal.emit()

    def isVisible(self) -> bool:
        """Return the current visible state."""

        return self._visible

    def show(self) -> None:
        """Mark the widget as visible."""

        self._visible = True


class _Margins:
    """Provide the left margin lookup used by split-button geometry code."""

    def left(self) -> int:
        """Return a stable left margin."""

        return 0


class _Layout:
    """Provide the menu layout interface used by QFluent buttons."""

    def contentsMargins(self) -> _Margins:
        """Return zero margins for popup calculations."""

        return _Margins()


class _MenuView:
    """Provide the minimal menu view hooks used by QFluent buttons."""

    def __init__(self) -> None:
        """Initialize the minimum-width record."""

        self.minimum_width = 0

    def setMinimumWidth(self, width: int) -> None:
        """Record the requested minimum width."""

        self.minimum_width = width

    def adjustSize(self, *_args: object, **_kwargs: object) -> None:
        """Accept view size adjustments without side effects."""

    def heightForAnimation(self, _pos: object, _ani_type: object) -> int:
        """Return a stable popup height for branch selection."""

        return 100


class _Menu(_Widget):
    """Provide a popup menu double with exec and sizing hooks."""

    def __init__(self) -> None:
        """Initialize size, layout, and execution counters."""

        super().__init__()
        self.exec_calls = 0
        self.view = _MenuView()
        self._layout = _Layout()

    def adjustSize(self) -> None:
        """Accept menu size adjustments without side effects."""

    def layout(self) -> _Layout:
        """Return the popup layout double."""

        return self._layout

    def exec(self, *_args: object, **_kwargs: object) -> None:
        """Record one popup open request and mark the menu visible."""

        self.exec_calls += 1
        self._visible = True


class _ClickableWidget(_Widget):
    """Provide a widget stub with a clicked signal."""

    def __init__(self, parent: object | None = None) -> None:
        """Initialize the clicked signal and enable state."""

        super().__init__(parent)
        self.clicked = _Signal()
        self._enabled = True

    def setEnabled(self, enabled: bool) -> None:
        """Record the enabled state."""

        self._enabled = enabled

    def setObjectName(self, _name: str) -> None:
        """Accept object-name assignment without side effects."""


class _ToolButton(_ClickableWidget):
    """Provide a tool-button stub with mouse-release tracking."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Initialize release counters and cursor state."""

        super().__init__()
        self.mouse_release_calls = 0
        self._cursor = None

    def mouseReleaseEvent(self, _event: object) -> None:
        """Record one base mouse release."""

        self.mouse_release_calls += 1

    def setCursor(self, cursor: object) -> None:
        """Record cursor updates."""

        self._cursor = cursor

    def setToolTip(self, _tooltip: str) -> None:
        """Accept tooltip updates without side effects."""

    def setIcon(self, _icon: object) -> None:
        """Accept icon updates without side effects."""


class _DropDownToolButton(_ToolButton):
    """Provide a dropdown-tool-button stub with menu support."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Initialize menu storage and show counters."""

        super().__init__()
        self._menu: object | None = None
        self.show_menu_calls = 0

    def setMenu(self, menu: object) -> None:
        """Store one attached popup menu."""

        self._menu = menu

    def menu(self) -> object | None:
        """Return the attached popup menu."""

        return self._menu

    def _showMenu(self) -> None:
        """Record the popup request and execute the menu when present."""

        self.show_menu_calls += 1
        menu = self.menu()
        if menu is not None and hasattr(menu, "exec"):
            menu.exec(None)


class _TransparentDropDownToolButton(_DropDownToolButton):
    """Reuse the dropdown tool-button stub for the transparent variant."""


class _SplitButtonBase(_Widget):
    """Provide shared split-button wiring for tool and push variants."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Initialize primary and drop-button children with signals."""

        super().__init__()
        self.flyout: object | None = None
        self.show_flyout_calls = 0
        self.dropDownClicked = _Signal()
        self.clicked = _Signal()
        self.button = _ClickableWidget(self)
        self.dropButton = _ClickableWidget(self)
        self.button.clicked.connect(self.clicked)
        self.dropButton.clicked.connect(self.dropDownClicked)
        self.dropButton.clicked.connect(self.showFlyout)

    def setFlyout(self, flyout: object) -> None:
        """Store one attached flyout menu."""

        self.flyout = flyout

    def showFlyout(self) -> None:
        """Record one popup request and execute the flyout when present."""

        self.show_flyout_calls += 1
        if self.flyout is not None and hasattr(self.flyout, "exec"):
            self.flyout.exec(None)

    def setDropButton(self, button: _ClickableWidget) -> None:
        """Replace the drop button and restore the inherited signal wiring."""

        self.dropButton = button
        self.dropButton.clicked.connect(self.dropDownClicked)
        self.dropButton.clicked.connect(self.showFlyout)

    def setCursor(self, _cursor: object) -> None:
        """Accept cursor updates without side effects."""

    def setToolTip(self, _tooltip: str) -> None:
        """Accept tooltip updates without side effects."""

    def setIcon(self, _icon: object) -> None:
        """Accept icon updates without side effects."""


class _SplitToolButton(_SplitButtonBase):
    """Provide the split-tool-button base used by SeedBox and save menus."""


class _PrimarySplitPushButton(_SplitButtonBase):
    """Provide the primary split-push-button base used by generate menus."""


def _install_widget_stubs(monkeypatch) -> None:
    """Install minimal PySide6 and qfluentwidgets modules for wrapper imports."""

    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QEvent = _QEvent
    qtcore.QObject = _QObject
    qtcore.QPoint = lambda x=0, y=0: (x, y)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QWidget = _Widget
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)

    pyside6 = types.ModuleType("PySide6")
    pyside6.QtCore = qtcore
    pyside6.QtWidgets = qtwidgets
    monkeypatch.setitem(sys.modules, "PySide6", pyside6)

    qfw = types.ModuleType("qfluentwidgets")
    qfw.ToolButton = _ToolButton
    qfw.DropDownToolButton = _DropDownToolButton
    qfw.TransparentDropDownToolButton = _TransparentDropDownToolButton
    qfw.SplitToolButton = _SplitToolButton
    qfw.PrimarySplitPushButton = _PrimarySplitPushButton
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)


def _import_module(monkeypatch):
    """Import the shared wrapper module under lightweight widget stubs."""

    _install_widget_stubs(monkeypatch)
    package_name = "substitute.presentation.widgets"
    package = types.ModuleType(package_name)
    package.__path__ = [str(REPO_ROOT / "substitute" / "presentation" / "widgets")]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, package_name, package)

    module_name = "substitute.presentation.widgets.menu_buttons"
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPO_ROOT / "substitute" / "presentation" / "widgets" / "menu_buttons.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _ensure_qapp() -> QApplication:
    """Return the active Qt application used by lifecycle regression tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _flush_deferred_deletes(app: QApplication, *, cycles: int = 3) -> None:
    """Process deferred-deletion events until Qt wrappers become invalid."""

    for _ in range(cycles):
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()


def test_toggle_transparent_dropdown_button_closes_same_menu_on_second_click(
    monkeypatch,
) -> None:
    """Second clicks should hide the already-open dropdown menu instead of reopening it."""

    module = _import_module(monkeypatch)
    button = module.ToggleTransparentDropDownToolButton()
    menu = _Menu()
    button.setMenu(menu)

    button.mouseReleaseEvent(None)
    button.mouseReleaseEvent(None)
    button.mouseReleaseEvent(None)

    assert menu.exec_calls == 2
    assert menu.hidden_calls == 1


def test_toggle_split_tool_button_rewires_drop_arrow_to_toggle_flyout(
    monkeypatch,
) -> None:
    """Drop-arrow clicks should preserve the signal while toggling the shared flyout."""

    module = _import_module(monkeypatch)
    button = module.ToggleSplitToolButton()
    flyout = _Menu()
    drop_clicks: list[str] = []
    button.dropDownClicked.connect(lambda: drop_clicks.append("drop"))
    button.setFlyout(flyout)

    button.dropButton.clicked.emit()
    button.dropButton.clicked.emit()
    button.dropButton.clicked.emit()

    assert drop_clicks == ["drop", "drop", "drop"]
    assert flyout.exec_calls == 2
    assert flyout.hidden_calls == 1


def test_toggle_primary_split_button_preserves_primary_action(
    monkeypatch,
) -> None:
    """Primary split buttons should leave the main action path unchanged."""

    module = _import_module(monkeypatch)
    button = module.TogglePrimarySplitPushButton()
    flyout = _Menu()
    primary_clicks: list[str] = []
    button.clicked.connect(lambda: primary_clicks.append("primary"))
    button.setFlyout(flyout)

    button.button.clicked.emit()
    button.dropButton.clicked.emit()

    assert primary_clicks == ["primary"]
    assert flyout.exec_calls == 1


def test_external_popup_close_clears_tracked_open_state(monkeypatch) -> None:
    """Externally hidden popups should reopen cleanly on the next click."""

    module = _import_module(monkeypatch)
    button = module.ToggleDropDownToolButton()
    menu = _Menu()
    button.setMenu(menu)

    button.mouseReleaseEvent(None)
    menu.hide()
    button.mouseReleaseEvent(None)

    assert menu.exec_calls == 2
    assert menu.hidden_calls == 1


def test_same_click_close_does_not_reopen_popup_on_release(monkeypatch) -> None:
    """System-closed popups over the trigger should consume the following release."""

    module = _import_module(monkeypatch)
    button = module.ToggleTransparentDropDownToolButton()
    menu = _Menu()
    button.setMenu(menu)

    button.mouseReleaseEvent(None)
    monkeypatch.setattr(
        button,
        "_should_suppress_next_popup_show",
        lambda popup: popup is menu,
    )

    menu.hide()
    button.mouseReleaseEvent(None)
    button.mouseReleaseEvent(None)

    assert menu.exec_calls == 2


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="Qt deferred deletion can abort Windows xdist workers",
)
def test_widget_contains_cursor_returns_false_for_deleted_qt_widget() -> None:
    """Deleted Qt widgets should short-circuit cursor hit-testing without raising."""

    module = importlib.import_module("substitute.presentation.widgets.menu_buttons")
    app = _ensure_qapp()
    widget = QWidget()

    widget.deleteLater()
    _flush_deferred_deletes(app)

    assert isValid(widget) is False
    assert module._PopupToggleMixin._widget_contains_cursor(widget) is False


def test_widget_contains_cursor_logs_teardown_runtime_error(monkeypatch) -> None:
    """Cursor hit-test teardown failures should emit one debug record with context."""

    module = _import_module(monkeypatch)
    debug_calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        module,
        "log_debug",
        lambda _logger, message, **context: debug_calls.append((message, context)),
    )

    class _BrokenWidget:
        def rect(self) -> object:
            raise RuntimeError("already deleted")

        def mapFromGlobal(self, point: object) -> object:
            return point

    assert module._PopupToggleMixin._widget_contains_cursor(_BrokenWidget()) is False
    assert debug_calls == [
        (
            "Popup trigger cursor hit-test failed during teardown",
            {
                "widget_type": "_BrokenWidget",
                "error": "RuntimeError('already deleted')",
            },
        )
    ]


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="Qt deferred deletion can abort Windows xdist workers",
)
def test_tracked_popup_close_after_owner_deletion_does_not_raise(
    monkeypatch,
) -> None:
    """Late popup close callbacks should tolerate a deleted owner wrapper."""

    module = importlib.import_module("substitute.presentation.widgets.menu_buttons")
    app = _ensure_qapp()
    monkeypatch.setattr(module.sys, "platform", "win32", raising=False)
    debug_calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        module,
        "log_debug",
        lambda _logger, message, **context: debug_calls.append((message, context)),
    )

    class _RuntimePopup(QWidget):
        """Provide one real Qt popup double with the tracked lifecycle signal."""

        closedSignal = Signal()

        def __init__(self) -> None:
            """Initialize one popup flagged as system-hidden."""

            super().__init__()
            self.isHideBySystem = True

    class _RuntimeOwner(module._PopupToggleMixin, QWidget):
        """Provide one real Qt owner that reuses the shared popup mixin."""

        def __init__(self) -> None:
            """Prime popup tracking before constructing the QWidget base."""

            self._prime_popup_toggle_state()
            super().__init__()

    owner = _RuntimeOwner()
    popup = _RuntimePopup()
    owner._track_attached_popup(popup)
    owner._attached_popup_marked_open = True

    owner.deleteLater()
    _flush_deferred_deletes(app)

    assert isValid(owner) is False

    popup.closedSignal.emit()

    assert owner._attached_popup_marked_open is False
    assert owner._suppress_next_popup_show is False
    assert (
        "Skipped popup-close suppression recompute for invalid owner",
        {
            "owner_type": "_RuntimeOwner",
            "popup_type": "_RuntimePopup",
            "suppress_next_popup_show": False,
        },
    ) in debug_calls
