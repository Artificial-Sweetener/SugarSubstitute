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

"""Verify Output navigation feature composition helpers."""

from __future__ import annotations

from typing import cast

from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareState,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.presentation.canvas.output.composition.navigation import (
    OutputCanvasPickerHost,
    output_canvas_picker_controller_for,
    output_navigation_controller_for_host,
    output_picker_controller_for_host,
    output_source_tab_selection_for_host,
    output_source_tabs_controller_for_host,
)
from substitute.presentation.canvas.shared.canvas_nav_picker import CanvasNavPickerItem
from tests.support.output_canvas.composition_fakes import (
    _Host,
    _MeasuredSelector,
    _SourceTabbar,
    _compare_controller,
    _image_item,
    _install_source_filter,
)


def test_output_canvas_composition_builds_source_tabs_controller_for_host() -> None:
    """Source-tabs composition should wire Output route and cache adapters."""

    tabbar = _SourceTabbar(width=144)
    syncs: list[None] = []
    updates: list[None] = []
    installed: list[tuple[object, int]] = []
    up_item = _image_item()
    host = _Host(
        tabbar=tabbar,
        _output_projection=OutputCanvasProjection(
            sources=(
                OutputCanvasSourceGroup("txt", "Text", {1: _image_item()}),
                OutputCanvasSourceGroup("up", "Upscale", {1: up_item}),
            ),
            active_source_key="txt",
            active_set_index=1,
            active_uuid=None,
            set_count=1,
        ),
    )
    select_source = output_source_tab_selection_for_host(
        host,
        update_tabbar_container=lambda: updates.append(None),
    )
    controller = output_source_tabs_controller_for_host(
        host,
        on_tab_changed=select_source,
        measure_preferred_width=lambda: tabbar.sizeHint().width(),
        sync_source_selector=lambda: syncs.append(None),
        install_tooltip_filter=lambda tab_item, _parent, delay: _install_source_filter(
            installed,
            tab_item,
            delay,
        ),
    )

    controller.rebuild_source_tabs(active_source_key="up")
    select_source("up")

    assert tabbar.added == [("txt", "Text"), ("up", "Upscale")]
    assert host._source_tab_cache_signature == (("txt", "Text"), ("up", "Upscale"))
    assert host._source_tabbar_preferred_width == 144
    assert host.active_source_key == "up"
    assert host.activeOutputChanged.calls == [(str(up_item.image_id),)]
    assert syncs == [None]
    assert updates == [None]
    assert installed


def test_output_canvas_composition_builds_navigation_controller_for_host() -> None:
    """Navigation-controller composition should wire host width and tabbar cache."""

    tabbar = _SourceTabbar(width=188)
    host = _Host(
        tabbar=tabbar,
        width_value=360,
    )
    controller = output_navigation_controller_for_host(host)

    assert controller.available_tabbar_container_width() == 336
    assert controller.preferred_tabbar_width() == 188
    assert host._source_tabbar_preferred_width == 188
    assert controller.tabbar() is tabbar


def test_output_canvas_picker_composition_wires_normal_source_picker() -> None:
    """Picker composition should wire normal source picker host collaborators."""

    host = _Host()
    text_item = _image_item()
    controller = output_canvas_picker_controller_for(
        cast(OutputCanvasPickerHost, host),
        visible_compare_state=lambda: OutputCompareState(enabled=False),
        visible_source_groups_by_key=lambda: {
            "txt": OutputCanvasSourceGroup("txt", "Text", {1: text_item}),
            "up": OutputCanvasSourceGroup("up", "Upscale", {}),
        },
        scene_groups_by_key=dict,
        scene_picker_row_width=lambda _items: 91,
        source_picker_row_width=lambda _items: 123,
        compare_controller=lambda: _compare_controller(),
        update_tabbar_container=lambda: None,
    )

    controller.show_source_picker()

    assert len(host._source_picker.calls) == 1
    anchor, items, active_key, row_width, selected_callback = host._source_picker.calls[
        0
    ]
    selected_callback("txt")

    assert anchor == "source-button"
    assert items == (
        CanvasNavPickerItem("txt", "Text"),
        CanvasNavPickerItem("up", "Upscale"),
    )
    assert active_key == "txt"
    assert row_width == 123
    assert host.active_source_key == "txt"
    assert host.active_set_index == 1
    assert host.last_real_set_index == 1
    assert host.activeOutputChanged.calls == [(str(text_item.image_id),)]


def test_output_picker_controller_for_host_wires_route_metrics() -> None:
    """Host picker composition should own selector row-width adapters."""

    text_item = _image_item()
    upscale_item = _image_item()
    text_source = OutputCanvasSourceGroup("txt", "Text", {1: text_item})
    upscale_source = OutputCanvasSourceGroup(
        "up",
        "Upscale XL",
        {1: upscale_item},
    )
    host = _Host(
        _output_projection=OutputCanvasProjection(
            sources=(text_source, upscale_source),
            active_source_key="txt",
            active_set_index=1,
            active_uuid=text_item.image_id,
            set_count=1,
            scene_groups=(
                OutputCanvasSceneGroup(
                    scene_run_id="run-portrait",
                    scene_key="portrait",
                    title="Portrait",
                    order=1,
                    sources=(text_source, upscale_source),
                    primary_image_id=text_item.image_id,
                ),
            ),
            active_scene_key="portrait",
            active_scene_overview=False,
            scene_count=2,
        ),
        active_source_key="txt",
        active_scene_key="portrait",
        scene_count=2,
        set_count=1,
        scene_selector_button=_MeasuredSelector(),
        source_selector_button=_MeasuredSelector(),
    )
    controller = output_picker_controller_for_host(
        cast(OutputCanvasPickerHost, host),
        visible_compare_state=lambda: OutputCompareState(enabled=False),
        compare_controller=lambda: _compare_controller(),
        update_tabbar_container=lambda: None,
        scene_selector_min_width=58,
        scene_selector_max_width=260,
        scene_selector_horizontal_padding=28,
        source_selector_min_width=58,
        source_selector_max_width=260,
        source_selector_horizontal_padding=28,
    )

    controller.show_scene_picker()
    controller.show_source_picker()

    assert host._scene_picker.calls[0][3] == 84
    assert host._source_picker.calls[0][3] == 98


def test_output_canvas_picker_composition_wires_set_picker_to_navigation() -> None:
    """Set picker composition should route selections through navigation ownership."""

    host = _Host()
    source = OutputCanvasSourceGroup(
        "txt",
        "Text",
        {2: _image_item(set_index=2)},
    )
    controller = output_canvas_picker_controller_for(
        cast(OutputCanvasPickerHost, host),
        visible_compare_state=lambda: OutputCompareState(enabled=False),
        visible_source_groups_by_key=lambda: {"txt": source},
        scene_groups_by_key=dict,
        scene_picker_row_width=lambda _items: 91,
        source_picker_row_width=lambda _items: 123,
        compare_controller=lambda: _compare_controller(),
        update_tabbar_container=lambda: None,
    )

    controller.show_set_picker()
    selected_callback = host._set_picker.calls[0][4]
    selected_callback(2)

    assert host._set_picker.calls[0][:4] == ("set-button", 2, 1, False)
    assert host.active_source_key == "txt"
    assert host.active_set_index == 2
    assert host.last_real_set_index == 2
    assert host.activeOutputChanged.calls == [(str(source.images_by_set[2].image_id),)]
    assert host.activeOutputGridChanged.calls == []


def test_output_canvas_picker_composition_wires_scene_picker_to_navigation() -> None:
    """Scene picker composition should route selections through navigation ownership."""

    host = _Host(scene_count=2)
    controller = output_canvas_picker_controller_for(
        cast(OutputCanvasPickerHost, host),
        visible_compare_state=lambda: OutputCompareState(enabled=False),
        visible_source_groups_by_key=dict,
        scene_groups_by_key=lambda: {
            "portrait": OutputCanvasSceneGroup(
                scene_run_id="run-portrait",
                scene_key="portrait",
                title="Portrait",
                order=1,
                sources=(
                    OutputCanvasSourceGroup(
                        "txt",
                        "Text",
                        {1: _image_item(), 2: _image_item(set_index=2)},
                    ),
                ),
            )
        },
        scene_picker_row_width=lambda _items: 91,
        source_picker_row_width=lambda _items: 123,
        compare_controller=lambda: _compare_controller(),
        update_tabbar_container=lambda: None,
    )

    controller.show_scene_picker()
    selected_callback = host._scene_picker.calls[0][4]
    selected_callback("portrait")

    assert host.active_scene_key == "portrait"
    assert host.active_scene_overview is False
    assert host.active_source_key == "txt"
    assert host.active_set_index == 0
    assert host.activeOutputSceneChanged.calls == [
        (
            OutputSceneNavigationSelection(
                scene_key="portrait",
                overview=False,
                source_key="txt",
                set_index=0,
                image_id=None,
            ),
        )
    ]
    assert host.activeOutputGridChanged.calls == []
