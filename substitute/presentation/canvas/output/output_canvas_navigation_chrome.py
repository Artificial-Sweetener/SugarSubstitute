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

"""Apply Output canvas floating navigation chrome to widget hosts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QTimer

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    scene_selector_current_width,
    source_selector_current_width,
)

from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)
from substitute.presentation.canvas.shared.output_nav_layout import (
    OutputNavBarGeometry,
    compare_navigation_geometry,
)


class _CompareNavigationController(Protocol):
    """Expose compare counts needed for navigation geometry."""

    def compare_set_count(self, side: str) -> int:
        """Return the available set count for one compare side."""


_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28


class _HeightWidget(Protocol):
    """Represent the minimal height API needed from a navigation widget."""

    def height(self) -> int:
        """Return the current widget height."""


class _VisibilityHeightWidget(_HeightWidget, Protocol):
    """Represent the minimal visibility and height API for selector widgets."""

    def setVisible(self, visible: bool) -> None:
        """Set widget visibility."""


def update_output_tabbar_container(
    host: object,
    *,
    single_shot: Callable[[int, Callable[[], None]], None] | None = None,
) -> None:
    """Resize, position, or hide the Output canvas floating navigation chrome."""

    compare_state = _visible_output_compare_state(host)
    if compare_state.enabled:
        update_output_compare_nav_containers(host)
        return
    comparison_nav = getattr(host, "comparison_nav_container", None)
    if comparison_nav is not None:
        comparison_nav.hide()
    source_tab_count = len(getattr(getattr(host, "tabbar", None), "items", {}))
    scene_count = int(getattr(host, "scene_count", 0))
    active_scene_overview = bool(getattr(host, "active_scene_overview", False))
    source_selector = getattr(host, "source_selector_button", None)
    show_scene_selector = scene_count > 1 and hasattr(host, "scene_selector_button")
    show_source_navigation = source_tab_count > 1 and not active_scene_overview
    show_set_selector = not active_scene_overview and (
        int(getattr(host, "set_count", 0)) > 1
        or OutputCanvasRouteModel.grid_available_for_current_source(
            _visible_source_groups_by_key(host),
            getattr(host, "active_source_key", None),
        )
    )
    padding_left = 12
    padding_bottom = 8
    extra_pad = 4
    gap = 4
    scene_w = (
        scene_selector_current_width(
            _scene_groups_by_key(host).values(),
            active_scene_key=getattr(host, "active_scene_key", None),
            active_scene_overview=active_scene_overview,
            widget=getattr(host, "scene_selector_button", None),
            minimum_width=_SCENE_SELECTOR_MIN_WIDTH,
            maximum_width=_SCENE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
        )
        if show_scene_selector
        else 0
    )
    set_selector = getattr(host, "set_selector_button")
    selector_w = set_selector.width() if show_set_selector else 0
    navigation_controller = _navigation_controller(host)
    tabbar_w = (
        navigation_controller.preferred_tabbar_width() if show_source_navigation else 0
    )
    expanded_width = OutputCanvasNavigationController.navigation_bar_width(
        (scene_w, selector_w, tabbar_w),
        gap=gap,
        extra_pad=extra_pad,
    )
    source_display = OutputCanvasNavigationController.source_navigation_display(
        show_source_navigation=show_source_navigation,
        has_source_selector=source_selector is not None,
        expanded_width=expanded_width,
        available_width=navigation_controller.available_tabbar_container_width(),
    )
    setattr(host, "_source_tabs_collapsed", source_display.source_tabs_collapsed)
    show_source_tabs = source_display.show_source_tabs
    show_source_selector = source_display.show_source_selector
    tabbar = getattr(host, "tabbar")
    if (
        not show_scene_selector
        and not show_source_tabs
        and not show_source_selector
        and not show_set_selector
    ):
        scene_selector = getattr(host, "scene_selector_button", None)
        OutputCanvasNavigationController.hide_source_navigation(
            container=getattr(host, "tabbar_container"),
            tabbar=tabbar,
            set_selector=set_selector,
            scene_selector=scene_selector,
            source_selector=source_selector,
        )
        return
    scene_selector = getattr(host, "scene_selector_button", None)
    OutputCanvasNavigationController.set_source_navigation_visibility(
        tabbar=tabbar,
        set_selector=set_selector,
        scene_selector=scene_selector,
        source_selector=source_selector,
        show_scene_selector=show_scene_selector,
        show_source_tabs=show_source_tabs,
        show_source_selector=show_source_selector,
        show_set_selector=show_set_selector,
    )

    scheduler = single_shot if single_shot is not None else QTimer.singleShot
    scheduler(
        0,
        lambda: _apply_deferred_source_navigation_geometry(
            host,
            navigation_controller=navigation_controller,
            show_source_navigation=show_source_navigation,
            show_source_tabs=show_source_tabs,
            show_source_selector=show_source_selector,
            show_scene_selector=show_scene_selector,
            show_set_selector=show_set_selector,
            source_selector=source_selector,
            scene_w=scene_w,
            selector_w=selector_w,
            padding_left=padding_left,
            padding_bottom=padding_bottom,
            extra_pad=extra_pad,
            gap=gap,
        ),
    )


def update_output_compare_nav_containers(host: object) -> None:
    """Resize and position base/comparison navigation bars in compare mode."""

    state = _visible_output_compare_state(host)
    if not state.enabled or state.base is None or state.comparison is None:
        OutputCanvasNavigationController.hide_compare_navigation_containers(
            base_container=getattr(host, "tabbar_container"),
            comparison_container=getattr(host, "comparison_nav_container"),
        )
        return
    padding_left = 8
    padding_right = 8
    padding_bottom = 8
    extra_pad = 4
    gap = 4
    min_gap = 12
    control_h = 28
    bg_h = control_h + 2 * extra_pad
    visibility = OutputCanvasNavigationController.compare_navigation_visibility(
        scene_count=int(getattr(host, "scene_count", 0)),
        set_count=int(getattr(host, "set_count", 0)),
    )
    setattr(host, "_source_tabs_collapsed", visibility.source_tabs_collapsed)
    OutputCanvasNavigationController.apply_compare_navigation_visibility(
        tabbar=getattr(host, "tabbar"),
        scene_selector=getattr(host, "scene_selector_button"),
        set_selector=getattr(host, "set_selector_button"),
        source_selector=getattr(host, "source_selector_button"),
        visibility=visibility,
    )
    _sync_output_comparison_navigation_buttons(host)
    base_scene_w = (
        scene_selector_current_width(
            _scene_groups_by_key(host).values(),
            active_scene_key=getattr(host, "active_scene_key", None),
            active_scene_overview=bool(
                getattr(host, "active_scene_overview", False),
            ),
            widget=getattr(host, "scene_selector_button", None),
            minimum_width=_SCENE_SELECTOR_MIN_WIDTH,
            maximum_width=_SCENE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
        )
        if int(getattr(host, "scene_count", 0)) > 1
        else 0
    )
    set_selector = getattr(host, "set_selector_button")
    base_set_w = set_selector.width() if int(getattr(host, "set_count", 0)) > 1 else 0
    base_source_w = source_selector_current_width(
        _visible_source_groups_by_key(host).values(),
        active_source_key=getattr(host, "active_source_key", None),
        widget=getattr(host, "source_selector_button", None),
        minimum_width=_SOURCE_SELECTOR_MIN_WIDTH,
        maximum_width=_SOURCE_SELECTOR_MAX_WIDTH,
        horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
    )
    comparison_scene_w = (
        OutputCanvasNavigationController.button_width(
            getattr(host, "comparison_scene_selector_button"),
        )
        if int(getattr(host, "scene_count", 0)) > 1
        else 0
    )
    compare_controller = _compare_controller(host)
    comparison_set_w = (
        OutputCanvasNavigationController.button_width(
            getattr(host, "comparison_set_selector_button"),
        )
        if compare_controller.compare_set_count("comparison") > 1
        else 0
    )
    comparison_source_w = OutputCanvasNavigationController.button_width(
        getattr(host, "comparison_source_selector_button"),
    )
    base_width = OutputCanvasNavigationController.navigation_bar_width(
        (base_scene_w, base_set_w, base_source_w),
        gap=gap,
        extra_pad=extra_pad,
    )
    comparison_width = OutputCanvasNavigationController.navigation_bar_width(
        (comparison_scene_w, comparison_set_w, comparison_source_w),
        gap=gap,
        extra_pad=extra_pad,
    )
    geometry = compare_navigation_geometry(
        canvas_width=int(getattr(host, "width")()),
        canvas_height=int(getattr(host, "height")()),
        base_width=base_width,
        comparison_width=comparison_width,
        bar_height=bg_h,
        padding_left=padding_left,
        padding_right=padding_right,
        padding_bottom=padding_bottom,
        min_gap=min_gap,
    )
    navigation_controller = _navigation_controller(host)
    navigation_controller.place_compare_bar(
        container=getattr(host, "tabbar_container"),
        background=getattr(host, "tabbar_bg"),
        geometry=geometry.base,
        controls=(
            (getattr(host, "scene_selector_button"), base_scene_w),
            (set_selector, base_set_w),
            (getattr(host, "source_selector_button"), base_source_w),
        ),
        control_h=control_h,
        extra_pad=extra_pad,
        gap=gap,
    )
    navigation_controller.place_compare_bar(
        container=getattr(host, "comparison_nav_container"),
        background=getattr(host, "comparison_nav_bg"),
        geometry=geometry.comparison,
        controls=(
            (getattr(host, "comparison_scene_selector_button"), comparison_scene_w),
            (getattr(host, "comparison_set_selector_button"), comparison_set_w),
            (getattr(host, "comparison_source_selector_button"), comparison_source_w),
        ),
        control_h=control_h,
        extra_pad=extra_pad,
        gap=gap,
    )


def _apply_deferred_source_navigation_geometry(
    host: object,
    *,
    navigation_controller: OutputCanvasNavigationController,
    show_source_navigation: bool,
    show_source_tabs: bool,
    show_source_selector: bool,
    show_scene_selector: bool,
    show_set_selector: bool,
    source_selector: object | None,
    scene_w: int,
    selector_w: int,
    padding_left: int,
    padding_bottom: int,
    extra_pad: int,
    gap: int,
) -> None:
    """Apply deferred tabbar overlay geometry from settled widget metrics."""

    settled_tabbar_w = (
        navigation_controller.preferred_tabbar_width() if show_source_navigation else 0
    )
    settled_expanded_width = OutputCanvasNavigationController.navigation_bar_width(
        (scene_w, selector_w, settled_tabbar_w),
        gap=gap,
        extra_pad=extra_pad,
    )
    settled_source_display = OutputCanvasNavigationController.source_navigation_display(
        show_source_navigation=show_source_navigation,
        has_source_selector=source_selector is not None,
        expanded_width=settled_expanded_width,
        available_width=navigation_controller.available_tabbar_container_width(),
    )
    setattr(
        host, "_source_tabs_collapsed", settled_source_display.source_tabs_collapsed
    )
    settled_show_source_tabs = settled_source_display.show_source_tabs
    settled_show_source_selector = settled_source_display.show_source_selector
    tabbar = getattr(host, "tabbar")
    if settled_show_source_tabs != show_source_tabs:
        tabbar.setVisible(settled_show_source_tabs)
    if (
        source_selector is not None
        and settled_show_source_selector != show_source_selector
    ):
        cast(_VisibilityHeightWidget, source_selector).setVisible(
            settled_show_source_selector
        )
    getattr(host, "tabbar_container").show()
    source_w = (
        source_selector_current_width(
            _visible_source_groups_by_key(host).values(),
            active_source_key=getattr(host, "active_source_key", None),
            widget=source_selector,
            minimum_width=_SOURCE_SELECTOR_MIN_WIDTH,
            maximum_width=_SOURCE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
        )
        if settled_show_source_selector and source_selector is not None
        else 0
    )
    tabbar_h = tabbar.sizeHint().height() if settled_show_source_tabs else 28
    scene_selector = getattr(host, "scene_selector_button", None)
    scene_h = (
        cast(_HeightWidget, scene_selector).height()
        if show_scene_selector and scene_selector is not None
        else 0
    )
    source_h = (
        cast(_HeightWidget, source_selector).height()
        if settled_show_source_selector and source_selector is not None
        else 0
    )
    set_selector = getattr(host, "set_selector_button")
    control_h = max(
        tabbar_h,
        scene_h,
        source_h,
        set_selector.height() if show_set_selector else 0,
        28,
    )
    bg_w = OutputCanvasNavigationController.navigation_bar_width(
        (
            scene_w,
            selector_w,
            settled_tabbar_w if settled_show_source_tabs else 0,
            source_w,
        ),
        gap=gap,
        extra_pad=extra_pad,
    )
    bg_h = control_h + 2 * extra_pad
    parent_h = int(getattr(host, "height")())
    y = parent_h - bg_h - padding_bottom
    OutputCanvasNavigationController.place_source_bar(
        container=getattr(host, "tabbar_container"),
        background=getattr(host, "tabbar_bg"),
        geometry=OutputNavBarGeometry(
            x=padding_left - extra_pad,
            y=y,
            width=bg_w,
            height=bg_h,
            stacked=False,
        ),
        tabbar=tabbar,
        set_selector=set_selector,
        scene_selector=scene_selector,
        source_selector=source_selector,
        show_scene_selector=show_scene_selector,
        show_source_tabs=settled_show_source_tabs,
        show_source_selector=settled_show_source_selector,
        show_set_selector=show_set_selector,
        scene_width=scene_w,
        set_width=selector_w,
        tabbar_width=settled_tabbar_w,
        source_width=source_w,
        tabbar_height=tabbar_h,
        control_height=control_h,
        extra_pad=extra_pad,
        gap=gap,
    )


def _navigation_controller(host: object) -> OutputCanvasNavigationController:
    """Return the composed navigation controller for a host."""

    runtime = getattr(host, "_runtime", None)
    controller = getattr(getattr(runtime, "navigation", None), "controller", None)
    if controller is None:
        controller = getattr(host, "_navigation_controller", None)
    if not isinstance(controller, OutputCanvasNavigationController):
        raise TypeError("Output navigation chrome requires a navigation controller.")
    return controller


def _compare_controller(host: object) -> _CompareNavigationController:
    """Return runtime-owned compare state controller for chrome geometry."""

    runtime = getattr(host, "_runtime", None)
    controller = getattr(getattr(runtime, "compare", None), "controller", None)
    if controller is None:
        controller = getattr(host, "_compare_controller")
    return cast(_CompareNavigationController, controller)


def _visible_output_compare_state(host: object) -> OutputCompareState:
    """Return compare state used only for current control rendering."""

    state = getattr(host, "_visible_compare_state", None)
    if isinstance(state, OutputCompareState):
        return state
    candidate = getattr(host, "output_compare_state", OutputCompareState())
    return (
        candidate if isinstance(candidate, OutputCompareState) else OutputCompareState()
    )


def _scene_groups_by_key(host: object) -> dict[str, OutputCanvasSceneGroup]:
    """Return host projection scenes with revision-scoped preview overlays."""

    projection = getattr(host, "_output_projection", None)
    return OutputCanvasRouteModel.scene_groups_by_key(
        projection if isinstance(projection, OutputCanvasProjection) else None,
        preview_scene_groups_by_key=getattr(
            getattr(host, "_output_revision_cache", None),
            "preview_scene_groups_by_key",
            {},
        ),
    )


def _visible_source_groups_by_key(
    host: object,
) -> dict[str, OutputCanvasSourceGroup]:
    """Return source selector rows visible for the host projection context."""

    projection = getattr(host, "_output_projection", None)
    return OutputCanvasRouteModel.visible_source_groups_by_key(
        projection if isinstance(projection, OutputCanvasProjection) else None,
        scene_groups_by_key=_scene_groups_by_key(host),
        active_scene_overview=bool(getattr(host, "active_scene_overview", False)),
        active_scene_key=getattr(host, "active_scene_key", None),
        scene_count=int(getattr(host, "scene_count", 0)),
    )


def _sync_output_comparison_navigation_buttons(host: object) -> None:
    """Refresh compare navigation labels without importing projection wiring eagerly."""

    from substitute.presentation.canvas.output.output_compare_projection_presenter import (  # noqa: PLC0415
        sync_output_comparison_navigation_buttons,
    )

    sync_output_comparison_navigation_buttons(host)


__all__ = [
    "update_output_compare_nav_containers",
    "update_output_tabbar_container",
]
