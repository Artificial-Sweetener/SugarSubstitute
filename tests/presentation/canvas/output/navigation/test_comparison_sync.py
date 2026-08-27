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

"""Verify atomic synchronization of comparison navigation controls."""

from __future__ import annotations


from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    sync_comparison_navigation_buttons,
)


from tests.presentation.canvas.output.navigation.controller_support import (
    ContainerSpy,
)


def test_sync_comparison_navigation_buttons_hides_container_when_not_visible() -> None:
    """Comparison navigation sync should hide the container without a comparison."""

    container = ContainerSpy()
    calls: list[tuple[str, object, object]] = []

    refreshed = sync_comparison_navigation_buttons(
        comparison_nav_container=container,
        enabled=True,
        base_selection=object(),
        comparison_selection=None,
        base_scene_button=object(),
        base_set_button=object(),
        base_source_button=object(),
        comparison_scene_button=object(),
        comparison_set_button=object(),
        comparison_source_button=object(),
        sync_scene_button=lambda _side, button, selection: calls.append(
            ("scene", button, selection),
        ),
        sync_set_button=lambda _side, button, selection: calls.append(
            ("set", button, selection),
        ),
        sync_source_button=lambda _side, button, selection: calls.append(
            ("source", button, selection),
        ),
    )

    assert refreshed is False
    assert container.hidden is True
    assert calls == []


def test_sync_comparison_navigation_buttons_refreshes_each_selector() -> None:
    """Comparison navigation sync should refresh scene, set, and source selectors."""

    container = ContainerSpy()
    base_selection = object()
    comparison_selection = object()
    base_scene_button = object()
    base_set_button = object()
    base_source_button = object()
    comparison_scene_button = object()
    comparison_set_button = object()
    comparison_source_button = object()
    calls: list[tuple[str, str, object, object]] = []

    refreshed = sync_comparison_navigation_buttons(
        comparison_nav_container=container,
        enabled=True,
        base_selection=base_selection,
        comparison_selection=comparison_selection,
        base_scene_button=base_scene_button,
        base_set_button=base_set_button,
        base_source_button=base_source_button,
        comparison_scene_button=comparison_scene_button,
        comparison_set_button=comparison_set_button,
        comparison_source_button=comparison_source_button,
        sync_scene_button=lambda side, button, selected: calls.append(
            ("scene", side, button, selected),
        ),
        sync_set_button=lambda side, button, selected: calls.append(
            ("set", side, button, selected),
        ),
        sync_source_button=lambda side, button, selected: calls.append(
            ("source", side, button, selected),
        ),
    )

    assert refreshed is True
    assert container.hidden is False
    assert calls == [
        ("scene", "base", base_scene_button, base_selection),
        ("set", "base", base_set_button, base_selection),
        ("source", "base", base_source_button, base_selection),
        (
            "scene",
            "comparison",
            comparison_scene_button,
            comparison_selection,
        ),
        ("set", "comparison", comparison_set_button, comparison_selection),
        (
            "source",
            "comparison",
            comparison_source_button,
            comparison_selection,
        ),
    ]
