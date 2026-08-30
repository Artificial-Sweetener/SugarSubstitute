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
from typing import TYPE_CHECKING, Callable, Protocol, cast

from PySide6.QtCore import QEvent
from PySide6.QtGui import QCursor
from shiboken6 import isValid as _is_valid_shiboken_object

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    class _SignalLike(Protocol):
        """Describe the QFluent signal operations used by the adapters."""

        def connect(self, callback: object) -> None:
            """Connect one callback or relay."""

        def disconnect(self, callback: object | None = None) -> None:
            """Disconnect one callback or all callbacks."""

        def emit(self, *args: object) -> None:
            """Emit one signal payload."""

    class _ButtonPart(QWidget):
        """Describe a real split-button child at the untyped package boundary."""

        clicked: _SignalLike

    class ToolButton(QWidget):
        """Describe the typed ToolButton method used by the mixin."""

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Accept the constructor overloads owned by QFluent."""

        def mouseReleaseEvent(self, event: object) -> None:
            """Forward one release event through the QFluent base."""

    class DropDownToolButton(ToolButton):
        """Describe the dropdown methods supplied by QFluent."""

        def setMenu(self, menu: object) -> None:
            """Attach one popup menu."""

        def _showMenu(self) -> None:
            """Show the attached popup menu."""

    class TransparentDropDownToolButton(DropDownToolButton):
        """Describe the transparent dropdown QFluent variant."""

    class _SplitButtonBase(QWidget):
        """Describe the split-button surface used by toggle adapters."""

        dropButton: _ButtonPart
        dropDownClicked: _SignalLike
        button: _ButtonPart
        clicked: _SignalLike

        def __init__(self, *args: object, **kwargs: object) -> None:
            """Accept the constructor overloads owned by QFluent."""

        def setFlyout(self, flyout: object) -> None:
            """Attach one popup flyout."""

        def setDropButton(self, button: object) -> None:
            """Replace the drop-arrow child."""

        def showFlyout(self) -> None:
            """Show the attached popup flyout."""

    class SplitToolButton(_SplitButtonBase):
        """Describe the QFluent split tool-button variant."""

    class PrimarySplitPushButton(_SplitButtonBase):
        """Describe the QFluent primary split-button variant."""

else:
    from qfluentwidgets import (  # type: ignore[import-untyped]
        DropDownToolButton,
        PrimarySplitPushButton,
        SplitToolButton,
        ToolButton,
        TransparentDropDownToolButton,
    )

from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.widgets.menu_buttons")


def _is_usable_qt_wrapper(candidate: object | None) -> bool:
    """Return whether one potential Qt wrapper is safe to call into."""

    if candidate is None:
        return False
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
                QEvent.Type.Hide,
                QEvent.Type.Close,
                QEvent.Type.Destroy,
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

        cast(DropDownToolButton, super()).setMenu(menu)
        self._track_attached_popup(menu)

    def mouseReleaseEvent(self, event: object) -> None:
        """Forward base release handling and then toggle the attached menu."""

        runtime_button = cast(DropDownToolButton, self)
        ToolButton.mouseReleaseEvent(runtime_button, event)
        self._toggle_attached_popup(runtime_button._showMenu)


class _ToggleSplitButtonMixin(_PopupToggleMixin):
    """Apply toggle semantics to QFluent split-button drop arrows."""

    def _prime_split_toggle_state(self) -> None:
        """Initialize one-time drop-button rewiring state."""

        self._toggle_wired_drop_button: object | None = None

    def setFlyout(self, flyout: object) -> None:
        """Attach one flyout and register it with the shared popup tracker."""

        cast("_SplitButtonBase", super()).setFlyout(flyout)
        self._track_attached_popup(flyout)

    def setDropButton(self, button: object) -> None:
        """Replace the drop button and restore toggle-aware arrow wiring."""

        cast("_SplitButtonBase", super()).setDropButton(button)
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
                for callback in (
                    cast("_SplitButtonBase", self).showFlyout,
                    self._toggle_drop_flyout,
                ):
                    try:
                        disconnect(callback)
                    except (TypeError, RuntimeError, ValueError):
                        continue

        connect = getattr(clicked_signal, "connect", None)
        if callable(connect):
            connect(cast("_SplitButtonBase", self).dropDownClicked)
            connect(self._toggle_drop_flyout)
            self._toggle_wired_drop_button = drop_button

    def _toggle_drop_flyout(self) -> None:
        """Toggle the tracked flyout instead of always reopening it."""

        self._toggle_attached_popup(cast("_SplitButtonBase", self).showFlyout)

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
