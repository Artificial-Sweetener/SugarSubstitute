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

"""Verify Output navigation host mutation, synchronization, and dispatch."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.canvas.output.output_canvas_navigation_controller import (
    activate_output_grid_for_source,
    activate_output_item,
    activate_output_scene,
    activate_output_scene_overview,
    sync_output_scene_selector_button,
    sync_output_set_selector_button,
    sync_output_source_selector_button,
)


from tests.presentation.canvas.output.navigation.controller_support import (
    SignalSpy,
    SelectorButtonSpy,
    build_output_item,
    build_source,
    build_scene,
)


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
            "portrait": build_scene(
                "portrait",
                sources=(
                    build_source("wf:text", set_indexes=(1,)),
                    build_source("wf:upscale", set_indexes=(1, 2)),
                ),
                representative_source_key="wf:upscale",
            )
        },
        update_tabbar_container=lambda: calls.append(("tabbar", None)),
    )

    assert activated == OutputSceneNavigationSelection(
        scene_key="portrait",
        overview=False,
        source_key="wf:upscale",
        set_index=0,
        image_id=None,
    )
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

    assert activated is None
    assert host.active_scene_key == "old"


def test_sync_output_scene_selector_button_applies_host_scene_label() -> None:
    """Scene selector adapter should render the active scene through host state."""

    scene = build_scene("portrait", sources=())
    button = SelectorButtonSpy()
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

    source = build_source("wf:upscale", set_indexes=(1, 2))
    button = SelectorButtonSpy()
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

    source = build_source("wf:upscale", set_indexes=(1,))
    other_source = build_source("wf:text", set_indexes=(1,))
    button = SelectorButtonSpy()
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


def test_activate_output_grid_for_source_applies_host_state_and_signal() -> None:
    """Source-grid adapter should own host mutation around the pure plan."""

    calls: list[tuple[str, object]] = []
    signal = SignalSpy()
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
        source_groups_by_key={
            "wf:upscale": build_source("wf:upscale", set_indexes=(1, 2))
        },
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


def test_activate_output_grid_for_source_accepts_single_item_source() -> None:
    """Source-grid adapter should preserve set zero for a one-tile source."""

    host = SimpleNamespace(active_source_key="wf:text", active_set_index=1)

    activated = activate_output_grid_for_source(
        host,
        "wf:text",
        source_groups_by_key={"wf:text": build_source("wf:text", set_indexes=(1,))},
        update_tabbar_container=lambda: None,
    )

    assert activated is True
    assert host.active_source_key == "wf:text"
    assert host.active_set_index == 0


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


def test_activate_output_item_applies_host_state_tabs_tooltips_and_signal() -> None:
    """Concrete output adapter should own host mutation around the pure plan."""

    item = build_output_item(set_index=3)
    calls: list[tuple[str, object]] = []
    signal = SignalSpy()
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

    item = build_output_item(set_index=2)
    signal = SignalSpy()
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
