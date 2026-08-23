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

"""Verify Output navigation measurement, placement, and visibility."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
)
from substitute.presentation.canvas.output.output_canvas_navigation_visibility import (
    OutputCanvasNavigationVisibilityPolicy,
)
from substitute.presentation.canvas.shared.output_nav_layout import OutputNavBarGeometry


from tests.presentation.canvas.output.navigation.controller_support import (
    WidgetStub,
    LayoutSpy,
    PlacedWidgetSpy,
    build_controller,
)


def test_available_tabbar_container_width_uses_canvas_width_padding() -> None:
    """Available navigation width should subtract horizontal canvas padding."""

    controller = build_controller(canvas_width=320)

    assert controller.available_tabbar_container_width() == 296


def test_available_tabbar_container_width_falls_back_without_canvas_width() -> None:
    """Missing canvas width should preserve the old effectively-unbounded fallback."""

    controller = build_controller(canvas_width=None)

    assert controller.available_tabbar_container_width() == 10_000


def test_preferred_tabbar_width_caches_positive_measurement() -> None:
    """Measured tabbar width should update the cached source-tabbar width."""

    cached: list[int] = []
    tabbar = WidgetStub(size_hint_width=180)
    controller = build_controller(tabbar=tabbar, cached_width=0, cached_updates=cached)

    width = controller.preferred_tabbar_width()

    assert width == 180
    assert cached == [180]


def test_preferred_tabbar_width_uses_cache_when_measurement_is_zero() -> None:
    """Cached width should preserve full tabbar width while the widget is hidden."""

    tabbar = WidgetStub(width_value=42, size_hint_width=0)
    controller = build_controller(tabbar=tabbar, cached_width=240)

    assert controller.preferred_tabbar_width() == 240


def test_measure_tabbar_preferred_width_uses_item_widths_spacing_and_margins() -> None:
    """Item fallback should include visible item widths, spacing, and margins."""

    layout = LayoutSpy(spacing_value=6, left=3, right=5)
    tabbar = SimpleNamespace(
        items={
            "one": WidgetStub(width_value=40, size_hint_width=0),
            "two": WidgetStub(size_hint_width=52),
        },
        sizeHint=lambda: SimpleNamespace(width=lambda: 0),
        layout=lambda: layout,
    )

    width = OutputCanvasNavigationController.measure_tabbar_preferred_width(tabbar)

    assert width == 40 + 52 + 6 + 3 + 5
    assert layout.invalidated is True
    assert layout.activated is True


def test_navigation_bar_width_supports_more_than_three_controls() -> None:
    """Extended navigation widths should include every positive control width."""

    width = OutputCanvasNavigationController.navigation_bar_width(
        (20, 0, 30, 40),
        gap=4,
        extra_pad=3,
    )

    assert width == 20 + 30 + 40 + (2 * 4) + (2 * 3)


def test_hide_compare_navigation_containers_hides_both_bars() -> None:
    """Invalid compare state should hide base and comparison navigation bars."""

    base = PlacedWidgetSpy()
    comparison = PlacedWidgetSpy()

    OutputCanvasNavigationController.hide_compare_navigation_containers(
        base_container=base,
        comparison_container=comparison,
    )

    assert base.hidden is True
    assert comparison.hidden is True


def test_apply_compare_navigation_visibility_hides_tabs_and_sets_controls() -> None:
    """Compare visibility application should own the base control toggles."""

    tabbar = PlacedWidgetSpy()
    scene_selector = PlacedWidgetSpy()
    set_selector = PlacedWidgetSpy()
    source_selector = PlacedWidgetSpy()

    OutputCanvasNavigationController.apply_compare_navigation_visibility(
        tabbar=tabbar,
        scene_selector=scene_selector,
        set_selector=set_selector,
        source_selector=source_selector,
        visibility=OutputCanvasNavigationVisibilityPolicy.compare(
            scene_count=1,
            set_count=3,
        ),
    )

    assert tabbar.hidden is True
    assert scene_selector.visible is False
    assert set_selector.visible is True
    assert source_selector.visible is True


def test_place_compare_bar_places_visible_controls_and_hides_empty_widths() -> None:
    """Compare bar placement should mutate only controls with visible widths."""

    container = PlacedWidgetSpy()
    background = PlacedWidgetSpy()
    first = PlacedWidgetSpy()
    hidden = PlacedWidgetSpy()
    second = PlacedWidgetSpy()

    OutputCanvasNavigationController.place_compare_bar(
        container=container,
        background=background,
        geometry=OutputNavBarGeometry(x=12, y=24, width=190, height=42, stacked=False),
        controls=((first, 50), (hidden, 0), (second, 70)),
        control_h=30,
        extra_pad=6,
        gap=8,
    )

    assert container.geometries == [(12, 24, 190, 42)]
    assert background.geometries == [(0, 0, 190, 42)]
    assert first.visible is True
    assert first.geometries == [(6, 6, 50, 30)]
    assert first.raised is True
    assert hidden.visible is False
    assert hidden.geometries == []
    assert second.visible is True
    assert second.geometries == [(64, 6, 70, 30)]
    assert second.raised is True
    assert background.lowered is True
    assert container.shown is True


def test_hide_source_navigation_hides_all_optional_controls() -> None:
    """Source navigation hide should cover the full normal navigation group."""

    container = PlacedWidgetSpy()
    tabbar = PlacedWidgetSpy()
    set_selector = PlacedWidgetSpy()
    scene_selector = PlacedWidgetSpy()
    source_selector = PlacedWidgetSpy()

    OutputCanvasNavigationController.hide_source_navigation(
        container=container,
        tabbar=tabbar,
        set_selector=set_selector,
        scene_selector=scene_selector,
        source_selector=source_selector,
    )

    assert container.hidden is True
    assert tabbar.hidden is True
    assert set_selector.hidden is True
    assert scene_selector.hidden is True
    assert source_selector.hidden is True


def test_set_source_navigation_visibility_applies_each_control_state() -> None:
    """Source navigation visibility should not be coordinated by the host widget."""

    tabbar = PlacedWidgetSpy()
    set_selector = PlacedWidgetSpy()
    scene_selector = PlacedWidgetSpy()
    source_selector = PlacedWidgetSpy()

    OutputCanvasNavigationController.set_source_navigation_visibility(
        tabbar=tabbar,
        set_selector=set_selector,
        scene_selector=scene_selector,
        source_selector=source_selector,
        show_scene_selector=True,
        show_source_tabs=False,
        show_source_selector=True,
        show_set_selector=False,
    )

    assert scene_selector.visible is True
    assert tabbar.visible is False
    assert source_selector.visible is True
    assert set_selector.visible is False


def test_place_source_bar_places_controls_in_navigation_order() -> None:
    """Source bar placement should own geometry and z-order for visible controls."""

    container = PlacedWidgetSpy()
    background = PlacedWidgetSpy()
    tabbar = PlacedWidgetSpy()
    set_selector = PlacedWidgetSpy()
    scene_selector = PlacedWidgetSpy()
    source_selector = PlacedWidgetSpy()

    OutputCanvasNavigationController.place_source_bar(
        container=container,
        background=background,
        geometry=OutputNavBarGeometry(x=8, y=320, width=200, height=42, stacked=False),
        tabbar=tabbar,
        set_selector=set_selector,
        scene_selector=scene_selector,
        source_selector=source_selector,
        show_scene_selector=True,
        show_source_tabs=True,
        show_source_selector=False,
        show_set_selector=True,
        scene_width=40,
        set_width=30,
        tabbar_width=100,
        source_width=70,
        tabbar_height=28,
        control_height=30,
        extra_pad=6,
        gap=8,
    )

    assert container.geometries == [(8, 320, 200, 42)]
    assert background.geometries == [(0, 0, 200, 42)]
    assert scene_selector.geometries == [(6, 6, 40, 30)]
    assert set_selector.geometries == [(54, 6, 30, 30)]
    assert tabbar.geometries == [(92, 6, 100, 28)]
    assert source_selector.geometries == []
    assert tabbar.raised is True
    assert scene_selector.raised is True
    assert set_selector.raised is True
    assert source_selector.raised is False
    assert background.lowered is True


def test_button_width_uses_current_width_then_size_hint() -> None:
    """Button width should prefer settled geometry and fall back to size hint."""

    assert (
        OutputCanvasNavigationController.button_width(
            WidgetStub(width_value=36, size_hint_width=80),
        )
        == 36
    )
    assert (
        OutputCanvasNavigationController.button_width(
            WidgetStub(width_value=0, size_hint_width=80),
        )
        == 80
    )
