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

"""Provide toggle-aware wrappers for QFluent popup menu buttons."""

from __future__ import annotations

import sys
from typing import Callable

try:
    from shiboken6 import isValid as _is_valid_shiboken_object
except ImportError:  # pragma: no cover - fallback for lightweight test stubs
    _is_valid_shiboken_object = None

try:
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QCursor
except ImportError:  # pragma: no cover - fallback for lightweight test stubs

    class QEvent:  # type: ignore[no-redef]
        """Provide the event constants consumed by popup tracking."""

        Hide = 18
        Close = 19
        Destroy = 16

        class Type:
            """Mirror Qt's nested event enum shape."""

            Hide = 18
            Close = 19
            Destroy = 16

    class QCursor:  # type: ignore[no-redef]
        """Provide a minimal cursor facade for lightweight test stubs."""

        @staticmethod
        def pos() -> tuple[int, int]:
            """Return a stable origin position."""

            return (0, 0)


try:
    from qfluentwidgets import DropDownToolButton as _RuntimeDropDownToolButton
    from qfluentwidgets import PrimarySplitPushButton as _RuntimePrimarySplitPushButton
    from qfluentwidgets import SplitToolButton as _RuntimeSplitToolButton
    from qfluentwidgets import ToolButton as _RuntimeToolButton
    from qfluentwidgets import (
        TransparentDropDownToolButton as _RuntimeTransparentDropDownToolButton,
    )
except (ImportError, AttributeError):  # pragma: no cover - fallback for tests only
    _RuntimeDropDownToolButton = None
    _RuntimePrimarySplitPushButton = None
    _RuntimeSplitToolButton = None
    _RuntimeToolButton = None
    _RuntimeTransparentDropDownToolButton = None

from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.widgets.menu_buttons")


class _FallbackSignal:
    """Provide a minimal signal implementation for fallback widget classes."""

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
        """Invoke all registered callbacks with the supplied arguments."""

        for callback in list(self._callbacks):
            relay = getattr(callback, "emit", None)
            if callable(relay):
                relay(*args)
                continue
            callback(*args)


class _FallbackObject:
    """Provide event-filter plumbing used by popup tracking helpers."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Initialize the installed event-filter collection."""

        self._event_filters: list[object] = []

    def installEventFilter(self, event_filter: object) -> None:
        """Register one event filter."""

        self._event_filters.append(event_filter)

    def removeEventFilter(self, event_filter: object) -> None:
        """Remove one previously installed event filter."""

        if event_filter in self._event_filters:
            self._event_filters.remove(event_filter)

    def _dispatch_event(self, event: object) -> None:
        """Deliver one event object to installed filters."""

        for event_filter in list(self._event_filters):
            handler = getattr(event_filter, "eventFilter", None)
            if callable(handler):
                handler(self, event)

    def eventFilter(self, _watched: object, _event: object) -> bool:
        """Accept event-filter delegation without side effects."""

        return False


class _FallbackWidget(_FallbackObject):
    """Provide the QWidget-like behavior required by wrapper tests."""

    def __init__(self, parent: object | None = None) -> None:
        """Initialize geometry, visibility, and lifecycle state."""

        super().__init__()
        self._parent = parent
        self._visible = False
        self._width = 120
        self._height = 32
        self._position = (0, 0)
        self.destroyed = _FallbackSignal()
        self.closedSignal = _FallbackSignal()

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
        """Hide the widget and notify observers."""

        self._visible = False
        self._dispatch_event(_FallbackEvent(_event_type("Hide", 18)))
        self.closedSignal.emit()

    def close(self) -> None:
        """Close the widget and notify observers."""

        self._visible = False
        self._dispatch_event(_FallbackEvent(_event_type("Close", 19)))
        self.closedSignal.emit()

    def isVisible(self) -> bool:
        """Return the current visible state."""

        return self._visible

    def show(self) -> None:
        """Mark the widget visible."""

        self._visible = True

    def move(self, x: int, y: int) -> None:
        """Store the widget position."""

        self._position = (x, y)

    def raise_(self) -> None:
        """Accept z-order raises without side effects."""


class _FallbackEvent:
    """Provide a minimal event object for fallback popup lifecycle hooks."""

    def __init__(self, event_type: int) -> None:
        """Store one event type."""

        self._event_type = event_type

    def type(self) -> int:
        """Return the stored event type."""

        return self._event_type


class _FallbackClickableWidget(_FallbackWidget):
    """Provide a widget stub with a clicked signal and enable state."""

    def __init__(self, parent: object | None = None) -> None:
        """Initialize click signaling and enabled state."""

        super().__init__(parent)
        self.clicked = _FallbackSignal()
        self._enabled = True

    def setEnabled(self, enabled: bool) -> None:
        """Record the enabled state."""

        self._enabled = enabled

    def setFixedWidth(self, width: int) -> None:
        """Store the fixed width."""

        self._width = width

    def setFixedHeight(self, height: int) -> None:
        """Store the fixed height."""

        self._height = height

    def setMinimumWidth(self, width: int) -> None:
        """Store the minimum width as the current width."""

        self._width = width

    def setMaximumWidth(self, width: int) -> None:
        """Store the maximum width as the current width."""

        self._width = width

    def setObjectName(self, _name: str) -> None:
        """Accept object-name assignment without side effects."""

    def setStyleSheet(self, _style: str) -> None:
        """Accept style updates without side effects."""


class _FallbackToolButton(_FallbackClickableWidget):
    """Provide a minimal QFluent-like tool button base."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Initialize mouse-release tracking and icon state."""

        super().__init__()
        self._icon = None
        self._tooltip = ""

    def mouseReleaseEvent(self, _event: object) -> None:
        """Accept mouse-release forwarding without side effects."""

    def setIcon(self, icon: object) -> None:
        """Store the current icon payload."""

        self._icon = icon

    def setToolTip(self, tooltip: str) -> None:
        """Store the tooltip text."""

        self._tooltip = tooltip

    def setCursor(self, _cursor: object) -> None:
        """Accept cursor updates without side effects."""


class _FallbackDropDownToolButton(_FallbackToolButton):
    """Provide a minimal dropdown tool-button base."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Initialize menu storage."""

        super().__init__()
        self._menu: object | None = None

    def setMenu(self, menu: object) -> None:
        """Store one attached popup menu."""

        self._menu = menu

    def menu(self) -> object | None:
        """Return the attached popup menu."""

        return self._menu

    def _showMenu(self) -> None:
        """Execute the attached menu when present."""

        menu = self.menu()
        if menu is not None and hasattr(menu, "exec"):
            menu.exec(None)


class _FallbackTransparentDropDownToolButton(_FallbackDropDownToolButton):
    """Reuse the fallback dropdown base for the transparent variant."""


class _FallbackSplitButtonBase(_FallbackWidget):
    """Provide shared split-button child wiring for fallback wrappers."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Initialize primary and drop-button children plus flyout state."""

        super().__init__()
        self.flyout: object | None = None
        self.clicked = _FallbackSignal()
        self.dropDownClicked = _FallbackSignal()
        self.button = _FallbackClickableWidget(self)
        self.dropButton = _FallbackClickableWidget(self)
        self.button.clicked.connect(self.clicked)
        self.dropButton.clicked.connect(self.dropDownClicked)
        self.dropButton.clicked.connect(self.showFlyout)

    def setFlyout(self, flyout: object) -> None:
        """Store the attached popup flyout."""

        self.flyout = flyout

    def showFlyout(self) -> None:
        """Execute the attached flyout when present."""

        if self.flyout is not None and hasattr(self.flyout, "exec"):
            self.flyout.exec(None)

    def setDropButton(self, button: _FallbackClickableWidget) -> None:
        """Replace the drop button and restore inherited signal wiring."""

        self.dropButton = button
        self.dropButton.clicked.connect(self.dropDownClicked)
        self.dropButton.clicked.connect(self.showFlyout)

    def setIcon(self, _icon: object) -> None:
        """Accept icon updates without side effects."""

    def setCursor(self, _cursor: object) -> None:
        """Accept cursor updates without side effects."""

    def setToolTip(self, _tooltip: str) -> None:
        """Accept tooltip updates without side effects."""

    def setEnabled(self, _enabled: bool) -> None:
        """Accept enabled-state updates without side effects."""

    def setFixedWidth(self, width: int) -> None:
        """Store the fixed width."""

        self._width = width

    def setFixedHeight(self, height: int) -> None:
        """Store the fixed height."""

        self._height = height

    def setMinimumWidth(self, width: int) -> None:
        """Store the minimum width as the current width."""

        self._width = width

    def setMaximumWidth(self, width: int) -> None:
        """Store the maximum width as the current width."""

        self._width = width


class _FallbackSplitToolButton(_FallbackSplitButtonBase):
    """Provide the fallback split-tool-button base."""


class _FallbackPrimarySplitPushButton(_FallbackSplitButtonBase):
    """Provide the fallback primary split-push-button base."""


if (
    _RuntimeToolButton is None
    or _RuntimeDropDownToolButton is None
    or _RuntimeTransparentDropDownToolButton is None
    or _RuntimeSplitToolButton is None
    or _RuntimePrimarySplitPushButton is None
):
    ToolButton = _FallbackToolButton
    DropDownToolButton = _FallbackDropDownToolButton
    TransparentDropDownToolButton = _FallbackTransparentDropDownToolButton
    SplitToolButton = _FallbackSplitToolButton
    PrimarySplitPushButton = _FallbackPrimarySplitPushButton
else:  # pragma: no cover - exercised in the real application runtime
    ToolButton = _RuntimeToolButton
    DropDownToolButton = _RuntimeDropDownToolButton
    TransparentDropDownToolButton = _RuntimeTransparentDropDownToolButton
    SplitToolButton = _RuntimeSplitToolButton
    PrimarySplitPushButton = _RuntimePrimarySplitPushButton


def _event_type(attr_name: str, fallback: int) -> int:
    """Resolve QEvent constants across Qt enum styles and test doubles."""

    enum_owner = getattr(QEvent, "Type", QEvent)
    event_type = getattr(enum_owner, attr_name, None)
    if event_type is None:
        event_type = getattr(QEvent, attr_name, None)
    if event_type is None:
        return fallback
    try:
        return int(event_type)
    except TypeError:
        return fallback


def _is_usable_qt_wrapper(candidate: object | None) -> bool:
    """Return whether one potential Qt wrapper is safe to call into."""

    if candidate is None:
        return False
    if _is_valid_shiboken_object is None:
        return True
    return bool(_is_valid_shiboken_object(candidate))


def _qt_object_type(candidate: object | None) -> str:
    """Return one stable object type label for structured popup logging."""

    if candidate is None:
        return "NoneType"
    return type(candidate).__name__


def _popup_log_context(owner: object | None, popup: object | None) -> dict[str, object]:
    """Build structured context for popup-toggle lifecycle logging."""

    return {
        "owner_type": _qt_object_type(owner),
        "popup_type": _qt_object_type(popup),
    }


class _PopupToggleMixin:
    """Track one attached popup and apply combo-box-like toggle semantics."""

    def _prime_popup_toggle_state(self) -> None:
        """Initialize popup tracking before the base widget constructor runs."""

        self._attached_popup: object | None = None
        self._attached_popup_marked_open = False
        self._suppress_next_popup_show = False
        self._closing_popup_from_toggle = False

    def _track_attached_popup(self, popup: object | None) -> None:
        """Register one popup instance for toggle-aware open and close tracking."""

        previous_popup = getattr(self, "_attached_popup", None)
        if previous_popup is not None and hasattr(previous_popup, "removeEventFilter"):
            previous_popup.removeEventFilter(self)

        self._attached_popup = popup
        self._attached_popup_marked_open = False

        log_debug(
            _LOGGER,
            "Updated tracked popup for toggle owner",
            popup_attached=popup is not None,
            **_popup_log_context(self, popup),
        )

        if popup is None:
            return

        if hasattr(popup, "installEventFilter"):
            popup.installEventFilter(self)

        self._connect_popup_lifecycle_signal(popup, "closedSignal")
        self._connect_popup_lifecycle_signal(popup, "destroyed")

    def _connect_popup_lifecycle_signal(
        self,
        popup: object,
        signal_name: str,
    ) -> None:
        """Connect one popup lifecycle signal back to the shared close tracker."""

        signal = getattr(popup, signal_name, None)
        if signal is None or not hasattr(signal, "connect"):
            return
        signal.connect(
            lambda *_args, tracked_popup=popup: self._on_tracked_popup_closed(
                tracked_popup
            )
        )

    def _on_tracked_popup_closed(self, popup: object) -> None:
        """Clear stale open state when the tracked popup closes or is destroyed."""

        if popup is not self._attached_popup:
            return

        self._attached_popup_marked_open = False
        if self._closing_popup_from_toggle:
            self._suppress_next_popup_show = False
            log_debug(
                _LOGGER,
                "Tracked popup closed from toggle action",
                suppress_next_popup_show=False,
                **_popup_log_context(self, popup),
            )
            return

        if not _is_usable_qt_wrapper(self):
            self._suppress_next_popup_show = False
            log_debug(
                _LOGGER,
                "Skipped popup-close suppression recompute for invalid owner",
                suppress_next_popup_show=False,
                **_popup_log_context(self, popup),
            )
            return

        self._suppress_next_popup_show = self._should_suppress_next_popup_show(popup)
        log_debug(
            _LOGGER,
            "Tracked popup closed and updated suppression state",
            popup_hide_by_system=bool(getattr(popup, "isHideBySystem", False)),
            suppress_next_popup_show=self._suppress_next_popup_show,
            **_popup_log_context(self, popup),
        )

    def _should_suppress_next_popup_show(self, popup: object) -> bool:
        """Return whether the next trigger release should be consumed after a close."""

        if sys.platform != "win32":
            return False
        if not bool(getattr(popup, "isHideBySystem", False)):
            return False
        return self._is_cursor_over_popup_trigger()

    def _is_cursor_over_popup_trigger(self) -> bool:
        """Return whether the cursor is currently over this wrapper's trigger area."""

        return self._widget_contains_cursor(self)

    @staticmethod
    def _widget_contains_cursor(widget: object) -> bool:
        """Return whether the supplied widget contains the global cursor position."""

        if not _is_usable_qt_wrapper(widget):
            log_debug(
                _LOGGER,
                "Skipped cursor hit-test for invalid popup trigger",
                widget_type=_qt_object_type(widget),
            )
            return False

        rect = getattr(widget, "rect", None)
        map_from_global = getattr(widget, "mapFromGlobal", None)
        if not callable(rect) or not callable(map_from_global):
            return False

        try:
            contains = getattr(rect(), "contains", None)
            if not callable(contains):
                return False
            return bool(contains(map_from_global(QCursor.pos())))
        except RuntimeError as error:
            log_debug(
                _LOGGER,
                "Popup trigger cursor hit-test failed during teardown",
                widget_type=_qt_object_type(widget),
                error=repr(error),
            )
            return False

    def _toggle_attached_popup(self, show_popup: Callable[[], None]) -> None:
        """Hide the current popup when open or invoke the inherited show path."""

        if self._suppress_next_popup_show:
            self._suppress_next_popup_show = False
            log_debug(
                _LOGGER,
                "Consumed suppressed popup show on trigger release",
                suppress_next_popup_show=False,
                **_popup_log_context(self, self._attached_popup),
            )
            return

        popup = self._attached_popup
        if popup is not None and self._is_attached_popup_open(popup):
            log_debug(
                _LOGGER,
                "Hiding tracked popup from toggle trigger",
                **_popup_log_context(self, popup),
            )
            self._hide_attached_popup(popup)
            self._attached_popup_marked_open = False
            return

        self._attached_popup_marked_open = popup is not None
        log_debug(
            _LOGGER,
            "Showing tracked popup from toggle trigger",
            popup_marked_open=self._attached_popup_marked_open,
            **_popup_log_context(self, popup),
        )
        show_popup()

    def _is_attached_popup_open(self, popup: object) -> bool:
        """Return whether the tracked popup is currently considered open."""

        if popup is not self._attached_popup:
            return False
        if self._attached_popup_marked_open:
            return True
        visible = getattr(popup, "isVisible", None)
        if not callable(visible):
            return False
        try:
            return bool(visible())
        except RuntimeError:
            self._attached_popup_marked_open = False
            return False

    def _hide_attached_popup(self, popup: object) -> None:
        """Hide or close the tracked popup without re-entering the show path."""

        hide = getattr(popup, "hide", None)
        if callable(hide):
            self._closing_popup_from_toggle = True
            try:
                hide()
            finally:
                self._closing_popup_from_toggle = False
            return
        close = getattr(popup, "close", None)
        if callable(close):
            self._closing_popup_from_toggle = True
            try:
                close()
            finally:
                self._closing_popup_from_toggle = False

    def eventFilter(self, watched: object, event: object) -> bool:
        """Clear tracked open state when the current popup hides or closes."""

        event_type = getattr(event, "type", None)
        if (
            watched is self._attached_popup
            and callable(event_type)
            and event_type()
            in {
                _event_type("Hide", 18),
                _event_type("Close", 19),
                _event_type("Destroy", 16),
            }
        ):
            self._on_tracked_popup_closed(watched)

        parent_event_filter = getattr(super(), "eventFilter", None)
        if callable(parent_event_filter):
            return bool(parent_event_filter(watched, event))
        return False


class _ToggleDropDownButtonMixin(_PopupToggleMixin):
    """Apply toggle semantics to QFluent dropdown tool buttons."""

    def setMenu(self, menu: object) -> None:
        """Attach one menu and register it with the shared popup tracker."""

        super().setMenu(menu)
        self._track_attached_popup(menu)

    def mouseReleaseEvent(self, event: object) -> None:
        """Forward base release handling and then toggle the attached menu."""

        ToolButton.mouseReleaseEvent(self, event)
        self._toggle_attached_popup(self._showMenu)


class _ToggleSplitButtonMixin(_PopupToggleMixin):
    """Apply toggle semantics to QFluent split-button drop arrows."""

    def _prime_split_toggle_state(self) -> None:
        """Initialize one-time drop-button rewiring state."""

        self._toggle_wired_drop_button: object | None = None

    def setFlyout(self, flyout: object) -> None:
        """Attach one flyout and register it with the shared popup tracker."""

        super().setFlyout(flyout)
        self._track_attached_popup(flyout)

    def setDropButton(self, button: object) -> None:
        """Replace the drop button and restore toggle-aware arrow wiring."""

        super().setDropButton(button)
        self._wire_toggle_drop_button()

    def _wire_toggle_drop_button(self) -> None:
        """Replace the inherited always-show handler on the drop arrow."""

        drop_button = getattr(self, "dropButton", None)
        if drop_button is None or drop_button is self._toggle_wired_drop_button:
            return

        clicked_signal = getattr(drop_button, "clicked", None)
        if clicked_signal is None:
            return

        disconnect = getattr(clicked_signal, "disconnect", None)
        if callable(disconnect):
            try:
                disconnect()
            except TypeError:
                for callback in (self.showFlyout, self._toggle_drop_flyout):
                    try:
                        disconnect(callback)
                    except (TypeError, RuntimeError, ValueError):
                        continue

        connect = getattr(clicked_signal, "connect", None)
        if callable(connect):
            connect(self.dropDownClicked)
            connect(self._toggle_drop_flyout)
            self._toggle_wired_drop_button = drop_button

    def _toggle_drop_flyout(self) -> None:
        """Toggle the tracked flyout instead of always reopening it."""

        self._toggle_attached_popup(self.showFlyout)

    def _is_cursor_over_popup_trigger(self) -> bool:
        """Return whether the cursor is currently over the drop-arrow trigger."""

        return self._widget_contains_cursor(getattr(self, "dropButton", None))


class ToggleDropDownToolButton(_ToggleDropDownButtonMixin, DropDownToolButton):
    """Close the attached menu on repeated clicks instead of reopening it."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the runtime widget and shared popup tracking state."""

        self._prime_popup_toggle_state()
        super().__init__(*args, **kwargs)


class ToggleTransparentDropDownToolButton(
    _ToggleDropDownButtonMixin,
    TransparentDropDownToolButton,
):
    """Close the attached menu on repeated clicks for transparent dropdown tools."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the runtime widget and shared popup tracking state."""

        self._prime_popup_toggle_state()
        super().__init__(*args, **kwargs)


class ToggleSplitToolButton(_ToggleSplitButtonMixin, SplitToolButton):
    """Close the attached flyout on repeated drop-arrow clicks."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the runtime widget, popup tracking, and arrow rewiring."""

        self._prime_popup_toggle_state()
        self._prime_split_toggle_state()
        super().__init__(*args, **kwargs)
        self._wire_toggle_drop_button()


class TogglePrimarySplitPushButton(_ToggleSplitButtonMixin, PrimarySplitPushButton):
    """Close the attached flyout on repeated primary-split drop-arrow clicks."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the runtime widget, popup tracking, and arrow rewiring."""

        self._prime_popup_toggle_state()
        self._prime_split_toggle_state()
        super().__init__(*args, **kwargs)
        self._wire_toggle_drop_button()


__all__ = [
    "ToggleDropDownToolButton",
    "TogglePrimarySplitPushButton",
    "ToggleSplitToolButton",
    "ToggleTransparentDropDownToolButton",
]
