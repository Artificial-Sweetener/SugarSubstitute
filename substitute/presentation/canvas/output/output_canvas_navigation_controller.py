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

"""Coordinate Output canvas navigation policy, adapters, and measurement."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    apply_scene_selector_button_state,
    apply_set_selector_button_state,
    apply_source_selector_button_state,
    scene_selector_full_text,
    selector_display_text_for_metrics,
    selector_font_metrics_for_widget,
    selector_width_for_metrics_text,
    source_selector_full_text,
)
from substitute.presentation.canvas.shared.output_nav_layout import (
    OutputNavBarGeometry,
    OutputNavControlWidths,
    navigation_bar_width,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.output.navigation_controller")

_SCENE_SELECTOR_MIN_WIDTH = 58
_SCENE_SELECTOR_MAX_WIDTH = 260
_SCENE_SELECTOR_HORIZONTAL_PADDING = 28
_SOURCE_SELECTOR_MIN_WIDTH = 58
_SOURCE_SELECTOR_MAX_WIDTH = 260
_SOURCE_SELECTOR_HORIZONTAL_PADDING = 28

OutputTabChangeKind = Literal[
    "none",
    "activate_grid",
    "activate_source_fallback",
    "activate_output_item",
    "unknown_source",
]
OutputSceneSelectionKind = Literal[
    "activate_scene_overview",
    "activate_scene",
]
OutputSetSelectionKind = Literal[
    "none",
    "activate_grid",
    "activate_output_item",
]
OutputSceneActivationFollowup = Literal[
    "none",
    "activate_grid",
    "activate_source_fallback",
]


@dataclass(frozen=True, slots=True)
class OutputTabChangeAction:
    """Describe the visible action required for one source-tab change."""

    kind: OutputTabChangeKind
    source_key: str
    item: OutputCanvasImageItem | None = None


@dataclass(frozen=True, slots=True)
class OutputSceneSelectionAction:
    """Describe the visible action required for one scene selection."""

    kind: OutputSceneSelectionKind
    scene_key: str


@dataclass(frozen=True, slots=True)
class OutputSetSelectionAction:
    """Describe the visible action required for one set selection."""

    kind: OutputSetSelectionKind
    set_index: int
    source_key: str | None = None
    item: OutputCanvasImageItem | None = None


@dataclass(frozen=True, slots=True)
class OutputSceneActivationPlan:
    """Describe state and follow-up activation for one concrete scene."""

    scene_key: str
    active_source_key: str | None
    set_count: int
    followup: OutputSceneActivationFollowup


@dataclass(frozen=True, slots=True)
class OutputGridActivationPlan:
    """Describe the source-grid target selected for activation."""

    source_key: str


@dataclass(frozen=True, slots=True)
class OutputSceneOverviewActivationPlan:
    """Describe state required to activate the all-scenes overview."""

    active_set_index: int = 1
    active_source_key: None = None
    set_count: int = 0


@dataclass(frozen=True, slots=True)
class OutputItemActivationPlan:
    """Describe state required to activate one concrete output item."""

    source_key: str
    active_set_index: int
    last_real_set_index: int
    image_id: UUID


@dataclass(frozen=True, slots=True)
class OutputCanvasNavigationController:
    """Own floating navigation width and tabbar measurement helpers."""

    canvas_width: Callable[[], int | None]
    tabbar: Callable[[], object]
    cached_source_tabbar_width: Callable[[], int]
    set_cached_source_tabbar_width: Callable[[int], None]

    def available_tabbar_container_width(self) -> int:
        """Return horizontal space available to the floating navigation bar."""

        width = self.canvas_width()
        if width is None:
            return 10_000
        return max(1, int(width) - 24)

    def preferred_tabbar_width(self) -> int:
        """Return full source tabbar preferred width even when it is hidden."""

        tabbar = self.tabbar()
        measured_width = self.measure_tabbar_preferred_width(tabbar)
        if measured_width > 0:
            self.set_cached_source_tabbar_width(measured_width)
            return measured_width
        cached_width = max(0, int(self.cached_source_tabbar_width() or 0))
        if cached_width > 0:
            return cached_width
        width = getattr(tabbar, "width", None)
        return int(width()) if callable(width) else 0

    @classmethod
    def measure_tabbar_preferred_width(cls, tabbar: object) -> int:
        """Measure the source tabbar's content width from current layout state."""

        ensure_polished = getattr(tabbar, "ensurePolished", None)
        if callable(ensure_polished):
            ensure_polished()
        layout_getter = getattr(tabbar, "layout", None)
        layout = layout_getter() if callable(layout_getter) else None
        if layout is not None:
            invalidate = getattr(layout, "invalidate", None)
            if callable(invalidate):
                invalidate()
            activate = getattr(layout, "activate", None)
            if callable(activate):
                activate()
        size_hint_width = cls.size_hint_width(tabbar)
        if size_hint_width > 0:
            return size_hint_width
        return cls.tabbar_item_width(tabbar, layout)

    @staticmethod
    def size_hint_width(widget: object) -> int:
        """Return a widget size-hint width when it reports a positive value."""

        size_hint = getattr(widget, "sizeHint", None)
        if not callable(size_hint):
            return 0
        hint = size_hint()
        width = getattr(hint, "width", None)
        if not callable(width):
            return 0
        return max(0, int(width()))

    @classmethod
    def tabbar_item_width(cls, tabbar: object, layout: object | None) -> int:
        """Calculate tabbar width from child item hints when parent hint is stale."""

        items = getattr(tabbar, "items", {})
        if not isinstance(items, Mapping):
            return 0
        item_widths = tuple(
            cls.tabbar_item_preferred_width(item) for item in items.values()
        )
        visible_item_widths = tuple(width for width in item_widths if width > 0)
        if not visible_item_widths:
            return 0
        spacing = cls.layout_spacing(layout)
        margins = cls.layout_horizontal_margins(layout)
        return (
            sum(visible_item_widths)
            + max(0, len(visible_item_widths) - 1) * spacing
            + margins
        )

    @classmethod
    def tabbar_item_preferred_width(cls, item: object) -> int:
        """Return a source-tab item width from settled or hinted geometry."""

        ensure_polished = getattr(item, "ensurePolished", None)
        if callable(ensure_polished):
            ensure_polished()
        adjust_size = getattr(item, "adjustSize", None)
        if callable(adjust_size):
            adjust_size()
        hinted_width = cls.size_hint_width(item)
        if hinted_width > 0:
            return hinted_width
        width = getattr(item, "width", None)
        return max(0, int(width())) if callable(width) else 0

    @staticmethod
    def layout_spacing(layout: object | None) -> int:
        """Return a layout's horizontal spacing when available."""

        if layout is None:
            return 0
        spacing = getattr(layout, "spacing", None)
        if not callable(spacing):
            return 0
        return max(0, int(spacing()))

    @staticmethod
    def layout_horizontal_margins(layout: object | None) -> int:
        """Return a layout's left and right margins when available."""

        if layout is None:
            return 0
        contents_margins = getattr(layout, "contentsMargins", None)
        if not callable(contents_margins):
            return 0
        margins = contents_margins()
        left = getattr(margins, "left", None)
        right = getattr(margins, "right", None)
        return (max(0, int(left())) if callable(left) else 0) + (
            max(0, int(right())) if callable(right) else 0
        )

    @staticmethod
    def navigation_bar_width(
        widths: tuple[int, ...],
        *,
        gap: int,
        extra_pad: int,
    ) -> int:
        """Return floating navigation background width for visible controls."""

        if len(widths) <= 3:
            padded_widths = tuple(widths[:3]) + (0,) * max(0, 3 - len(widths))
            return navigation_bar_width(
                OutputNavControlWidths(
                    scene=padded_widths[0],
                    set=padded_widths[1],
                    source=padded_widths[2],
                ),
                gap=gap,
                extra_pad=extra_pad,
            )
        visible_widths = [width for width in widths if width > 0]
        width = sum(visible_widths)
        width += max(0, len(visible_widths) - 1) * gap
        width += 2 * extra_pad
        return max(width, 1)

    @staticmethod
    def source_navigation_display(
        *,
        show_source_navigation: bool,
        has_source_selector: bool,
        expanded_width: int,
        available_width: int,
    ) -> SourceNavigationDisplay:
        """Return whether source navigation should render tabs or selector."""

        collapsed = bool(
            show_source_navigation
            and has_source_selector
            and expanded_width > available_width
        )
        return SourceNavigationDisplay(
            source_tabs_collapsed=collapsed,
            show_source_tabs=show_source_navigation and not collapsed,
            show_source_selector=show_source_navigation and collapsed,
        )

    @staticmethod
    def compare_navigation_visibility(
        *,
        scene_count: int,
        set_count: int,
    ) -> CompareNavigationVisibility:
        """Return base-control visibility required for active compare mode."""

        return CompareNavigationVisibility(
            source_tabs_collapsed=True,
            show_scene_selector=scene_count > 1,
            show_set_selector=set_count > 1,
            show_source_selector=True,
        )

    @classmethod
    def hide_compare_navigation_containers(
        cls,
        *,
        base_container: object,
        comparison_container: object,
    ) -> None:
        """Hide both compare navigation containers when compare state is invalid."""

        cls.hide_widget(base_container)
        cls.hide_widget(comparison_container)

    @classmethod
    def apply_compare_navigation_visibility(
        cls,
        *,
        tabbar: object,
        scene_selector: object,
        set_selector: object,
        source_selector: object,
        visibility: CompareNavigationVisibility,
    ) -> None:
        """Apply base-control visibility required before compare geometry updates."""

        cls.hide_widget(tabbar)
        cls.set_widget_visible(scene_selector, visibility.show_scene_selector)
        cls.set_widget_visible(set_selector, visibility.show_set_selector)
        cls.set_widget_visible(source_selector, visibility.show_source_selector)

    @classmethod
    def place_compare_bar(
        cls,
        *,
        container: object,
        background: object,
        geometry: OutputNavBarGeometry,
        controls: tuple[tuple[object, int], ...],
        control_h: int,
        extra_pad: int,
        gap: int,
    ) -> None:
        """Place one compare navigation bar and toggle its visible controls."""

        set_container_geometry = getattr(container, "setGeometry", None)
        if callable(set_container_geometry):
            set_container_geometry(
                geometry.x,
                geometry.y,
                geometry.width,
                geometry.height,
            )
        set_background_geometry = getattr(background, "setGeometry", None)
        if callable(set_background_geometry):
            set_background_geometry(0, 0, geometry.width, geometry.height)
        x = extra_pad
        for control, width in controls:
            cls.place_compare_bar_control(
                control=control,
                width=width,
                x=x,
                y=extra_pad,
                height=control_h,
            )
            if width > 0:
                x += width + gap
        lower_background = getattr(background, "lower", None)
        if callable(lower_background):
            lower_background()
        show_container = getattr(container, "show", None)
        if callable(show_container):
            show_container()

    @staticmethod
    def place_compare_bar_control(
        *,
        control: object,
        width: int,
        x: int,
        y: int,
        height: int,
    ) -> None:
        """Place one compare navigation control or hide it when width is empty."""

        set_visible = getattr(control, "setVisible", None)
        if width <= 0:
            if callable(set_visible):
                set_visible(False)
            return
        if callable(set_visible):
            set_visible(True)
        set_geometry = getattr(control, "setGeometry", None)
        if callable(set_geometry):
            set_geometry(x, y, width, height)
        raise_control = getattr(control, "raise_", None)
        if callable(raise_control):
            raise_control()

    @classmethod
    def hide_source_navigation(
        cls,
        *,
        container: object,
        tabbar: object,
        set_selector: object,
        scene_selector: object | None,
        source_selector: object | None,
    ) -> None:
        """Hide every normal source-navigation control and its container."""

        for control in (
            scene_selector,
            source_selector,
            tabbar,
            set_selector,
            container,
        ):
            cls.hide_widget(control)

    @classmethod
    def set_source_navigation_visibility(
        cls,
        *,
        tabbar: object,
        set_selector: object,
        scene_selector: object | None,
        source_selector: object | None,
        show_scene_selector: bool,
        show_source_tabs: bool,
        show_source_selector: bool,
        show_set_selector: bool,
    ) -> None:
        """Apply normal source-navigation visibility before geometry settles."""

        cls.set_widget_visible(scene_selector, show_scene_selector)
        cls.set_widget_visible(tabbar, show_source_tabs)
        cls.set_widget_visible(source_selector, show_source_selector)
        cls.set_widget_visible(set_selector, show_set_selector)

    @classmethod
    def place_source_bar(
        cls,
        *,
        container: object,
        background: object,
        geometry: OutputNavBarGeometry,
        tabbar: object,
        set_selector: object,
        scene_selector: object | None,
        source_selector: object | None,
        show_scene_selector: bool,
        show_source_tabs: bool,
        show_source_selector: bool,
        show_set_selector: bool,
        scene_width: int,
        set_width: int,
        tabbar_width: int,
        source_width: int,
        tabbar_height: int,
        control_height: int,
        extra_pad: int,
        gap: int,
    ) -> None:
        """Place the normal source navigation bar and visible controls."""

        cls.set_widget_geometry(
            container,
            geometry.x,
            geometry.y,
            geometry.width,
            geometry.height,
        )
        cls.set_widget_geometry(background, 0, 0, geometry.width, geometry.height)
        x = extra_pad
        if show_scene_selector and scene_selector is not None:
            cls.set_widget_geometry(
                scene_selector,
                x,
                extra_pad,
                scene_width,
                control_height,
            )
            x += scene_width + gap
        if show_set_selector:
            cls.set_widget_geometry(
                set_selector,
                x,
                extra_pad,
                set_width,
                control_height,
            )
            x += set_width + gap
        if show_source_tabs:
            cls.set_widget_geometry(
                tabbar,
                x,
                extra_pad,
                tabbar_width,
                tabbar_height,
            )
        if show_source_selector and source_selector is not None:
            cls.set_widget_geometry(
                source_selector,
                x,
                extra_pad,
                source_width,
                control_height,
            )
        cls.raise_widget(tabbar)
        if show_scene_selector:
            cls.raise_widget(scene_selector)
        if show_source_selector:
            cls.raise_widget(source_selector)
        cls.raise_widget(set_selector)
        cls.lower_widget(background)

    @staticmethod
    def hide_widget(widget: object | None) -> None:
        """Hide a widget-like object when it exposes ``hide``."""

        hide = getattr(widget, "hide", None)
        if callable(hide):
            hide()

    @staticmethod
    def set_widget_visible(widget: object | None, visible: bool) -> None:
        """Set widget-like object visibility when supported."""

        set_visible = getattr(widget, "setVisible", None)
        if callable(set_visible):
            set_visible(visible)

    @staticmethod
    def set_widget_geometry(
        widget: object | None,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        """Set widget-like object geometry when supported."""

        set_geometry = getattr(widget, "setGeometry", None)
        if callable(set_geometry):
            set_geometry(x, y, width, height)

    @staticmethod
    def raise_widget(widget: object | None) -> None:
        """Raise a widget-like object when supported."""

        raise_widget = getattr(widget, "raise_", None)
        if callable(raise_widget):
            raise_widget()

    @staticmethod
    def lower_widget(widget: object | None) -> None:
        """Lower a widget-like object when supported."""

        lower_widget = getattr(widget, "lower", None)
        if callable(lower_widget):
            lower_widget()

    @classmethod
    def button_width(cls, button: object) -> int:
        """Return current button width with size hint fallback."""

        width = getattr(button, "width", None)
        value = int(width()) if callable(width) else 0
        if value > 0:
            return value
        return cls.size_hint_width(button)

    @staticmethod
    def source_fallback_item(
        source_groups: Mapping[str, OutputCanvasSourceGroup],
        source_key: str,
        *,
        last_real_set_index: int,
    ) -> OutputCanvasImageItem | None:
        """Return the concrete item used when a source grid cannot be activated."""

        source = source_groups.get(source_key)
        if source is None:
            return None
        item = source.nearest_item(last_real_set_index)
        if item is not None:
            return item
        return source.nearest_item(1)

    @staticmethod
    def tab_change_action(
        *,
        route_key: str,
        suppress_tab_change: bool,
        active_set_index: int,
        source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    ) -> OutputTabChangeAction:
        """Return the widget action required by one source-tab route key."""

        if suppress_tab_change:
            return OutputTabChangeAction("none", route_key)
        if active_set_index == 0:
            source = source_groups_by_key.get(route_key)
            if source is not None and OutputCanvasRouteModel.grid_available_for_source(
                source
            ):
                return OutputTabChangeAction("activate_grid", route_key)
            return OutputTabChangeAction("activate_source_fallback", route_key)
        item = OutputCanvasRouteModel.item_for_source_and_set(
            source_groups_by_key,
            route_key,
            active_set_index,
        )
        if item is None:
            return OutputTabChangeAction("unknown_source", route_key)
        return OutputTabChangeAction("activate_output_item", route_key, item)

    @staticmethod
    def scene_selection_action(scene_key: str) -> OutputSceneSelectionAction:
        """Return the widget action required by one scene picker selection."""

        if scene_key == "all":
            return OutputSceneSelectionAction("activate_scene_overview", scene_key)
        return OutputSceneSelectionAction("activate_scene", scene_key)

    @staticmethod
    def set_selection_action(
        *,
        set_index: int,
        active_source_key: str | None,
        source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    ) -> OutputSetSelectionAction:
        """Return the widget action required by one set picker selection."""

        if set_index == 0:
            return OutputSetSelectionAction(
                "activate_grid",
                set_index,
                active_source_key,
            )
        target = OutputCanvasRouteModel.concrete_set_selection(
            source_groups_by_key,
            active_source_key=active_source_key,
            set_index=set_index,
        )
        if target is None:
            return OutputSetSelectionAction("none", set_index)
        source_key, item = target
        return OutputSetSelectionAction(
            "activate_output_item",
            set_index,
            source_key,
            item,
        )

    @staticmethod
    def scene_activation_plan(
        *,
        scene_key: str,
        scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
        was_scene_overview: bool,
        active_source_key: str | None,
    ) -> OutputSceneActivationPlan | None:
        """Return concrete scene activation state without mutating widgets."""

        scene = scene_groups_by_key.get(scene_key)
        if scene is None:
            return None
        source_groups_by_key = {source.source_key: source for source in scene.sources}
        preferred_source_key = (
            scene.representative_source_key if was_scene_overview else None
        )
        resolved_source_key = OutputCanvasRouteModel.resolved_active_source_key(
            source_groups_by_key,
            preferred_source_key or active_source_key,
            previous_source_key=active_source_key,
            preserve_previous=not was_scene_overview,
        )
        if OutputCanvasRouteModel.grid_available_for_current_source(
            source_groups_by_key,
            resolved_source_key,
        ):
            followup: OutputSceneActivationFollowup = "activate_grid"
        elif resolved_source_key is not None:
            followup = "activate_source_fallback"
        else:
            followup = "none"
        return OutputSceneActivationPlan(
            scene_key=scene_key,
            active_source_key=resolved_source_key,
            set_count=OutputCanvasRouteModel.set_count_for_sources(
                tuple(source_groups_by_key.values())
            ),
            followup=followup,
        )

    @staticmethod
    def grid_activation_plan(
        *,
        source_key: str | None,
        source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    ) -> OutputGridActivationPlan | None:
        """Return the source-grid activation target, if one can render a grid."""

        resolved_source_key = source_key
        if resolved_source_key is None:
            resolved_source_key = OutputCanvasRouteModel.first_grid_source_key(
                source_groups_by_key
            )
        if resolved_source_key is None:
            return None
        source = source_groups_by_key.get(resolved_source_key)
        if source is None or not OutputCanvasRouteModel.grid_available_for_source(
            source
        ):
            return None
        return OutputGridActivationPlan(resolved_source_key)

    @staticmethod
    def scene_overview_activation_plan(
        *,
        scene_count: int,
    ) -> OutputSceneOverviewActivationPlan | None:
        """Return all-scenes overview activation state when overview is available."""

        if scene_count <= 1:
            return None
        return OutputSceneOverviewActivationPlan()

    @staticmethod
    def item_activation_plan(
        *,
        source_key: str,
        item: OutputCanvasImageItem,
    ) -> OutputItemActivationPlan:
        """Return concrete output item activation state."""

        return OutputItemActivationPlan(
            source_key=source_key,
            active_set_index=item.set_index,
            last_real_set_index=item.set_index,
            image_id=item.image_id,
        )


def select_output_set(
    host: object,
    set_index: int,
    *,
    source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    update_tabbar_container: Callable[[], None],
) -> None:
    """Apply a set-picker selection through the Output navigation host."""

    active_source_key = getattr(host, "active_source_key", None)
    action = OutputCanvasNavigationController.set_selection_action(
        set_index=set_index,
        active_source_key=active_source_key
        if isinstance(active_source_key, str)
        else None,
        source_groups_by_key=source_groups_by_key,
    )
    if action.kind == "activate_grid":
        activate_output_grid_for_source(
            host,
            action.source_key,
            source_groups_by_key=source_groups_by_key,
            emit_selection=True,
            update_tabbar_container=update_tabbar_container,
        )
        return
    if action.kind == "none":
        return
    if action.source_key is None or action.item is None:
        return
    activate_output_item(
        host,
        action.source_key,
        action.item,
        update_tabbar_container=update_tabbar_container,
    )


def select_output_source(
    host: object,
    route_key: str,
    *,
    source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    update_tabbar_container: Callable[[], None],
) -> None:
    """Apply a source-tab selection through the Output navigation host."""

    action = OutputCanvasNavigationController.tab_change_action(
        route_key=route_key,
        suppress_tab_change=bool(getattr(host, "_suppress_tab_change", False)),
        active_set_index=int(getattr(host, "active_set_index", 0)),
        source_groups_by_key=source_groups_by_key,
    )
    if action.kind == "none":
        return
    if action.kind == "activate_grid":
        activate_output_grid_for_source(
            host,
            action.source_key,
            source_groups_by_key=source_groups_by_key,
            emit_selection=True,
            update_tabbar_container=update_tabbar_container,
        )
        return
    if action.kind == "activate_source_fallback":
        last_real_set_index = int(getattr(host, "last_real_set_index", 1))
        item = OutputCanvasNavigationController.source_fallback_item(
            source_groups_by_key,
            action.source_key,
            last_real_set_index=last_real_set_index,
        )
        if item is not None:
            activate_output_item(
                host,
                action.source_key,
                item,
                update_tabbar_container=update_tabbar_container,
            )
        return
    if action.kind == "unknown_source":
        log_warning(
            _LOGGER,
            "Ignored unknown output source route key",
            route_key=route_key,
        )
        return
    if action.item is not None:
        activate_output_item(
            host,
            action.source_key,
            action.item,
            update_tabbar_container=update_tabbar_container,
        )


def select_output_scene(
    host: object,
    scene_key: str,
    *,
    scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
    update_tabbar_container: Callable[[], None],
) -> None:
    """Apply a scene-picker selection through the Output navigation host."""

    action = OutputCanvasNavigationController.scene_selection_action(scene_key)
    if action.kind == "activate_scene_overview":
        if activate_output_scene_overview(
            host,
            update_tabbar_container=update_tabbar_container,
        ):
            _emit_signal(
                getattr(host, "activeOutputSceneChanged", None),
                getattr(host, "active_scene_key", None) or "",
                True,
            )
        return

    if activate_output_scene(
        host,
        action.scene_key,
        scene_groups_by_key=scene_groups_by_key,
        update_tabbar_container=update_tabbar_container,
    ):
        _emit_signal(
            getattr(host, "activeOutputSceneChanged", None),
            action.scene_key,
            False,
        )
        active_source_key = getattr(host, "active_source_key", None)
        if int(getattr(host, "active_set_index", 0)) == 0 and isinstance(
            active_source_key, str
        ):
            _emit_signal(
                getattr(host, "activeOutputGridChanged", None),
                active_source_key,
            )


def activate_output_scene(
    host: object,
    scene_key: str,
    *,
    scene_groups_by_key: Mapping[str, OutputCanvasSceneGroup],
    update_tabbar_container: Callable[[], None],
) -> bool:
    """Apply concrete scene navigation state through the Output host."""

    active_source_key = getattr(host, "active_source_key", None)
    plan = OutputCanvasNavigationController.scene_activation_plan(
        scene_key=scene_key,
        scene_groups_by_key=scene_groups_by_key,
        was_scene_overview=bool(getattr(host, "active_scene_overview", False)),
        active_source_key=active_source_key
        if isinstance(active_source_key, str)
        else None,
    )
    if plan is None:
        return False
    scene = scene_groups_by_key.get(plan.scene_key)
    if scene is None:
        return False
    source_groups_for_scene = {source.source_key: source for source in scene.sources}
    setattr(host, "active_scene_key", plan.scene_key)
    setattr(host, "active_scene_overview", False)
    setattr(host, "set_count", plan.set_count)
    setattr(host, "active_source_key", plan.active_source_key)

    source_tabs_controller = _source_tabs_controller(host)
    rebuild_source_tabs = getattr(source_tabs_controller, "rebuild_source_tabs", None)
    if callable(rebuild_source_tabs):
        rebuild_source_tabs(active_source_key=plan.active_source_key)

    if plan.followup == "activate_grid":
        activate_output_grid_for_source(
            host,
            plan.active_source_key,
            source_groups_by_key=source_groups_for_scene,
            update_tabbar_container=update_tabbar_container,
        )
    elif plan.followup == "activate_source_fallback" and plan.active_source_key:
        item = OutputCanvasNavigationController.source_fallback_item(
            source_groups_for_scene,
            plan.active_source_key,
            last_real_set_index=int(getattr(host, "last_real_set_index", 1)),
        )
        if item is not None:
            activate_output_item(
                host,
                plan.active_source_key,
                item,
                update_tabbar_container=update_tabbar_container,
            )

    sync_output_scene_selector_button(host)
    sync_output_source_selector_button(host)
    update_tabbar_container()
    return True


def activate_output_scene_overview(
    host: object,
    *,
    update_tabbar_container: Callable[[], None],
) -> bool:
    """Apply all-scenes overview navigation state through the Output host."""

    plan = OutputCanvasNavigationController.scene_overview_activation_plan(
        scene_count=int(getattr(host, "scene_count", 0)),
    )
    if plan is None:
        return False
    setattr(host, "active_scene_overview", True)
    setattr(host, "active_set_index", plan.active_set_index)
    setattr(host, "active_source_key", plan.active_source_key)
    setattr(host, "set_count", plan.set_count)
    if hasattr(host, "tabbar"):
        source_tabs_controller = _source_tabs_controller(host)
        rebuild_source_tabs = getattr(
            source_tabs_controller, "rebuild_source_tabs", None
        )
        if callable(rebuild_source_tabs):
            rebuild_source_tabs(active_source_key=None)
    sync_output_scene_selector_button(host)
    sync_output_set_selector_button(host)
    sync_output_source_selector_button(host)
    update_tabbar_container()
    interaction_controller = _interaction_controller(host)
    set_grid_interaction_locked = getattr(
        interaction_controller,
        "set_grid_interaction_locked",
        None,
    )
    if callable(set_grid_interaction_locked):
        set_grid_interaction_locked(True)
    return True


def activate_output_grid_for_source(
    host: object,
    source_key: str | None,
    *,
    source_groups_by_key: Mapping[str, OutputCanvasSourceGroup],
    emit_selection: bool = False,
    update_tabbar_container: Callable[[], None],
) -> bool:
    """Apply source-grid navigation state through the Output host."""

    plan = OutputCanvasNavigationController.grid_activation_plan(
        source_key=source_key,
        source_groups_by_key=source_groups_by_key,
    )
    if plan is None:
        return False
    setattr(host, "active_scene_overview", False)
    setattr(host, "active_source_key", plan.source_key)
    setattr(host, "active_set_index", 0)

    tabbar = getattr(host, "tabbar", None)
    tabbar_items = getattr(tabbar, "items", {})
    if isinstance(tabbar_items, Mapping) and plan.source_key in tabbar_items:
        set_current_item = getattr(tabbar, "setCurrentItem", None)
        if callable(set_current_item):
            setattr(host, "_suppress_tab_change", True)
            try:
                set_current_item(plan.source_key)
            finally:
                setattr(host, "_suppress_tab_change", False)

    sync_output_set_selector_button(host)
    sync_output_scene_selector_button(host)
    sync_output_source_selector_button(host)
    update_tabbar_container()

    interaction_controller = _interaction_controller(host)
    set_grid_interaction_locked = getattr(
        interaction_controller,
        "set_grid_interaction_locked",
        None,
    )
    if callable(set_grid_interaction_locked):
        set_grid_interaction_locked(True)
    if emit_selection:
        _emit_signal(getattr(host, "activeOutputGridChanged", None), plan.source_key)
    return True


def activate_output_item(
    host: object,
    source_key: str,
    item: OutputCanvasImageItem,
    *,
    emit_selection: bool = True,
    update_tabbar_container: Callable[[], None],
) -> None:
    """Apply concrete output item navigation state through the Output host."""

    plan = OutputCanvasNavigationController.item_activation_plan(
        source_key=source_key,
        item=item,
    )
    interaction_controller = _interaction_controller(host)
    set_grid_interaction_locked = getattr(
        interaction_controller,
        "set_grid_interaction_locked",
        None,
    )
    if callable(set_grid_interaction_locked):
        set_grid_interaction_locked(False)
    setattr(host, "active_scene_overview", False)
    setattr(host, "active_source_key", plan.source_key)
    setattr(host, "active_set_index", plan.active_set_index)
    setattr(host, "last_real_set_index", plan.last_real_set_index)

    tabbar = getattr(host, "tabbar", None)
    tabbar_items = getattr(tabbar, "items", {})
    if isinstance(tabbar_items, Mapping) and plan.source_key in tabbar_items:
        set_current_item = getattr(tabbar, "setCurrentItem", None)
        if callable(set_current_item):
            setattr(host, "_suppress_tab_change", True)
            try:
                set_current_item(plan.source_key)
            finally:
                setattr(host, "_suppress_tab_change", False)

    sync_output_set_selector_button(host)
    if hasattr(host, "tabbar"):
        source_tabs_controller = _source_tabs_controller(host)
        refresh_source_tab_tooltips = getattr(
            source_tabs_controller,
            "refresh_source_tab_tooltips",
            None,
        )
        if callable(refresh_source_tab_tooltips):
            refresh_source_tab_tooltips()
    sync_output_scene_selector_button(host)
    sync_output_source_selector_button(host)
    if emit_selection:
        _emit_signal(getattr(host, "activeOutputChanged", None), str(plan.image_id))
    update_tabbar_container()


def sync_output_scene_selector_button(host: object) -> None:
    """Refresh the normal scene selector from an opaque Output host."""

    button = getattr(host, "scene_selector_button", None)
    projection = getattr(host, "_output_projection", None)
    scene_groups = OutputCanvasRouteModel.scene_groups_by_key(
        projection if isinstance(projection, OutputCanvasProjection) else None,
        preview_scene_groups_by_key=getattr(
            getattr(host, "_output_revision_cache", None),
            "preview_scene_groups_by_key",
            {},
        ),
    )
    full_text = scene_selector_full_text(
        scene_groups.values(),
        active_scene_key=getattr(host, "active_scene_key", None),
        active_scene_overview=bool(getattr(host, "active_scene_overview", False)),
    )
    font_metrics = selector_font_metrics_for_widget(button)
    display_text = selector_display_text_for_metrics(
        full_text,
        font_metrics=font_metrics,
        text_elide_mode=getattr(host, "_selector_text_elide_mode", None),
        max_width=_SCENE_SELECTOR_MAX_WIDTH,
        horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
    )
    apply_scene_selector_button_state(
        button,
        full_text=full_text,
        display_text=display_text,
        width=selector_width_for_metrics_text(
            full_text,
            font_metrics=font_metrics,
            minimum_width=_SCENE_SELECTOR_MIN_WIDTH,
            maximum_width=_SCENE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SCENE_SELECTOR_HORIZONTAL_PADDING,
        ),
        scene_count=int(getattr(host, "scene_count", 0)),
    )


def sync_output_set_selector_button(host: object) -> None:
    """Refresh the normal set selector from an opaque Output host."""

    button = getattr(host, "set_selector_button", None)
    apply_set_selector_button_state(
        button,
        active_set_index=int(getattr(host, "active_set_index", 0)),
        active_scene_overview=bool(getattr(host, "active_scene_overview", False)),
        set_count=int(getattr(host, "set_count", 0)),
        grid_available=OutputCanvasRouteModel.grid_available_for_current_source(
            _visible_source_groups_for_host(host),
            getattr(host, "active_source_key", None),
        ),
    )


def sync_output_source_selector_button(host: object) -> None:
    """Refresh the collapsed source selector from an opaque Output host."""

    button = getattr(host, "source_selector_button", None)
    if button is None:
        return
    sources = _visible_source_groups_for_host(host)
    full_text = source_selector_full_text(
        sources.values(),
        active_source_key=getattr(host, "active_source_key", None),
    )
    font_metrics = selector_font_metrics_for_widget(button)
    display_text = selector_display_text_for_metrics(
        full_text,
        font_metrics=font_metrics,
        text_elide_mode=getattr(host, "_selector_text_elide_mode", None),
        max_width=_SOURCE_SELECTOR_MAX_WIDTH,
        horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
    )
    apply_source_selector_button_state(
        button,
        full_text=full_text,
        display_text=display_text,
        width=selector_width_for_metrics_text(
            full_text,
            font_metrics=font_metrics,
            minimum_width=_SOURCE_SELECTOR_MIN_WIDTH,
            maximum_width=_SOURCE_SELECTOR_MAX_WIDTH,
            horizontal_padding=_SOURCE_SELECTOR_HORIZONTAL_PADDING,
        ),
        source_tabs_collapsed=bool(getattr(host, "_source_tabs_collapsed", False)),
        tab_count=len(getattr(getattr(host, "tabbar", None), "items", {})),
        active_scene_overview=bool(getattr(host, "active_scene_overview", False)),
    )


def _visible_source_groups_for_host(
    host: object,
) -> dict[str, OutputCanvasSourceGroup]:
    """Return visible source groups for the host's current scene context."""

    projection = getattr(host, "_output_projection", None)
    typed_projection = (
        projection if isinstance(projection, OutputCanvasProjection) else None
    )
    scene_groups = OutputCanvasRouteModel.scene_groups_by_key(
        typed_projection,
        preview_scene_groups_by_key=getattr(
            getattr(host, "_output_revision_cache", None),
            "preview_scene_groups_by_key",
            {},
        ),
    )
    return OutputCanvasRouteModel.visible_source_groups_by_key(
        typed_projection,
        scene_groups_by_key=scene_groups,
        active_scene_overview=bool(getattr(host, "active_scene_overview", False)),
        active_scene_key=getattr(host, "active_scene_key", None),
        scene_count=int(getattr(host, "scene_count", 0)),
    )


def _source_tabs_controller(host: object) -> object | None:
    """Return runtime-owned source tabs with lightweight-host fallback."""

    runtime = getattr(host, "_runtime", None)
    navigation = getattr(runtime, "navigation", None)
    controller = getattr(navigation, "source_tabs", None)
    return controller or getattr(host, "_source_tabs_controller", None)


def _interaction_controller(host: object) -> object | None:
    """Return runtime-owned pointer interaction with lightweight-host fallback."""

    runtime = getattr(host, "_runtime", None)
    interaction = getattr(runtime, "interaction", None)
    controller = getattr(interaction, "pointer", None)
    return controller or getattr(host, "_interaction_controller", None)


def _emit_signal(signal: object, *args: object) -> None:
    """Emit a Qt-like signal when the host exposes one."""

    emit = getattr(signal, "emit", None)
    if callable(emit):
        emit(*args)


@dataclass(frozen=True, slots=True)
class SourceNavigationDisplay:
    """Describe the selected normal source-navigation render mode."""

    source_tabs_collapsed: bool
    show_source_tabs: bool
    show_source_selector: bool


@dataclass(frozen=True, slots=True)
class CompareNavigationVisibility:
    """Describe base-control visibility required for active compare navigation."""

    source_tabs_collapsed: bool
    show_scene_selector: bool
    show_set_selector: bool
    show_source_selector: bool


__all__ = [
    "CompareNavigationVisibility",
    "OutputGridActivationPlan",
    "OutputItemActivationPlan",
    "OutputCanvasNavigationController",
    "OutputSceneOverviewActivationPlan",
    "OutputSceneActivationFollowup",
    "OutputSceneActivationPlan",
    "OutputSceneSelectionAction",
    "OutputSceneSelectionKind",
    "OutputSetSelectionAction",
    "OutputSetSelectionKind",
    "OutputTabChangeAction",
    "OutputTabChangeKind",
    "SourceNavigationDisplay",
    "activate_output_grid_for_source",
    "activate_output_item",
    "activate_output_scene",
    "activate_output_scene_overview",
    "select_output_scene",
    "select_output_source",
    "select_output_set",
    "sync_output_scene_selector_button",
    "sync_output_set_selector_button",
    "sync_output_source_selector_button",
]
