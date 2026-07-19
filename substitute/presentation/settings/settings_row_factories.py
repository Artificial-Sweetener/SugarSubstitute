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

"""Build shared Fluent Settings row primitives without feature policy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    ComboBox,
    IconWidget,
    IndicatorPosition,
    SwitchButton,
)

from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_ICON_MAX_SIZE,
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)


def build_switch_settings_row(
    *,
    parent: QWidget,
    icon: Any,
    title: str,
    description: str,
    checked: bool,
    on_changed: Callable[[bool], object],
) -> InteractiveSettingsCard:
    """Create a standard clickable switch Settings row."""

    switch = SwitchButton("Off", parent, indicatorPos=IndicatorPosition.RIGHT)
    switch.setOnText("On")
    switch.setOffText("Off")
    switch.setChecked(checked)
    switch.checkedChanged.connect(on_changed)
    row = InteractiveSettingsCard(
        visual_widget=build_settings_icon_widget(icon, parent),
        title=title,
        description=description,
        trailing_widget=switch,
        reserve_visual_space=True,
        parent=parent,
    )
    row.activated.connect(lambda: switch.setChecked(not switch.isChecked()))
    return row


def build_combo_settings_row(
    *,
    parent: QWidget,
    icon: Any,
    title: str,
    description: str,
    options: tuple[tuple[str, object], ...],
    selected: object,
    on_changed: Callable[[object], object],
    enabled: bool = True,
    extra_button: QWidget | None = None,
) -> SettingsCard:
    """Create a standard combo-box Settings row."""

    combo = ComboBox(parent)
    configure_settings_field_width(combo, preferred_width=180)
    for label, value in options:
        combo.addItem(label, userData=value)
    for index in range(combo.count()):
        if combo.itemData(index) == selected:
            combo.setCurrentIndex(index)
            break
    combo.setEnabled(enabled)
    combo.currentIndexChanged.connect(lambda _index: on_changed(combo.currentData()))
    controls = (
        SettingsControlGroup(combo, extra_button, parent=parent)
        if extra_button is not None
        else combo
    )
    return SettingsCard(
        visual_widget=build_settings_icon_widget(icon, parent),
        title=title,
        description=description,
        trailing_widget=controls,
        reserve_visual_space=True,
        wrap_threshold=640,
        parent=parent,
    )


def build_settings_icon_widget(icon: Any, parent: QWidget | None) -> IconWidget:
    """Create one fixed-size Settings row icon."""

    widget = IconWidget(icon, parent)
    widget.setFixedSize(SETTINGS_CARD_ICON_MAX_SIZE, SETTINGS_CARD_ICON_MAX_SIZE)
    return widget


def build_named_settings_icon_widget(
    icon: Any,
    object_name: str,
    parent: QWidget | None,
) -> IconWidget:
    """Create one named fixed-size Settings row icon."""

    widget = build_settings_icon_widget(icon, parent)
    widget.setObjectName(object_name)
    return widget


__all__ = [
    "build_combo_settings_row",
    "build_named_settings_icon_widget",
    "build_settings_icon_widget",
    "build_switch_settings_row",
]
