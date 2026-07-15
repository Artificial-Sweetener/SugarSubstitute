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

"""Construct Output canvas navigation widgets without controller wiring."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget
from qfluentwidgets import SegmentedItem, SegmentedWidget  # type: ignore[import-untyped]

from substitute.presentation.canvas.shared.canvas_nav_picker import CanvasNavPicker
from substitute.presentation.canvas.shared.output_set_picker import OutputSetPicker


@dataclass(frozen=True, slots=True)
class OutputNavigationWidgets:
    """Group Output navigation widgets by their shared construction lifetime."""

    tabbar_container: QWidget
    tabbar_bg: QLabel
    scene_selector_button: SegmentedItem
    set_selector_button: SegmentedItem
    source_selector_button: SegmentedItem
    tabbar: SegmentedWidget
    set_picker: OutputSetPicker
    scene_picker: CanvasNavPicker
    source_picker: CanvasNavPicker
    comparison_nav_container: QWidget
    comparison_nav_bg: QLabel
    comparison_scene_selector_button: SegmentedItem
    comparison_set_selector_button: SegmentedItem
    comparison_source_selector_button: SegmentedItem


def create_output_navigation_widgets(
    parent: QWidget,
    *,
    scene_selector_min_width: int,
    source_selector_min_width: int,
) -> OutputNavigationWidgets:
    """Create base and comparison navigation chrome for an Output host."""

    tabbar_container = QWidget(parent)
    tabbar_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    tabbar_container.setStyleSheet("background: transparent; border: none;")
    tabbar_container.setGeometry(0, 0, 200, 60)

    tabbar_bg = QLabel(tabbar_container)
    tabbar_bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    tabbar_bg.lower()
    tabbar_bg.show()

    scene_selector_button = SegmentedItem("All", tabbar_container)
    scene_selector_button.setCursor(Qt.CursorShape.PointingHandCursor)
    scene_selector_button.setMinimumSize(scene_selector_min_width, 28)
    scene_selector_button.hide()

    set_selector_button = SegmentedItem("1", tabbar_container)
    set_selector_button.setCursor(Qt.CursorShape.PointingHandCursor)
    set_selector_button.setMinimumSize(34, 28)
    set_selector_button.hide()

    source_selector_button = SegmentedItem("Output", tabbar_container)
    source_selector_button.setCursor(Qt.CursorShape.PointingHandCursor)
    source_selector_button.setMinimumSize(source_selector_min_width, 28)
    source_selector_button.hide()

    tabbar = SegmentedWidget(tabbar_container)
    tabbar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    tabbar.raise_()
    tabbar.setMinimumHeight(28)
    tabbar.setMinimumWidth(40)

    comparison_nav_container = QWidget(parent)
    comparison_nav_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    comparison_nav_container.setStyleSheet("background: transparent; border: none;")
    comparison_nav_bg = QLabel(comparison_nav_container)
    comparison_nav_bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    comparison_nav_bg.lower()

    comparison_scene_selector_button = SegmentedItem("All", comparison_nav_container)
    comparison_scene_selector_button.setCursor(Qt.CursorShape.PointingHandCursor)
    comparison_scene_selector_button.setMinimumSize(scene_selector_min_width, 28)
    comparison_set_selector_button = SegmentedItem("1", comparison_nav_container)
    comparison_set_selector_button.setCursor(Qt.CursorShape.PointingHandCursor)
    comparison_set_selector_button.setMinimumSize(34, 28)
    comparison_source_selector_button = SegmentedItem(
        "Output", comparison_nav_container
    )
    comparison_source_selector_button.setCursor(Qt.CursorShape.PointingHandCursor)
    comparison_source_selector_button.setMinimumSize(source_selector_min_width, 28)
    comparison_nav_container.hide()

    return OutputNavigationWidgets(
        tabbar_container=tabbar_container,
        tabbar_bg=tabbar_bg,
        scene_selector_button=scene_selector_button,
        set_selector_button=set_selector_button,
        source_selector_button=source_selector_button,
        tabbar=tabbar,
        set_picker=OutputSetPicker(parent),
        scene_picker=CanvasNavPicker(parent),
        source_picker=CanvasNavPicker(parent),
        comparison_nav_container=comparison_nav_container,
        comparison_nav_bg=comparison_nav_bg,
        comparison_scene_selector_button=comparison_scene_selector_button,
        comparison_set_selector_button=comparison_set_selector_button,
        comparison_source_selector_button=comparison_source_selector_button,
    )


__all__ = ["OutputNavigationWidgets", "create_output_navigation_widgets"]
