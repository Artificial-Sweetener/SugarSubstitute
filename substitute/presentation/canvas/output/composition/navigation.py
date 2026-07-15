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

"""Compose Output navigation and picker collaborators."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.presentation.canvas.output.output_canvas_picker_controller import (
    OutputCanvasPickerController,
    picker_row_width_for_items,
)
from substitute.presentation.canvas.output.output_canvas_source_tabs_controller import (
    OutputCanvasSourceTabsController,
    TooltipInstaller,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
    visible_output_source_groups_by_key,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
    select_output_scene,
    select_output_source,
    select_output_set,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    scene_selector_current_width,
    selector_width_for_widget_text,
    source_selector_current_width,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    OutputCompareController,
)
from substitute.presentation.canvas.shared.canvas_nav_picker import CanvasNavPickerItem

from .projection import (
    _host_width_for,
    _output_projection_for,
    _source_tab_cache_signature_for,
    _source_tab_tooltip_filters_for,
)


class _SetPickerPort(Protocol):
    """Show the set picker anchored to a host control."""

    def show_for(
        self,
        anchor: object,
        *,
        set_count: int,
        active_set_index: int,
        include_grid: bool,
        selected_callback: Callable[[int], None],
    ) -> None:
        """Show set choices for an Output selector."""


class _NavPickerPort(Protocol):
    """Show keyed navigation picker rows anchored to a host control."""

    def show_for(
        self,
        anchor: object,
        *,
        items: tuple[CanvasNavPickerItem, ...],
        active_key: str,
        row_width: int | None,
        selected_callback: Callable[[str], None],
    ) -> None:
        """Show navigation choices for an Output selector."""


class OutputCanvasPickerHost(Protocol):
    """Expose widget collaborators needed to compose picker presentation."""

    _set_picker: _SetPickerPort
    _scene_picker: _NavPickerPort
    _source_picker: _NavPickerPort
    _output_projection: object
    active_source_key: str | None
    active_scene_key: str | None
    active_scene_overview: bool
    active_set_index: int
    scene_count: int
    set_count: int
    set_selector_button: object
    scene_selector_button: object
    source_selector_button: object


def output_canvas_picker_controller_for(
    host: OutputCanvasPickerHost,
    *,
    visible_compare_state: Callable[[], OutputCompareState],
    visible_source_groups_by_key: Callable[
        [],
        Mapping[str, OutputCanvasSourceGroup],
    ],
    scene_groups_by_key: Callable[[], Mapping[str, OutputCanvasSceneGroup]],
    scene_picker_row_width: Callable[[tuple[CanvasNavPickerItem, ...]], int],
    source_picker_row_width: Callable[[tuple[CanvasNavPickerItem, ...]], int],
    compare_controller: Callable[[], OutputCompareController],
    update_tabbar_container: Callable[[], None],
) -> OutputCanvasPickerController:
    """Return the picker controller wired to an Output canvas host."""

    return OutputCanvasPickerController(
        visible_compare_state=visible_compare_state,
        grid_available_for_current_source=lambda: (
            OutputCanvasRouteModel.grid_available_for_current_source(
                visible_source_groups_by_key(),
                host.active_source_key,
            )
        ),
        set_count=lambda: int(getattr(host, "set_count", 0)),
        active_set_index=lambda: int(getattr(host, "active_set_index", 0)),
        set_selector_button=lambda: host.set_selector_button,
        show_set_picker_for=lambda anchor, set_count, active_set_index, include_grid, selected_callback: (
            host._set_picker.show_for(
                anchor,
                set_count=set_count,
                active_set_index=active_set_index,
                include_grid=include_grid,
                selected_callback=selected_callback,
            )
        ),
        on_set_selected=lambda set_index: select_output_set(
            host,
            set_index,
            source_groups_by_key=visible_source_groups_by_key(),
            update_tabbar_container=update_tabbar_container,
        ),
        scene_count=lambda: int(getattr(host, "scene_count", 0)),
        active_scene_overview=lambda: bool(
            getattr(host, "active_scene_overview", False)
        ),
        active_scene_key=lambda: (
            host.active_scene_key
            if isinstance(getattr(host, "active_scene_key", None), str)
            else None
        ),
        scene_selector_button=lambda: host.scene_selector_button,
        scene_groups_by_key=scene_groups_by_key,
        scene_picker_row_width=scene_picker_row_width,
        show_scene_picker_for=lambda anchor, items, active_key, row_width, selected_callback: (
            host._scene_picker.show_for(
                anchor,
                items=items,
                active_key=active_key,
                row_width=row_width,
                selected_callback=selected_callback,
            )
        ),
        on_scene_selected=lambda scene_key: select_output_scene(
            host,
            scene_key,
            scene_groups_by_key=scene_groups_by_key(),
            update_tabbar_container=update_tabbar_container,
        ),
        active_source_key=lambda: (
            host.active_source_key
            if isinstance(getattr(host, "active_source_key", None), str)
            else None
        ),
        source_selector_button=lambda: host.source_selector_button,
        visible_source_groups_by_key=visible_source_groups_by_key,
        source_picker_row_width=source_picker_row_width,
        show_source_picker_for=lambda anchor, items, active_key, row_width, selected_callback: (
            host._source_picker.show_for(
                anchor,
                items=items,
                active_key=active_key,
                row_width=row_width,
                selected_callback=selected_callback,
            )
        ),
        on_source_selected=lambda route_key: select_output_source(
            host,
            route_key,
            source_groups_by_key=visible_source_groups_by_key(),
            update_tabbar_container=update_tabbar_container,
        ),
        output_projection=lambda: _output_projection_for(host),
        compare_selection=lambda side: compare_controller().compare_selection(side),
        compare_sources=lambda side: compare_controller().compare_sources(side),
        compare_set_count=lambda side: compare_controller().compare_set_count(side),
        compare_scene_button=lambda side: compare_controller().compare_scene_button(
            side
        ),
        compare_set_button=lambda side: compare_controller().compare_set_button(side),
        compare_source_button=lambda side: compare_controller().compare_source_button(
            side
        ),
        compare_source_picker_row_width=lambda _side, items: (
            compare_controller().compare_source_picker_row_width(items)
        ),
        set_compare_scene=lambda side, scene_key: (
            compare_controller().set_compare_scene(
                side,
                scene_key,
            )
        ),
        set_compare_set=lambda side, set_index: compare_controller().set_compare_set(
            side,
            set_index,
        ),
        set_compare_source=lambda side, source_key: (
            compare_controller().set_compare_source(
                side,
                source_key,
            )
        ),
    )


def output_picker_controller_for_host(
    host: OutputCanvasPickerHost,
    *,
    visible_compare_state: Callable[[], OutputCompareState],
    compare_controller: Callable[[], OutputCompareController],
    update_tabbar_container: Callable[[], None],
    scene_selector_min_width: int,
    scene_selector_max_width: int,
    scene_selector_horizontal_padding: int,
    source_selector_min_width: int,
    source_selector_max_width: int,
    source_selector_horizontal_padding: int,
) -> OutputCanvasPickerController:
    """Return the picker controller with host selector metric adapters."""

    def scene_groups_by_key() -> Mapping[str, OutputCanvasSceneGroup]:
        """Return scene groups from the host route state."""

        return output_scene_groups_by_key(output_route_state_snapshot(host))

    def visible_source_groups_by_key() -> Mapping[str, OutputCanvasSourceGroup]:
        """Return currently visible source groups from the host route state."""

        return visible_output_source_groups_by_key(output_route_state_snapshot(host))

    def scene_picker_row_width(items: tuple[CanvasNavPickerItem, ...]) -> int:
        """Return the row width for scene picker rows."""

        return picker_row_width_for_items(
            scene_selector_current_width(
                scene_groups_by_key().values(),
                active_scene_key=getattr(host, "active_scene_key", None),
                active_scene_overview=bool(
                    getattr(host, "active_scene_overview", False)
                ),
                widget=getattr(host, "scene_selector_button", None),
                minimum_width=scene_selector_min_width,
                maximum_width=scene_selector_max_width,
                horizontal_padding=scene_selector_horizontal_padding,
            ),
            items,
            lambda label: selector_width_for_widget_text(
                label,
                widget=getattr(host, "scene_selector_button", None),
                minimum_width=scene_selector_min_width,
                maximum_width=scene_selector_max_width,
                horizontal_padding=scene_selector_horizontal_padding,
            ),
        )

    def source_picker_row_width(items: tuple[CanvasNavPickerItem, ...]) -> int:
        """Return the row width for source picker rows."""

        return picker_row_width_for_items(
            source_selector_current_width(
                visible_source_groups_by_key().values(),
                active_source_key=getattr(host, "active_source_key", None),
                widget=getattr(host, "source_selector_button", None),
                minimum_width=source_selector_min_width,
                maximum_width=source_selector_max_width,
                horizontal_padding=source_selector_horizontal_padding,
            ),
            items,
            lambda label: selector_width_for_widget_text(
                label,
                widget=getattr(host, "source_selector_button", None),
                minimum_width=source_selector_min_width,
                maximum_width=source_selector_max_width,
                horizontal_padding=source_selector_horizontal_padding,
            ),
        )

    return output_canvas_picker_controller_for(
        host,
        visible_compare_state=visible_compare_state,
        visible_source_groups_by_key=visible_source_groups_by_key,
        scene_groups_by_key=scene_groups_by_key,
        scene_picker_row_width=scene_picker_row_width,
        source_picker_row_width=source_picker_row_width,
        compare_controller=compare_controller,
        update_tabbar_container=update_tabbar_container,
    )


def output_source_tab_selection_for_host(
    host: object,
    *,
    update_tabbar_container: Callable[[], None],
) -> Callable[[str], None]:
    """Return the source-tab selection callback wired to an Output canvas host."""

    return lambda route_key: select_output_source(
        host,
        route_key,
        source_groups_by_key=visible_output_source_groups_by_key(
            output_route_state_snapshot(host)
        ),
        update_tabbar_container=update_tabbar_container,
    )


def output_source_tabs_controller_for_host(
    host: object,
    *,
    on_tab_changed: Callable[[str], None],
    measure_preferred_width: Callable[[], int],
    sync_source_selector: Callable[[], None],
    install_tooltip_filter: TooltipInstaller,
) -> OutputCanvasSourceTabsController:
    """Return the source-tabs controller wired to an Output canvas host."""

    return OutputCanvasSourceTabsController(
        visible_sources=lambda: tuple(
            visible_output_source_groups_by_key(
                output_route_state_snapshot(host)
            ).values()
        ),
        cached_signature=lambda: _source_tab_cache_signature_for(host),
        set_cached_signature=lambda signature: setattr(
            host,
            "_source_tab_cache_signature",
            signature,
        ),
        set_preferred_width=lambda width: setattr(
            host,
            "_source_tabbar_preferred_width",
            width,
        ),
        tabbar=lambda: getattr(host, "tabbar"),
        on_tab_changed=on_tab_changed,
        active_set_index=lambda: int(getattr(host, "active_set_index", 1)),
        tooltip_filters=lambda: _source_tab_tooltip_filters_for(host),
        measure_preferred_width=measure_preferred_width,
        sync_source_selector=sync_source_selector,
        install_tooltip_filter=install_tooltip_filter,
    )


def output_navigation_controller_for_host(
    host: object,
) -> OutputCanvasNavigationController:
    """Return the floating navigation controller wired to an Output canvas host."""

    return OutputCanvasNavigationController(
        canvas_width=lambda: _host_width_for(host),
        tabbar=lambda: getattr(host, "tabbar"),
        cached_source_tabbar_width=lambda: int(
            getattr(host, "_source_tabbar_preferred_width", 0) or 0
        ),
        set_cached_source_tabbar_width=lambda width: setattr(
            host,
            "_source_tabbar_preferred_width",
            width,
        ),
    )
