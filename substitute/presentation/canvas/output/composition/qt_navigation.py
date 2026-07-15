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

"""Compose Output navigation widgets with their feature controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtWidgets import QWidget

from substitute.presentation.canvas.output.composition.navigation import (
    OutputCanvasPickerHost,
    output_navigation_controller_for_host,
    output_picker_controller_for_host,
    output_source_tab_selection_for_host,
    output_source_tabs_controller_for_host,
)
from substitute.presentation.canvas.output.composition.runtime_types import (
    OutputNavigationRuntime,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    selector_width_for_widget_text,
)
from substitute.presentation.canvas.output.output_canvas_navigation_chrome import (
    update_output_tabbar_container,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
    sync_output_source_selector_button,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
    visible_output_compare_state,
)
from substitute.presentation.widgets.cursor_tooltip_filter import (
    install_cursor_tooltip_filter,
)

if TYPE_CHECKING:
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas

_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28


def compose_output_navigation_runtime(
    host: OutputCanvas,
    *,
    compare_controller: OutputCompareController,
) -> OutputNavigationRuntime:
    """Compose tab selection, source tabs, pickers, and navigation signals."""

    select_source = output_source_tab_selection_for_host(
        host,
        update_tabbar_container=lambda: update_output_tabbar_container(host),
    )
    host.tabbar.currentItemChanged.connect(select_source)
    host._source_tabs_collapsed = False
    host._source_tabbar_preferred_width = 0
    host._source_tab_cache_signature = None
    host._source_tab_tooltip_filters = {}
    source_tabs = output_source_tabs_controller_for_host(
        host,
        on_tab_changed=select_source,
        measure_preferred_width=lambda: (
            OutputCanvasNavigationController.measure_tabbar_preferred_width(host.tabbar)
        ),
        sync_source_selector=lambda: sync_output_source_selector_button(host),
        install_tooltip_filter=lambda tab_item, parent, delay: (
            install_cursor_tooltip_filter(
                cast(QWidget, tab_item),
                cast(QWidget, parent),
                show_delay_ms=delay,
            )
        ),
    )
    controller = output_navigation_controller_for_host(host)
    picker = output_picker_controller_for_host(
        cast(OutputCanvasPickerHost, host),
        visible_compare_state=lambda: visible_output_compare_state(host),
        compare_controller=lambda: compare_controller,
        update_tabbar_container=lambda: update_output_tabbar_container(host),
        scene_selector_min_width=_SCENE_SELECTOR_MIN_WIDTH,
        scene_selector_max_width=_SCENE_SELECTOR_MAX_WIDTH,
        scene_selector_horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
        source_selector_min_width=_SOURCE_SELECTOR_MIN_WIDTH,
        source_selector_max_width=_SOURCE_SELECTOR_MAX_WIDTH,
        source_selector_horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
    )
    host.scene_selector_button.clicked.connect(lambda: picker.show_scene_picker())
    host.set_selector_button.clicked.connect(lambda: picker.show_set_picker())
    host.source_selector_button.clicked.connect(lambda: picker.show_source_picker())
    host.comparison_scene_selector_button.clicked.connect(
        lambda: picker.show_compare_scene_picker("comparison")
    )
    host.comparison_set_selector_button.clicked.connect(
        lambda: picker.show_compare_set_picker("comparison")
    )
    host.comparison_source_selector_button.clicked.connect(
        lambda: picker.show_compare_source_picker("comparison")
    )
    return OutputNavigationRuntime(picker, source_tabs, controller)


def source_selector_width_for_text(host: OutputCanvas, text: str) -> int:
    """Measure one Output source-selector label through the production widget."""

    return selector_width_for_widget_text(
        text,
        widget=host.source_selector_button,
        minimum_width=_SOURCE_SELECTOR_MIN_WIDTH,
        maximum_width=_SOURCE_SELECTOR_MAX_WIDTH,
        horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
    )


__all__ = ["compose_output_navigation_runtime", "source_selector_width_for_text"]
