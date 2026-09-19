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
from weakref import ref

from PySide6.QtCore import QObject, QTimer
from shiboken6 import isValid

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_compare_navigation_chrome import (
    update_output_compare_nav_containers,
)
from substitute.presentation.canvas.output.output_compare_controller import (
    visible_output_compare_state,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    scene_selector_current_width,
    source_selector_current_width,
)

from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)
from substitute.presentation.canvas.output.output_canvas_navigation_visibility import (
    OutputCanvasNavigationVisibilityPolicy,
)
from substitute.presentation.canvas.output.output_canvas_route_state import (
    output_route_state_snapshot,
    output_scene_groups_by_key,
    visible_output_source_groups_by_key,
)
from substitute.presentation.canvas.shared.output_nav_layout import OutputNavBarGeometry


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

    compare_state = visible_output_compare_state(host)
    if compare_state.enabled:
        update_output_compare_nav_containers(host)
        return
    comparison_nav = getattr(host, "comparison_nav_container", None)
    if comparison_nav is not None:
        comparison_nav.hide()
    source_tab_count = len(getattr(getattr(host, "tabbar", None), "items", {}))
    active_scene_overview = bool(getattr(host, "active_scene_overview", False))
    source_selector = getattr(host, "source_selector_button", None)
    scene_groups = _scene_groups_by_key(host)
    visibility = OutputCanvasNavigationVisibilityPolicy.normal(
        scene_count=int(getattr(host, "scene_count", 0)),
        source_count=source_tab_count,
        set_count=int(getattr(host, "set_count", 0)),
        active_scene_overview=active_scene_overview,
    )
    show_scene_selector = visibility.show_scene_selector
    show_source_navigation = visibility.show_source_navigation
    show_set_selector = visibility.show_set_selector
    padding_left = 12
    padding_bottom = 8
    extra_pad = 4
    gap = 4
    scene_w = (
        scene_selector_current_width(
            scene_groups.values(),
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
    source_display = OutputCanvasNavigationVisibilityPolicy.source_display(
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

    _schedule_deferred_source_navigation_geometry(
        host,
        scheduler=single_shot if single_shot is not None else QTimer.singleShot,
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
    )


def _schedule_deferred_source_navigation_geometry(
    host: object,
    *,
    scheduler: Callable[[int, Callable[[], None]], None],
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
    """Schedule geometry only while a Qt navigation host remains valid."""

    def apply(live_host: object) -> None:
        """Apply the settled geometry for one still-live host."""

        _apply_deferred_source_navigation_geometry(
            live_host,
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
        )

    if isinstance(host, QObject):
        host_reference = ref(host)

        def apply_if_host_remains_live() -> None:
            """Ignore a deferred refresh after Qt has destroyed its host."""

            live_host = host_reference()
            if live_host is not None and isValid(live_host):
                apply(live_host)

        scheduler(0, apply_if_host_remains_live)
        return

    scheduler(0, lambda: apply(host))


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
    settled_source_display = OutputCanvasNavigationVisibilityPolicy.source_display(
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


def _scene_groups_by_key(host: object) -> dict[str, OutputCanvasSceneGroup]:
    """Return host projection scenes with revision-scoped preview overlays."""

    document_navigation = getattr(host, "_document_navigation", None)
    scene_groups = getattr(document_navigation, "scene_groups", None)
    if callable(scene_groups):
        return dict(scene_groups())
    return output_scene_groups_by_key(output_route_state_snapshot(host))


def _visible_source_groups_by_key(
    host: object,
) -> dict[str, OutputCanvasSourceGroup]:
    """Return source selector rows visible for the host projection context."""

    document_navigation = getattr(host, "_document_navigation", None)
    visible_sources = getattr(document_navigation, "visible_sources", None)
    if callable(visible_sources):
        return dict(visible_sources())
    return visible_output_source_groups_by_key(
        output_route_state_snapshot(host),
    )


__all__ = [
    "update_output_tabbar_container",
]
