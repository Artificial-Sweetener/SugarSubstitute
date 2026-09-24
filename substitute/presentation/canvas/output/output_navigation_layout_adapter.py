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

"""Apply responsive Output navigation geometry to widget-like hosts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.presentation.canvas.output.output_canvas_navigation_measurement import (
    OutputCanvasNavigationMeasurement,
)
from substitute.presentation.canvas.output.output_canvas_navigation_visibility import (
    CompareNavigationVisibility,
)
from substitute.presentation.canvas.shared.output_nav_layout import (
    OutputNavBarGeometry,
    OutputNavControlWidths,
    navigation_bar_width,
)


@dataclass(frozen=True, slots=True)
class OutputNavigationLayoutAdapter(OutputCanvasNavigationMeasurement):
    """Measure and place floating Output navigation controls."""

    canvas_width: Callable[[], int | None]
    tabbar: Callable[[], object]
    cached_source_tabbar_width: Callable[[], int]
    set_cached_source_tabbar_width: Callable[[int], None]

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
        """Apply base-control visibility before compare geometry updates."""

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
        """Place one compare navigation bar and toggle its controls."""

        cls.set_widget_geometry(
            container,
            geometry.x,
            geometry.y,
            geometry.width,
            geometry.height,
        )
        cls.set_widget_geometry(background, 0, 0, geometry.width, geometry.height)
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
        cls.lower_widget(background)
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
        """Place one compare control or hide it when width is empty."""

        set_visible = getattr(control, "setVisible", None)
        if width <= 0:
            if callable(set_visible):
                set_visible(False)
            return
        if callable(set_visible):
            set_visible(True)
        OutputNavigationLayoutAdapter.set_widget_geometry(
            control,
            x,
            y,
            width,
            height,
        )
        OutputNavigationLayoutAdapter.raise_widget(control)

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
            cls.set_widget_geometry(tabbar, x, extra_pad, tabbar_width, tabbar_height)
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
        """Hide a widget-like object when supported."""

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
        """Return current button width with size-hint fallback."""

        width = getattr(button, "width", None)
        value = int(width()) if callable(width) else 0
        return value if value > 0 else cls.size_hint_width(button)


__all__ = ["OutputNavigationLayoutAdapter"]
