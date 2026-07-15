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

"""Own shared popup-menu toggle behavior for shell buttons."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QAbstractButton, QApplication
from qfluentwidgets import MenuAnimationType  # type: ignore[import-untyped]


def left_mouse_button_is_down() -> bool:
    """Return whether the application currently reports a held left button."""

    return bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)


class ShellMenuButtonController(QObject):
    """Synchronize one shell button with its popup menu visibility."""

    def __init__(
        self,
        button: QAbstractButton,
        *,
        menu_position: Callable[[], QPoint],
        animation_type: MenuAnimationType = MenuAnimationType.DROP_DOWN,
        qfluent_drop_down_vertical_offset: int = 0,
    ) -> None:
        """Create a controller that reacts to normal button click delivery."""

        super().__init__(button)
        self._button = button
        self._menu_position = menu_position
        self._animation_type = animation_type
        self._qfluent_drop_down_vertical_offset = qfluent_drop_down_vertical_offset
        self._menu: object | None = None
        self._observed_menu: QObject | None = None
        self._menu_open = False
        self._closing_from_controller = False
        self._suppress_next_owner_click = False
        self._consume_owner_click_release = False
        self._application_filter_installed = False
        self._button.installEventFilter(self)

    def set_menu(self, menu: object) -> None:
        """Attach the menu and observe external menu closure."""

        self._remove_menu_filter()
        self._menu = menu
        self._install_menu_filter(menu)
        self._connect_menu_close_signal(menu)

    def menu(self) -> object | None:
        """Return the currently attached menu."""

        return self._menu

    def handle_button_clicked(self, checked: bool = False) -> None:
        """Open or close the menu after the button emits its normal click signal."""

        _ = checked
        if self._suppress_next_owner_click:
            self._suppress_next_owner_click = False
            self._sync_application_filter()
            self._set_menu_open(False)
            return

        if self.is_menu_open():
            self.close_menu_if_open()
            return

        self._open_menu()

    def trigger(self) -> None:
        """Toggle the attached menu for programmatic callers."""

        if self.close_menu_if_open():
            return
        self._open_menu()

    def is_menu_open(self) -> bool:
        """Return whether the controller has a confirmed visible menu."""

        return self._menu_open

    def close_menu_if_open(self) -> bool:
        """Close the attached menu when it is visible or believed open."""

        menu = self._menu
        menu_visible = self._menu_is_visible()
        had_open_state = self._menu_open or menu_visible
        if menu is None or not had_open_state:
            self._set_menu_open(False)
            return False
        hide = getattr(menu, "hide", None)
        close = getattr(menu, "close", None)
        if callable(hide) or callable(close):
            self._closing_from_controller = True
            try:
                if callable(hide):
                    hide()
                elif callable(close):
                    close()
            finally:
                self._record_controller_close()
                self._closing_from_controller = False
            return True

        self._record_controller_close()
        return had_open_state

    def _open_menu(self) -> None:
        """Open the attached menu at the controller-owned position."""

        menu = self._menu
        execute = getattr(menu, "exec", None)
        if not callable(execute):
            self._set_menu_open(False)
            return
        position, animation_type = self._resolve_menu_execution(menu)
        execute(position, aniType=animation_type)
        self._set_menu_open(self._menu_is_visible())

    def _resolve_menu_execution(
        self,
        menu: object,
    ) -> tuple[QPoint, MenuAnimationType]:
        """Return a left-anchored QFluent popup position and animation type."""

        view = getattr(menu, "view", None)
        height_for_animation = getattr(view, "heightForAnimation", None)
        if view is None or not callable(height_for_animation):
            return self._menu_position(), self._animation_type

        self._prepare_menu_size(menu, view)
        # QFluent treats exec().x as the visible list edge and subtracts its
        # transparent layout margin when moving the popup window.
        drop_down_position = self._button.mapToGlobal(
            QPoint(
                0,
                self._button.height() + self._qfluent_drop_down_vertical_offset,
            )
        )
        pull_up_position = self._button.mapToGlobal(QPoint(0, 0))
        drop_down_height = int(
            height_for_animation(drop_down_position, MenuAnimationType.DROP_DOWN)
        )
        pull_up_height = int(
            height_for_animation(pull_up_position, MenuAnimationType.PULL_UP)
        )
        if drop_down_height >= pull_up_height:
            self._adjust_menu_view_for_animation(
                view,
                drop_down_position,
                MenuAnimationType.DROP_DOWN,
            )
            return drop_down_position, MenuAnimationType.DROP_DOWN

        self._adjust_menu_view_for_animation(
            view,
            pull_up_position,
            MenuAnimationType.PULL_UP,
        )
        return pull_up_position, MenuAnimationType.PULL_UP

    def _prepare_menu_size(self, menu: object, view: object) -> None:
        """Apply QFluent dropdown sizing before positioning a menu."""

        set_minimum_width = getattr(view, "setMinimumWidth", None)
        if callable(set_minimum_width):
            set_minimum_width(self._button.width())

        adjust_view_size = getattr(view, "adjustSize", None)
        if callable(adjust_view_size):
            adjust_view_size()

        adjust_menu_size = getattr(menu, "adjustSize", None)
        if callable(adjust_menu_size):
            adjust_menu_size()

    def _adjust_menu_view_for_animation(
        self,
        view: object,
        position: QPoint,
        animation_type: MenuAnimationType,
    ) -> None:
        """Resize the QFluent menu view for the selected popup direction."""

        adjust_size = getattr(view, "adjustSize", None)
        if not callable(adjust_size):
            return
        try:
            adjust_size(position, animation_type)
        except TypeError:
            adjust_size()

    def _connect_menu_close_signal(self, menu: object) -> None:
        """Listen to menu close notifications when the menu exposes them."""

        for signal_name in ("aboutToHide", "closedSignal"):
            signal = getattr(menu, signal_name, None)
            connect = getattr(signal, "connect", None)
            if callable(connect):
                connect(
                    lambda *_args, tracked_menu=menu: self._mark_menu_closed(
                        tracked_menu
                    )
                )

    def _mark_menu_closed(self, menu: object | None = None) -> None:
        """Return the button to unchecked state when the popup closes elsewhere."""

        if self._closing_from_controller:
            return

        self._set_menu_open(False)
        if self._should_suppress_next_owner_click(menu):
            self._suppress_next_owner_click = True
            self._sync_application_filter()
            return
        self._suppress_next_owner_click = False
        self._sync_application_filter()

    def _should_suppress_next_owner_click(self, menu: object | None) -> bool:
        """Return whether a popup close belongs to an owner-button click."""

        if not self._cursor_is_over_button():
            return False
        return left_mouse_button_is_down() or bool(
            getattr(menu, "isHideBySystem", False)
        )

    def _record_controller_close(self) -> None:
        """Record a close initiated by this controller."""

        self._suppress_next_owner_click = False
        self._set_menu_open(False)
        self._sync_application_filter()

    def _sync_application_filter(self) -> None:
        """Install the app filter exactly when menu-click ownership needs it."""

        if (
            self._menu_open
            or self._suppress_next_owner_click
            or self._consume_owner_click_release
        ):
            self._install_application_filter()
        else:
            self._remove_application_filter()

    def _install_application_filter(self) -> None:
        """Observe application mouse events while menu ownership is active."""

        app = QApplication.instance()
        if app is not None and not self._application_filter_installed:
            app.installEventFilter(self)
            self._application_filter_installed = True

    def _remove_application_filter(self) -> None:
        """Stop observing application-level release events."""

        app = QApplication.instance()
        if app is not None and self._application_filter_installed:
            app.removeEventFilter(self)
        self._application_filter_installed = False

    def _install_menu_filter(self, menu: object) -> None:
        """Observe popup lifecycle events that may not emit a signal."""

        if isinstance(menu, QObject):
            menu.installEventFilter(self)
            self._observed_menu = menu

    def _remove_menu_filter(self) -> None:
        """Stop observing the previously attached popup."""

        if self._observed_menu is not None:
            try:
                self._observed_menu.removeEventFilter(self)
            except RuntimeError:
                pass
        self._observed_menu = None

    def eventFilter(self, watched: object, event: object) -> bool:
        """Synchronize popup close events and owner-click suppression."""

        if (
            self._application_filter_installed
            and isinstance(event, QEvent)
            and event.type()
            in {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
            }
            and not self._button.isVisible()
        ):
            self.close_menu_if_open()
            self._consume_owner_click_release = False
            self._suppress_next_owner_click = False
            self._set_menu_open(False)
            self._sync_application_filter()
            return False

        if self._should_consume_owner_press(event):
            self._consume_owner_click_release = True
            self._suppress_next_owner_click = False
            self.close_menu_if_open()
            self._button.setDown(False)
            self._sync_application_filter()
            return True

        if self._should_consume_owner_release(event):
            self._consume_owner_click_release = False
            self._suppress_next_owner_click = False
            self._button.setDown(False)
            self._sync_application_filter()
            return True

        if (
            watched is self._button
            and isinstance(event, QEvent)
            and event.type()
            in {
                QEvent.Type.Hide,
                QEvent.Type.Close,
                QEvent.Type.Destroy,
            }
        ):
            self.close_menu_if_open()
            self._consume_owner_click_release = False
            self._suppress_next_owner_click = False
            self._set_menu_open(False)
            self._sync_application_filter()

        if (
            watched is self._observed_menu
            and isinstance(event, QEvent)
            and event.type()
            in {
                QEvent.Type.Hide,
                QEvent.Type.Close,
                QEvent.Type.Destroy,
            }
        ):
            self._mark_menu_closed(watched)
        if (
            self._suppress_next_owner_click
            and watched is not self._button
            and isinstance(event, QEvent)
            and event.type() == QEvent.Type.MouseButtonRelease
        ):
            self._suppress_next_owner_click = False
            self._sync_application_filter()
        return False

    def _should_consume_owner_press(self, event: object) -> bool:
        """Return whether the current mouse press is the menu-closing owner click."""

        if not isinstance(event, QEvent):
            return False
        if event.type() != QEvent.Type.MouseButtonPress:
            return False
        if not self._event_uses_left_button(event):
            return False
        if not self._event_is_over_button(event):
            return False
        return self._menu_open or self._suppress_next_owner_click

    def _should_consume_owner_release(self, event: object) -> bool:
        """Return whether a consumed owner press should also consume its release."""

        if not self._consume_owner_click_release:
            return False
        if not isinstance(event, QEvent):
            return False
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False
        return self._event_uses_left_button(event)

    def _event_uses_left_button(self, event: object) -> bool:
        """Return whether a generic Qt mouse event belongs to the left button."""

        button = getattr(event, "button", None)
        if not callable(button):
            return True
        return bool(button() == Qt.MouseButton.LeftButton)

    def _event_is_over_button(self, event: object) -> bool:
        """Return whether a mouse event position falls inside the owner button."""

        global_position = getattr(event, "globalPosition", None)
        if callable(global_position):
            point = global_position()
            to_point = getattr(point, "toPoint", None)
            if callable(to_point):
                return self._global_point_is_over_button(to_point())

        global_pos = getattr(event, "globalPos", None)
        if callable(global_pos):
            return self._global_point_is_over_button(global_pos())

        return self._cursor_is_over_button()

    def _menu_is_visible(self) -> bool:
        """Return whether the attached menu reports visible."""

        menu = self._menu
        if menu is None:
            return False
        is_visible = getattr(menu, "isVisible", None)
        return bool(is_visible()) if callable(is_visible) else False

    def _cursor_is_over_button(self) -> bool:
        """Return whether the current cursor position is inside the owner button."""

        return self._global_point_is_over_button(QCursor.pos())

    def _global_point_is_over_button(self, global_point: QPoint) -> bool:
        """Return whether one global point is inside the owner button."""

        local_cursor = self._button.mapFromGlobal(global_point)
        if not self._button.rect().contains(local_cursor):
            return False
        hit_button = getattr(self._button, "hitButton", None)
        return bool(hit_button(local_cursor)) if callable(hit_button) else True

    def _set_menu_open(self, menu_open: bool) -> None:
        """Set confirmed menu-open state and repaint the owner button."""

        if self._menu_open == menu_open:
            return
        self._menu_open = menu_open
        self._sync_application_filter()
        self._button.update()


__all__ = [
    "ShellMenuButtonController",
    "left_mouse_button_is_down",
]
