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


from typing import TYPE_CHECKING, Protocol, cast

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QAbstractButton

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

    class PushButton(QWidget):
        """Describe the typed push-button method used by the mixin."""

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

    class DropDownPushButton(PushButton):
        """Describe the dropdown push-button methods supplied by QFluent."""

        def setMenu(self, menu: object) -> None:
            """Attach one popup menu."""

        def _showMenu(self) -> None:
            """Show the attached popup menu."""

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
        DropDownPushButton,
        PrimarySplitPushButton,
        PushButton,
        SplitToolButton,
        ToolButton,
        TransparentDropDownToolButton,
    )

from substitute.presentation.widgets.menu_button_controller import (
    MenuButtonController,
)


class _ToggleDropDownButtonMixin:
    """Delegate QFluent dropdown menu lifecycle to the shared controller."""

    def _initialize_menu_controller(self) -> None:
        """Bind the concrete dropdown trigger after its Qt base is initialized."""

        button = cast(QAbstractButton, self)
        self._menu_controller = MenuButtonController(
            button,
            menu_position=lambda: button.mapToGlobal(QPoint(0, button.height())),
            connect_clicked=False,
        )

    def setMenu(self, menu: object) -> None:
        """Attach one menu through QFluent and the shared lifecycle owner."""

        cast(DropDownToolButton, super()).setMenu(menu)
        self._menu_controller.set_menu(menu)

    def set_popup_menu(self, menu: object) -> None:
        """Expose the architecture-approved menu attachment boundary."""

        self.setMenu(menu)

    def _toggle_menu(self, show_menu: object) -> None:
        """Toggle the attached menu through its QFluent show operation."""

        if callable(show_menu):
            self._menu_controller.trigger_with(show_menu)


class _ToggleDropDownToolButtonMixin(_ToggleDropDownButtonMixin):
    """Adapt QFluent tool-button release delivery to shared menu ownership."""

    def mouseReleaseEvent(self, event: object) -> None:
        """Forward base release handling and then toggle the attached menu."""

        runtime_button = cast(DropDownToolButton, self)
        ToolButton.mouseReleaseEvent(runtime_button, event)
        self._toggle_menu(runtime_button._showMenu)


class _ToggleDropDownPushButtonMixin(_ToggleDropDownButtonMixin):
    """Adapt QFluent push-button release delivery to shared menu ownership."""

    def mouseReleaseEvent(self, event: object) -> None:
        """Forward base release handling and then toggle the attached menu."""

        runtime_button = cast(DropDownPushButton, self)
        PushButton.mouseReleaseEvent(runtime_button, event)
        self._toggle_menu(runtime_button._showMenu)


class _ToggleSplitButtonMixin:
    """Delegate QFluent split-arrow flyout lifecycle to the shared controller."""

    def _prime_split_toggle_state(self) -> None:
        """Initialize one-time drop-button rewiring state."""

        self._toggle_wired_drop_button: object | None = None
        self._attached_flyout: object | None = None
        self._menu_controller: MenuButtonController | None = None

    def setFlyout(self, flyout: object) -> None:
        """Attach one flyout through QFluent and the shared lifecycle owner."""

        cast("_SplitButtonBase", super()).setFlyout(flyout)
        self._attached_flyout = flyout
        if self._menu_controller is not None:
            self._menu_controller.set_menu(flyout)

    def set_popup_flyout(self, flyout: object) -> None:
        """Expose the architecture-approved flyout attachment boundary."""

        self.setFlyout(flyout)

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
            trigger = cast(QAbstractButton, drop_button)
            self._menu_controller = MenuButtonController(
                trigger,
                menu_position=lambda: trigger.mapToGlobal(QPoint(0, trigger.height())),
                connect_clicked=False,
            )
            if self._attached_flyout is not None:
                self._menu_controller.set_menu(self._attached_flyout)
            connect(cast("_SplitButtonBase", self).dropDownClicked)
            connect(self._toggle_drop_flyout)
            self._toggle_wired_drop_button = drop_button

    def _toggle_drop_flyout(self) -> None:
        """Toggle the tracked flyout instead of always reopening it."""

        if self._menu_controller is not None:
            self._menu_controller.trigger_with(
                cast("_SplitButtonBase", self).showFlyout
            )


class ToggleDropDownToolButton(
    _ToggleDropDownToolButtonMixin,
    DropDownToolButton,
):
    """Close the attached menu on repeated clicks instead of reopening it."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the runtime widget and shared popup tracking state."""

        super().__init__(*args, **kwargs)
        self._initialize_menu_controller()


class ToggleTransparentDropDownToolButton(
    _ToggleDropDownToolButtonMixin,
    TransparentDropDownToolButton,
):
    """Close the attached menu on repeated clicks for transparent dropdown tools."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the runtime widget and shared popup tracking state."""

        super().__init__(*args, **kwargs)
        self._initialize_menu_controller()


class ToggleDropDownPushButton(
    _ToggleDropDownPushButtonMixin,
    DropDownPushButton,
):
    """Close an attached push-button menu on repeated clicks."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the QFluent button and shared lifecycle controller."""

        super().__init__(*args, **kwargs)
        self._initialize_menu_controller()


class ToggleSplitToolButton(_ToggleSplitButtonMixin, SplitToolButton):
    """Close the attached flyout on repeated drop-arrow clicks."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the runtime widget, popup tracking, and arrow rewiring."""

        self._prime_split_toggle_state()
        super().__init__(*args, **kwargs)
        self._wire_toggle_drop_button()


class TogglePrimarySplitPushButton(_ToggleSplitButtonMixin, PrimarySplitPushButton):
    """Close the attached flyout on repeated primary-split drop-arrow clicks."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Initialize the runtime widget, popup tracking, and arrow rewiring."""

        self._prime_split_toggle_state()
        super().__init__(*args, **kwargs)
        self._wire_toggle_drop_button()


__all__ = [
    "ToggleDropDownPushButton",
    "ToggleDropDownToolButton",
    "TogglePrimarySplitPushButton",
    "ToggleSplitToolButton",
    "ToggleTransparentDropDownToolButton",
]
