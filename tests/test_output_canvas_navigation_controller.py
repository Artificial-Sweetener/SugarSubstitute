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

"""Verify Output canvas navigation controller behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from uuid import uuid4

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.domain.workflow import ImageMeta
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    OutputCanvasNavigationController,
    activate_output_grid_for_source,
    activate_output_item,
    activate_output_scene,
    activate_output_scene_overview,
    sync_output_scene_selector_button,
    sync_output_set_selector_button,
    sync_output_source_selector_button,
)
from substitute.presentation.canvas.shared.output_nav_layout import OutputNavBarGeometry


def test_available_tabbar_container_width_uses_canvas_width_padding() -> None:
    """Available navigation width should subtract horizontal canvas padding."""

    controller = _controller(canvas_width=320)

    assert controller.available_tabbar_container_width() == 296


def test_available_tabbar_container_width_falls_back_without_canvas_width() -> None:
    """Missing canvas width should preserve the old effectively-unbounded fallback."""

    controller = _controller(canvas_width=None)

    assert controller.available_tabbar_container_width() == 10_000


def test_preferred_tabbar_width_caches_positive_measurement() -> None:
    """Measured tabbar width should update the cached source-tabbar width."""

    cached: list[int] = []
    tabbar = _Widget(size_hint_width=180)
    controller = _controller(tabbar=tabbar, cached_width=0, cached_updates=cached)

    width = controller.preferred_tabbar_width()

    assert width == 180
    assert cached == [180]


def test_preferred_tabbar_width_uses_cache_when_measurement_is_zero() -> None:
    """Cached width should preserve full tabbar width while the widget is hidden."""

    tabbar = _Widget(width_value=42, size_hint_width=0)
    controller = _controller(tabbar=tabbar, cached_width=240)

    assert controller.preferred_tabbar_width() == 240


def test_measure_tabbar_preferred_width_uses_item_widths_spacing_and_margins() -> None:
    """Item fallback should include visible item widths, spacing, and margins."""

    layout = _Layout(spacing_value=6, left=3, right=5)
    tabbar = SimpleNamespace(
        items={
            "one": _Widget(width_value=40, size_hint_width=0),
            "two": _Widget(size_hint_width=52),
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


def test_source_navigation_display_expands_when_width_fits() -> None:
    """Source navigation should render tabs when expanded tabs fit available space."""

    display = OutputCanvasNavigationController.source_navigation_display(
        show_source_navigation=True,
        has_source_selector=True,
        expanded_width=120,
        available_width=160,
    )

    assert display.source_tabs_collapsed is False
    assert display.show_source_tabs is True
    assert display.show_source_selector is False


def test_source_navigation_display_collapses_when_width_overflows() -> None:
    """Source navigation should use the compact selector when tabs overflow."""

    display = OutputCanvasNavigationController.source_navigation_display(
        show_source_navigation=True,
        has_source_selector=True,
        expanded_width=200,
        available_width=160,
    )

    assert display.source_tabs_collapsed is True
    assert display.show_source_tabs is False
    assert display.show_source_selector is True


def test_source_navigation_display_requires_selector_to_collapse() -> None:
    """Missing compact selector should keep tab rendering when navigation is shown."""

    display = OutputCanvasNavigationController.source_navigation_display(
        show_source_navigation=True,
        has_source_selector=False,
        expanded_width=200,
        available_width=160,
    )

    assert display.source_tabs_collapsed is False
    assert display.show_source_tabs is True
    assert display.show_source_selector is False


def test_source_navigation_display_hides_all_source_modes_when_disabled() -> None:
    """Disabled source navigation should hide expanded and collapsed source controls."""

    display = OutputCanvasNavigationController.source_navigation_display(
        show_source_navigation=False,
        has_source_selector=True,
        expanded_width=200,
        available_width=160,
    )

    assert display.source_tabs_collapsed is False
    assert display.show_source_tabs is False
    assert display.show_source_selector is False


def test_compare_navigation_visibility_sets_base_control_modes() -> None:
    """Active compare mode should collapse source tabs and expose base selectors."""

    visibility = OutputCanvasNavigationController.compare_navigation_visibility(
        scene_count=2,
        set_count=1,
    )

    assert visibility.source_tabs_collapsed is True
    assert visibility.show_scene_selector is True
    assert visibility.show_set_selector is False
    assert visibility.show_source_selector is True


def test_hide_compare_navigation_containers_hides_both_bars() -> None:
    """Invalid compare state should hide base and comparison navigation bars."""

    base = _PlacedWidget()
    comparison = _PlacedWidget()

    OutputCanvasNavigationController.hide_compare_navigation_containers(
        base_container=base,
        comparison_container=comparison,
    )

    assert base.hidden is True
    assert comparison.hidden is True


def test_apply_compare_navigation_visibility_hides_tabs_and_sets_controls() -> None:
    """Compare visibility application should own the base control toggles."""

    tabbar = _PlacedWidget()
    scene_selector = _PlacedWidget()
    set_selector = _PlacedWidget()
    source_selector = _PlacedWidget()

    OutputCanvasNavigationController.apply_compare_navigation_visibility(
        tabbar=tabbar,
        scene_selector=scene_selector,
        set_selector=set_selector,
        source_selector=source_selector,
        visibility=OutputCanvasNavigationController.compare_navigation_visibility(
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

    container = _PlacedWidget()
    background = _PlacedWidget()
    first = _PlacedWidget()
    hidden = _PlacedWidget()
    second = _PlacedWidget()

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

    container = _PlacedWidget()
    tabbar = _PlacedWidget()
    set_selector = _PlacedWidget()
    scene_selector = _PlacedWidget()
    source_selector = _PlacedWidget()

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

    tabbar = _PlacedWidget()
    set_selector = _PlacedWidget()
    scene_selector = _PlacedWidget()
    source_selector = _PlacedWidget()

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

    container = _PlacedWidget()
    background = _PlacedWidget()
    tabbar = _PlacedWidget()
    set_selector = _PlacedWidget()
    scene_selector = _PlacedWidget()
    source_selector = _PlacedWidget()

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
            _Widget(width_value=36, size_hint_width=80),
        )
        == 36
    )
    assert (
        OutputCanvasNavigationController.button_width(
            _Widget(width_value=0, size_hint_width=80),
        )
        == 80
    )


def test_source_fallback_item_prefers_nearest_last_real_set() -> None:
    """Source fallback should preserve the user's last concrete set when possible."""

    first_item = _output_item(set_index=1)
    nearest_item = _output_item(set_index=3)
    source = OutputCanvasSourceGroup(
        source_key="source-a",
        label="Source A",
        images_by_set={1: first_item, 3: nearest_item},
    )

    item = OutputCanvasNavigationController.source_fallback_item(
        {"source-a": source},
        "source-a",
        last_real_set_index=4,
    )

    assert item is nearest_item


def test_source_fallback_item_returns_none_for_unknown_source() -> None:
    """Missing sources should not produce a fallback activation item."""

    item = OutputCanvasNavigationController.source_fallback_item(
        {},
        "missing-source",
        last_real_set_index=2,
    )

    assert item is None


def test_tab_change_action_ignores_suppressed_signal() -> None:
    """Suppressed tabbar changes should not trigger navigation work."""

    action = OutputCanvasNavigationController.tab_change_action(
        route_key="wf:text",
        suppress_tab_change=True,
        active_set_index=1,
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1,))},
    )

    assert action.kind == "none"
    assert action.source_key == "wf:text"
    assert action.item is None


def test_tab_change_action_activates_grid_for_grid_set() -> None:
    """Grid mode tab changes should keep source-grid activation when available."""

    action = OutputCanvasNavigationController.tab_change_action(
        route_key="wf:text",
        suppress_tab_change=False,
        active_set_index=0,
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1, 2))},
    )

    assert action.kind == "activate_grid"
    assert action.source_key == "wf:text"


def test_tab_change_action_falls_back_when_grid_is_missing() -> None:
    """Grid mode tab changes should fall back when a source cannot render a grid."""

    action = OutputCanvasNavigationController.tab_change_action(
        route_key="wf:text",
        suppress_tab_change=False,
        active_set_index=0,
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1,))},
    )

    assert action.kind == "activate_source_fallback"
    assert action.source_key == "wf:text"


def test_tab_change_action_returns_concrete_output_item() -> None:
    """Concrete set tab changes should resolve the selected source item."""

    action = OutputCanvasNavigationController.tab_change_action(
        route_key="wf:text",
        suppress_tab_change=False,
        active_set_index=2,
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1, 2))},
    )

    assert action.kind == "activate_output_item"
    assert action.source_key == "wf:text"
    assert action.item is not None
    assert action.item.set_index == 2


def test_tab_change_action_reports_unknown_source() -> None:
    """Concrete set tab changes should report unknown routes for widget logging."""

    action = OutputCanvasNavigationController.tab_change_action(
        route_key="missing",
        suppress_tab_change=False,
        active_set_index=1,
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1,))},
    )

    assert action.kind == "unknown_source"
    assert action.source_key == "missing"
    assert action.item is None


def test_scene_selection_action_activates_scene_overview_for_all() -> None:
    """The All scene picker row should request scene-overview activation."""

    action = OutputCanvasNavigationController.scene_selection_action("all")

    assert action.kind == "activate_scene_overview"
    assert action.scene_key == "all"


def test_scene_selection_action_activates_concrete_scene() -> None:
    """Concrete scene picker rows should request scoped scene activation."""

    action = OutputCanvasNavigationController.scene_selection_action("portrait")

    assert action.kind == "activate_scene"
    assert action.scene_key == "portrait"


def test_set_selection_action_activates_grid_set() -> None:
    """Set index zero should request source-grid activation for the active source."""

    action = OutputCanvasNavigationController.set_selection_action(
        set_index=0,
        active_source_key="wf:text",
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1, 2))},
    )

    assert action.kind == "activate_grid"
    assert action.source_key == "wf:text"
    assert action.item is None


def test_set_selection_action_returns_active_source_item() -> None:
    """Concrete set selection should prefer the active source when available."""

    action = OutputCanvasNavigationController.set_selection_action(
        set_index=2,
        active_source_key="wf:text",
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1, 2))},
    )

    assert action.kind == "activate_output_item"
    assert action.source_key == "wf:text"
    assert action.item is not None
    assert action.item.set_index == 2


def test_set_selection_action_falls_back_to_first_source_for_set() -> None:
    """Concrete set selection should use the first source containing the set."""

    action = OutputCanvasNavigationController.set_selection_action(
        set_index=2,
        active_source_key="missing",
        source_groups_by_key={
            "wf:text": _source("wf:text", set_indexes=(1,)),
            "wf:upscale": _source("wf:upscale", set_indexes=(2,)),
        },
    )

    assert action.kind == "activate_output_item"
    assert action.source_key == "wf:upscale"
    assert action.item is not None
    assert action.item.set_index == 2


def test_set_selection_action_returns_none_without_target() -> None:
    """Missing set targets should not ask the widget to mutate visible state."""

    action = OutputCanvasNavigationController.set_selection_action(
        set_index=3,
        active_source_key="wf:text",
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=())},
    )

    assert action.kind == "none"
    assert action.source_key is None
    assert action.item is None


def test_scene_activation_plan_returns_none_for_unknown_scene() -> None:
    """Unknown scene activation should not ask the widget to mutate visible state."""

    plan = OutputCanvasNavigationController.scene_activation_plan(
        scene_key="missing",
        scene_groups_by_key={},
        was_scene_overview=False,
        active_source_key="wf:text",
    )

    assert plan is None


def test_scene_activation_plan_prefers_representative_from_overview() -> None:
    """Leaving overview should prefer the scene representative source."""

    plan = OutputCanvasNavigationController.scene_activation_plan(
        scene_key="portrait",
        scene_groups_by_key={
            "portrait": _scene(
                "portrait",
                sources=(
                    _source("wf:text", set_indexes=(1,)),
                    _source("wf:upscale", set_indexes=(1, 2)),
                ),
                representative_source_key="wf:upscale",
            )
        },
        was_scene_overview=True,
        active_source_key="wf:text",
    )

    assert plan is not None
    assert plan.scene_key == "portrait"
    assert plan.active_source_key == "wf:upscale"
    assert plan.set_count == 2
    assert plan.followup == "activate_grid"


def test_scene_activation_plan_preserves_previous_source_when_possible() -> None:
    """Scene activation should preserve the active source outside overview."""

    plan = OutputCanvasNavigationController.scene_activation_plan(
        scene_key="portrait",
        scene_groups_by_key={
            "portrait": _scene(
                "portrait",
                sources=(
                    _source("wf:text", set_indexes=(1,)),
                    _source("wf:upscale", set_indexes=(1,)),
                ),
                representative_source_key="wf:upscale",
            )
        },
        was_scene_overview=False,
        active_source_key="wf:text",
    )

    assert plan is not None
    assert plan.active_source_key == "wf:text"
    assert plan.set_count == 1
    assert plan.followup == "activate_source_fallback"


def test_scene_activation_plan_reports_no_followup_without_sources() -> None:
    """Empty scenes should activate without requesting source follow-up."""

    plan = OutputCanvasNavigationController.scene_activation_plan(
        scene_key="empty",
        scene_groups_by_key={"empty": _scene("empty", sources=())},
        was_scene_overview=False,
        active_source_key=None,
    )

    assert plan is not None
    assert plan.active_source_key is None
    assert plan.set_count == 0
    assert plan.followup == "none"


def test_activate_output_scene_applies_host_state_and_source_grid_followup() -> None:
    """Concrete scene adapter should own scene state and grid follow-up mutation."""

    calls: list[tuple[str, object]] = []
    host = SimpleNamespace(
        active_scene_overview=True,
        active_source_key="wf:text",
        active_set_index=1,
        set_count=1,
        last_real_set_index=1,
        _suppress_tab_change=False,
        tabbar=SimpleNamespace(
            items={"wf:upscale": object()},
            setCurrentItem=lambda key: calls.append(("tab", key)),
        ),
        _source_tabs_controller=SimpleNamespace(
            rebuild_source_tabs=lambda *, active_source_key: calls.append(
                ("rebuild", active_source_key)
            )
        ),
        _interaction_controller=SimpleNamespace(
            set_grid_interaction_locked=lambda locked: calls.append(("locked", locked))
        ),
    )

    activated = activate_output_scene(
        host,
        "portrait",
        scene_groups_by_key={
            "portrait": _scene(
                "portrait",
                sources=(
                    _source("wf:text", set_indexes=(1,)),
                    _source("wf:upscale", set_indexes=(1, 2)),
                ),
                representative_source_key="wf:upscale",
            )
        },
        update_tabbar_container=lambda: calls.append(("tabbar", None)),
    )

    assert activated is True
    assert host.active_scene_key == "portrait"
    assert host.active_scene_overview is False
    assert host.active_source_key == "wf:upscale"
    assert host.active_set_index == 0
    assert host.set_count == 2
    assert host._suppress_tab_change is False
    assert calls == [
        ("rebuild", "wf:upscale"),
        ("tab", "wf:upscale"),
        ("tabbar", None),
        ("locked", True),
        ("tabbar", None),
    ]


def test_activate_output_scene_rejects_unknown_scene() -> None:
    """Concrete scene adapter should not mutate host state for unknown scenes."""

    host = SimpleNamespace(active_scene_key="old")

    activated = activate_output_scene(
        host,
        "missing",
        scene_groups_by_key={},
        update_tabbar_container=lambda: None,
    )

    assert activated is False
    assert host.active_scene_key == "old"


def test_sync_output_scene_selector_button_applies_host_scene_label() -> None:
    """Scene selector adapter should render the active scene through host state."""

    scene = _scene("portrait", sources=())
    button = _SelectorButton()
    host = SimpleNamespace(
        _output_projection=OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
            scene_groups=(scene,),
            active_scene_key="portrait",
            active_scene_overview=False,
            scene_count=2,
        ),
        scene_selector_button=button,
        active_scene_key="portrait",
        active_scene_overview=False,
        scene_count=2,
    )

    sync_output_scene_selector_button(host)

    assert button.text == "portrait"
    assert button.visible is True


def test_sync_output_set_selector_button_applies_host_set_state() -> None:
    """Set selector adapter should render set state from the opaque host."""

    source = _source("wf:upscale", set_indexes=(1, 2))
    button = _SelectorButton()
    host = SimpleNamespace(
        _output_projection=OutputCanvasProjection(
            sources=(source,),
            active_source_key="wf:upscale",
            active_set_index=2,
            active_uuid=None,
            set_count=2,
        ),
        set_selector_button=button,
        active_source_key="wf:upscale",
        active_set_index=2,
        active_scene_overview=False,
        set_count=2,
        scene_count=0,
    )

    sync_output_set_selector_button(host)

    assert button.text == "2"
    assert button.visible is True


def test_sync_output_source_selector_button_applies_host_source_label() -> None:
    """Source selector adapter should render the active source through host state."""

    source = _source("wf:upscale", set_indexes=(1,))
    other_source = _source("wf:text", set_indexes=(1,))
    button = _SelectorButton()
    host = SimpleNamespace(
        _output_projection=OutputCanvasProjection(
            sources=(other_source, source),
            active_source_key="wf:upscale",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        ),
        source_selector_button=button,
        active_source_key="wf:upscale",
        active_scene_overview=False,
        _source_tabs_collapsed=True,
        tabbar=SimpleNamespace(
            items={"wf:text": object(), "wf:upscale": object()},
        ),
    )

    sync_output_source_selector_button(host)

    assert button.text == "wf:upscale"
    assert button.visible is True


def test_grid_activation_plan_uses_explicit_grid_source() -> None:
    """Explicit source-grid activation should accept sources with multiple sets."""

    plan = OutputCanvasNavigationController.grid_activation_plan(
        source_key="wf:text",
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1, 2))},
    )

    assert plan is not None
    assert plan.source_key == "wf:text"


def test_grid_activation_plan_uses_first_grid_source_when_missing() -> None:
    """Missing source input should fall back to the first source that can grid."""

    plan = OutputCanvasNavigationController.grid_activation_plan(
        source_key=None,
        source_groups_by_key={
            "wf:text": _source("wf:text", set_indexes=(1,)),
            "wf:upscale": _source("wf:upscale", set_indexes=(1, 2)),
        },
    )

    assert plan is not None
    assert plan.source_key == "wf:upscale"


def test_grid_activation_plan_rejects_unknown_source() -> None:
    """Unknown source-grid activation should not mutate visible state."""

    assert (
        OutputCanvasNavigationController.grid_activation_plan(
            source_key="missing",
            source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1, 2))},
        )
        is None
    )


def test_grid_activation_plan_rejects_single_item_source() -> None:
    """Sources without multiple sets cannot render a source grid."""

    assert (
        OutputCanvasNavigationController.grid_activation_plan(
            source_key="wf:text",
            source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1,))},
        )
        is None
    )


def test_activate_output_grid_for_source_applies_host_state_and_signal() -> None:
    """Source-grid adapter should own host mutation around the pure plan."""

    calls: list[tuple[str, object]] = []
    signal = _Signal()
    host = SimpleNamespace(
        active_scene_overview=True,
        active_source_key=None,
        active_set_index=3,
        _suppress_tab_change=False,
        tabbar=SimpleNamespace(
            items={"wf:upscale": object()},
            setCurrentItem=lambda key: calls.append(("tab", key)),
        ),
        _interaction_controller=SimpleNamespace(
            set_grid_interaction_locked=lambda locked: calls.append(("locked", locked))
        ),
        activeOutputGridChanged=signal,
    )

    activated = activate_output_grid_for_source(
        host,
        "wf:upscale",
        source_groups_by_key={"wf:upscale": _source("wf:upscale", set_indexes=(1, 2))},
        emit_selection=True,
        update_tabbar_container=lambda: calls.append(("tabbar", None)),
    )

    assert activated is True
    assert host.active_scene_overview is False
    assert host.active_source_key == "wf:upscale"
    assert host.active_set_index == 0
    assert host._suppress_tab_change is False
    assert signal.calls == [("wf:upscale",)]
    assert calls == [
        ("tab", "wf:upscale"),
        ("tabbar", None),
        ("locked", True),
    ]


def test_activate_output_grid_for_source_rejects_single_item_source() -> None:
    """Source-grid adapter should not mutate host state without a grid source."""

    host = SimpleNamespace(active_source_key="wf:text", active_set_index=1)

    activated = activate_output_grid_for_source(
        host,
        "wf:text",
        source_groups_by_key={"wf:text": _source("wf:text", set_indexes=(1,))},
        update_tabbar_container=lambda: None,
    )

    assert activated is False
    assert host.active_source_key == "wf:text"
    assert host.active_set_index == 1


def test_scene_overview_activation_plan_rejects_single_scene() -> None:
    """All-scenes overview should activate only when multiple scenes exist."""

    assert (
        OutputCanvasNavigationController.scene_overview_activation_plan(scene_count=1)
        is None
    )


def test_scene_overview_activation_plan_sets_overview_navigation_state() -> None:
    """All-scenes overview activation should expose the existing overview defaults."""

    plan = OutputCanvasNavigationController.scene_overview_activation_plan(
        scene_count=2,
    )

    assert plan is not None
    assert plan.active_set_index == 1
    assert plan.active_source_key is None
    assert plan.set_count == 0


def test_activate_output_scene_overview_applies_host_state_and_chrome_updates() -> None:
    """Scene overview adapter should own host mutation around the pure plan."""

    calls: list[tuple[str, object]] = []
    host = SimpleNamespace(
        scene_count=2,
        active_scene_overview=False,
        active_set_index=3,
        active_source_key="wf:text",
        set_count=3,
        tabbar=object(),
        _source_tabs_controller=SimpleNamespace(
            rebuild_source_tabs=lambda *, active_source_key: calls.append(
                ("rebuild", active_source_key)
            )
        ),
        _interaction_controller=SimpleNamespace(
            set_grid_interaction_locked=lambda locked: calls.append(("locked", locked))
        ),
    )

    activated = activate_output_scene_overview(
        host,
        update_tabbar_container=lambda: calls.append(("tabbar", None)),
    )

    assert activated is True
    assert host.active_scene_overview is True
    assert host.active_set_index == 1
    assert host.active_source_key is None
    assert host.set_count == 0
    assert calls == [
        ("rebuild", None),
        ("tabbar", None),
        ("locked", True),
    ]


def test_activate_output_scene_overview_rejects_single_scene() -> None:
    """Scene overview adapter should not mutate host state without overview."""

    host = SimpleNamespace(scene_count=1, active_scene_overview=False)

    assert (
        activate_output_scene_overview(
            host,
            update_tabbar_container=lambda: None,
        )
        is False
    )
    assert host.active_scene_overview is False


def test_item_activation_plan_uses_item_identity_and_set() -> None:
    """Concrete output item activation should expose item-derived state."""

    item = _output_item(set_index=3)

    plan = OutputCanvasNavigationController.item_activation_plan(
        source_key="wf:upscale",
        item=item,
    )

    assert plan.source_key == "wf:upscale"
    assert plan.active_set_index == 3
    assert plan.last_real_set_index == 3
    assert plan.image_id == item.image_id


def test_activate_output_item_applies_host_state_tabs_tooltips_and_signal() -> None:
    """Concrete output adapter should own host mutation around the pure plan."""

    item = _output_item(set_index=3)
    calls: list[tuple[str, object]] = []
    signal = _Signal()
    host = SimpleNamespace(
        active_scene_overview=True,
        active_source_key=None,
        active_set_index=1,
        last_real_set_index=1,
        _suppress_tab_change=False,
        tabbar=SimpleNamespace(
            items={"wf:upscale": object()},
            setCurrentItem=lambda key: calls.append(("tab", key)),
        ),
        _interaction_controller=SimpleNamespace(
            set_grid_interaction_locked=lambda locked: calls.append(("locked", locked))
        ),
        _source_tabs_controller=SimpleNamespace(
            refresh_source_tab_tooltips=lambda: calls.append(("tooltips", None))
        ),
        activeOutputChanged=signal,
    )

    activate_output_item(
        host,
        "wf:upscale",
        item,
        update_tabbar_container=lambda: calls.append(("tabbar", None)),
    )

    assert host.active_scene_overview is False
    assert host.active_source_key == "wf:upscale"
    assert host.active_set_index == 3
    assert host.last_real_set_index == 3
    assert host._suppress_tab_change is False
    assert signal.calls == [(str(item.image_id),)]
    assert calls == [
        ("locked", False),
        ("tab", "wf:upscale"),
        ("tooltips", None),
        ("tabbar", None),
    ]


def test_activate_output_item_can_skip_selection_signal() -> None:
    """Concrete output adapter should preserve silent fallback activation paths."""

    item = _output_item(set_index=2)
    signal = _Signal()
    host = SimpleNamespace(
        tabbar=SimpleNamespace(items={}),
        activeOutputChanged=signal,
    )

    activate_output_item(
        host,
        "wf:text",
        item,
        emit_selection=False,
        update_tabbar_container=lambda: None,
    )

    assert host.active_scene_overview is False
    assert host.active_source_key == "wf:text"
    assert host.active_set_index == 2
    assert host.last_real_set_index == 2
    assert signal.calls == []


@dataclass(slots=True)
class _Signal:
    """Small signal double that records emitted payloads."""

    calls: list[tuple[object, ...]] = field(default_factory=list)

    def emit(self, *args: object) -> None:
        """Record emitted signal arguments."""

        self.calls.append(args)


class _SelectorButton:
    """Record selector button writes from navigation adapters."""

    def __init__(self) -> None:
        """Create an unset selector button."""

        self.text = ""
        self.visible = False
        self.fixed_width = 0
        self.tooltip = ""

    def setText(self, text: str) -> None:
        """Record selector text."""

        self.text = text

    def setVisible(self, visible: bool) -> None:
        """Record selector visibility."""

        self.visible = visible

    def setFixedWidth(self, width: int) -> None:
        """Record selector width."""

        self.fixed_width = width

    def setToolTip(self, tooltip: str) -> None:
        """Record selector tooltip."""

        self.tooltip = tooltip

    def fontMetrics(self) -> object:  # noqa: N802
        """Return deterministic text metrics."""

        return SimpleNamespace(horizontalAdvance=lambda text: len(text) * 8)


@dataclass(slots=True)
class _Widget:
    """Small widget double exposing width and sizeHint."""

    width_value: int = 0
    size_hint_width: int = 0

    def ensurePolished(self) -> None:  # noqa: N802
        """No-op Qt polish hook."""

    def adjustSize(self) -> None:  # noqa: N802
        """No-op Qt size adjustment hook."""

    def sizeHint(self) -> object:  # noqa: N802
        """Return a minimal Qt-like size hint."""

        return SimpleNamespace(width=lambda: self.size_hint_width)

    def width(self) -> int:
        """Return configured width."""

        return self.width_value


@dataclass(slots=True)
class _Layout:
    """Small layout double exposing spacing and margins."""

    spacing_value: int
    left: int
    right: int
    invalidated: bool = False
    activated: bool = False

    def invalidate(self) -> None:
        """Record invalidation."""

        self.invalidated = True

    def activate(self) -> None:
        """Record activation."""

        self.activated = True

    def spacing(self) -> int:
        """Return configured spacing."""

        return self.spacing_value

    def contentsMargins(self) -> object:  # noqa: N802
        """Return minimal Qt-like margins."""

        return SimpleNamespace(
            left=lambda: self.left,
            right=lambda: self.right,
        )


@dataclass(slots=True)
class _PlacedWidget:
    """Small widget double that records placement and z-order calls."""

    geometries: list[tuple[int, int, int, int]] = field(default_factory=list)
    visible: bool | None = None
    hidden: bool = False
    raised: bool = False
    lowered: bool = False
    shown: bool = False

    def setGeometry(self, x: int, y: int, width: int, height: int) -> None:  # noqa: N802
        """Record assigned geometry."""

        self.geometries.append((x, y, width, height))

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Record assigned visibility."""

        self.visible = visible

    def hide(self) -> None:
        """Record hide request."""

        self.hidden = True
        self.visible = False

    def raise_(self) -> None:
        """Record raise request."""

        self.raised = True

    def lower(self) -> None:
        """Record lower request."""

        self.lowered = True

    def show(self) -> None:
        """Record show request."""

        self.shown = True


def _controller(
    *,
    canvas_width: int | None = 400,
    tabbar: object | None = None,
    cached_width: int = 0,
    cached_updates: list[int] | None = None,
) -> OutputCanvasNavigationController:
    """Return a navigation controller with deterministic collaborators."""

    updates = cached_updates if cached_updates is not None else []
    return OutputCanvasNavigationController(
        canvas_width=lambda: canvas_width,
        tabbar=lambda: tabbar or _Widget(width_value=120, size_hint_width=0),
        cached_source_tabbar_width=lambda: cached_width,
        set_cached_source_tabbar_width=updates.append,
    )


def _output_item(*, set_index: int) -> OutputCanvasImageItem:
    """Return a typed output item for navigation policy tests."""

    return OutputCanvasImageItem(
        uuid4(),
        ImageMeta("Workflow", "Cube", set_index - 1, "", "E:/outputs/image.png"),
        set_index,
    )


def _source(
    source_key: str,
    *,
    set_indexes: tuple[int, ...],
) -> OutputCanvasSourceGroup:
    """Return a source group with deterministic image items."""

    return OutputCanvasSourceGroup(
        source_key=source_key,
        label=source_key,
        images_by_set={index: _output_item(set_index=index) for index in set_indexes},
    )


def _scene(
    scene_key: str,
    *,
    sources: tuple[OutputCanvasSourceGroup, ...],
    representative_source_key: str | None = None,
) -> OutputCanvasSceneGroup:
    """Return a scene group with deterministic navigation metadata."""

    return OutputCanvasSceneGroup(
        scene_run_id=f"{scene_key}-run",
        scene_key=scene_key,
        title=scene_key,
        order=0,
        sources=sources,
        representative_source_key=representative_source_key,
    )
