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

"""Verify the authoritative Output navigation visibility policy."""

from __future__ import annotations

from substitute.presentation.canvas.output.output_canvas_navigation_visibility import (
    OutputCanvasNavigationVisibilityPolicy,
)


def test_normal_visibility_keeps_scene_and_batch_cardinality_independent() -> None:
    """Scene and Batch controls should follow only their applicable counts."""

    batchless_scenes = OutputCanvasNavigationVisibilityPolicy.normal(
        scene_count=3,
        source_count=1,
        set_count=1,
        active_scene_overview=True,
    )
    batched_single_scene = OutputCanvasNavigationVisibilityPolicy.normal(
        scene_count=1,
        source_count=1,
        set_count=3,
        active_scene_overview=False,
    )

    assert batchless_scenes.show_scene_selector is True
    assert batchless_scenes.show_set_selector is False
    assert batchless_scenes.has_visible_control is True
    assert batched_single_scene.show_scene_selector is False
    assert batched_single_scene.show_set_selector is True


def test_normal_visibility_hides_contextual_controls_during_scene_overview() -> None:
    """Scene overview should hide source and batch controls without hiding Scene."""

    visibility = OutputCanvasNavigationVisibilityPolicy.normal(
        scene_count=2,
        source_count=4,
        set_count=3,
        active_scene_overview=True,
    )

    assert visibility.show_scene_selector is True
    assert visibility.show_source_navigation is False
    assert visibility.show_set_selector is False


def test_source_display_expands_when_width_fits() -> None:
    """Source navigation should render tabs when expanded tabs fit."""

    display = OutputCanvasNavigationVisibilityPolicy.source_display(
        show_source_navigation=True,
        has_source_selector=True,
        expanded_width=120,
        available_width=160,
    )

    assert display.source_tabs_collapsed is False
    assert display.show_source_tabs is True
    assert display.show_source_selector is False


def test_source_display_collapses_when_width_overflows() -> None:
    """Source navigation should use the compact selector when tabs overflow."""

    display = OutputCanvasNavigationVisibilityPolicy.source_display(
        show_source_navigation=True,
        has_source_selector=True,
        expanded_width=200,
        available_width=160,
    )

    assert display.source_tabs_collapsed is True
    assert display.show_source_tabs is False
    assert display.show_source_selector is True


def test_source_display_requires_selector_to_collapse() -> None:
    """Missing compact selector should keep visible source tabs expanded."""

    display = OutputCanvasNavigationVisibilityPolicy.source_display(
        show_source_navigation=True,
        has_source_selector=False,
        expanded_width=200,
        available_width=160,
    )

    assert display.source_tabs_collapsed is False
    assert display.show_source_tabs is True
    assert display.show_source_selector is False


def test_source_display_hides_both_modes_when_source_navigation_is_unavailable() -> (
    None
):
    """Unavailable source navigation should hide expanded and compact controls."""

    display = OutputCanvasNavigationVisibilityPolicy.source_display(
        show_source_navigation=False,
        has_source_selector=True,
        expanded_width=200,
        available_width=160,
    )

    assert display.source_tabs_collapsed is False
    assert display.show_source_tabs is False
    assert display.show_source_selector is False


def test_compare_visibility_uses_independent_scene_and_batch_counts() -> None:
    """Comparison hierarchy controls should follow independent cardinalities."""

    scene_only = OutputCanvasNavigationVisibilityPolicy.compare(
        scene_count=2,
        set_count=1,
    )
    batch_only = OutputCanvasNavigationVisibilityPolicy.compare(
        scene_count=1,
        set_count=3,
    )

    assert scene_only.source_tabs_collapsed is True
    assert scene_only.show_scene_selector is True
    assert scene_only.show_set_selector is False
    assert scene_only.show_source_selector is True
    assert batch_only.show_scene_selector is False
    assert batch_only.show_set_selector is True
