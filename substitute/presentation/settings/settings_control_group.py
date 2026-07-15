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

"""Provide shared width-aware trailing controls for Settings rows."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QBoxLayout, QSizePolicy, QWidget

from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_TRAILING_MIN_WIDTH,
    SettingsCardLayoutMode,
)

SettingsControlGroupMode = Literal["horizontal", "vertical"]
_QT_MAX_WIDGET_SIZE = 16777215
_PREFERRED_WIDTH_PROPERTY = "settingsPreferredWidth"


class SettingsControlGroup(QWidget):
    """Arrange Settings row controls with width-aware wrapping."""

    def __init__(
        self,
        *widgets: QWidget,
        spacing: int = 8,
        parent: QWidget | None = None,
    ) -> None:
        """Create a control group with horizontal default placement."""

        super().__init__(parent)
        self._widgets = tuple(widgets)
        self._spacing = spacing
        self._mode: SettingsControlGroupMode = "horizontal"
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setMinimumWidth(SETTINGS_CARD_TRAILING_MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(self._spacing)
        for widget in self._widgets:
            widget.setParent(self)
            self._layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
        self._apply_layout_mode()

    def set_settings_card_layout_mode(self, mode: SettingsCardLayoutMode) -> None:
        """Apply the SettingsCard width mode to this compound content."""

        self.set_layout_mode("horizontal" if mode == "wide" else "vertical")

    def set_layout_mode(self, mode: SettingsControlGroupMode) -> None:
        """Switch between horizontal and vertical control placement."""

        if self._mode == mode:
            return
        self._mode = mode
        self._apply_layout_mode()

    def layout_mode(self) -> SettingsControlGroupMode:
        """Return the active group layout mode."""

        return self._mode

    def sizeHint(self) -> QSize:
        """Return a mode-aware preferred size using configured field widths."""

        if self._mode == "vertical":
            return QSize(
                max(
                    (_preferred_widget_width(widget) for widget in self._widgets),
                    default=0,
                ),
                sum(_effective_widget_height(widget) for widget in self._widgets)
                + self._spacing * max(0, len(self._widgets) - 1),
            )
        return QSize(
            sum(_preferred_widget_width(widget) for widget in self._widgets)
            + self._spacing * max(0, len(self._widgets) - 1),
            max(
                (_effective_widget_height(widget) for widget in self._widgets),
                default=0,
            ),
        )

    def minimumSizeHint(self) -> QSize:
        """Return the smallest useful group size for wrapped Settings rows."""

        if self._mode == "vertical":
            return QSize(
                max((widget.minimumWidth() for widget in self._widgets), default=0),
                sum(_effective_widget_height(widget) for widget in self._widgets)
                + self._spacing * max(0, len(self._widgets) - 1),
            )
        return QSize(
            sum(widget.minimumWidth() for widget in self._widgets)
            + self._spacing * max(0, len(self._widgets) - 1),
            max(
                (_effective_widget_height(widget) for widget in self._widgets),
                default=0,
            ),
        )

    def _apply_layout_mode(self) -> None:
        """Apply orientation and sizing for the active layout mode."""

        if self._mode == "horizontal":
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self.setMaximumWidth(_QT_MAX_WIDGET_SIZE)
            self._layout.setDirection(QBoxLayout.Direction.LeftToRight)
            alignment = Qt.AlignmentFlag.AlignVCenter
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setMaximumWidth(_QT_MAX_WIDGET_SIZE)
            self._layout.setDirection(QBoxLayout.Direction.TopToBottom)
            alignment = Qt.AlignmentFlag.AlignLeft
        for index in range(self._layout.count()):
            item = self._layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is not None:
                self._layout.setAlignment(widget, alignment)
        self.setMinimumHeight(self.minimumSizeHint().height())


def configure_settings_field_width(
    widget: QWidget,
    *,
    preferred_width: int,
    minimum_width: int = SETTINGS_CARD_TRAILING_MIN_WIDTH,
) -> None:
    """Configure a Settings field with a shrinkable preferred width."""

    widget.setMinimumWidth(minimum_width)
    widget.setMaximumWidth(preferred_width)
    widget.setProperty(_PREFERRED_WIDTH_PROPERTY, preferred_width)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


def _preferred_widget_width(widget: QWidget) -> int:
    """Return the preferred Settings width for one child widget."""

    preferred_width = widget.property(_PREFERRED_WIDTH_PROPERTY)
    if isinstance(preferred_width, int):
        return preferred_width
    return widget.sizeHint().width()


def _effective_widget_height(widget: QWidget) -> int:
    """Return the non-clipping height required by one child widget."""

    return max(
        widget.minimumHeight(),
        widget.minimumSizeHint().height(),
        widget.sizeHint().height(),
    )


__all__ = [
    "SettingsControlGroup",
    "SettingsControlGroupMode",
    "configure_settings_field_width",
]
