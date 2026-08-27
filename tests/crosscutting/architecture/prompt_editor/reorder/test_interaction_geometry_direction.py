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

"""Keep prompt reorder geometry owners focused and directional."""

from __future__ import annotations


from ..inventory import (
    PROMPT_PRESENTATION_ROOT,
    prompt_editor_architecture_inventory,
)


def test_reorder_interaction_geometry_has_directional_focused_owners() -> None:
    """Keep target values, queries, publication, and coordination one-way."""

    architecture = prompt_editor_architecture_inventory()
    module_paths = architecture.module_paths
    graph = architecture.graph
    projection = "substitute.presentation.editor.prompt_editor.projection."
    values = f"{projection}reorder_drop_targets"
    pointer = f"{projection}reorder_pointer_hit_testing"
    drop_builder = f"{projection}reorder_drop_geometry_builder"
    drop_publication = f"{projection}reorder_drop_geometry_publication"
    drag_preparation = f"{projection}reorder_drag_geometry_preparation"
    keyboard_geometry = f"{projection}reorder_keyboard_geometry"
    keyboard_navigation = f"{projection}reorder_keyboard_navigation"
    keyboard_transition = f"{projection}reorder_keyboard_projection_transition"
    state = f"{projection}reorder_interaction_geometry_state"
    identity = f"{projection}reorder_interaction_geometry_identity"
    preview_layout_policy = f"{projection}reorder_preview_layout_policy"
    preview_layout_state = f"{projection}reorder_preview_layout_state"
    preview_transition = f"{projection}reorder_preview_geometry_transition"
    geometry_owner = f"{projection}reorder_geometry_owner"
    owner = f"{projection}reorder_interaction_geometry"
    focused_modules = {
        values,
        pointer,
        drop_builder,
        drop_publication,
        drag_preparation,
        keyboard_geometry,
        keyboard_navigation,
        keyboard_transition,
        state,
        identity,
        preview_layout_policy,
        preview_layout_state,
        preview_transition,
        owner,
    }
    forbidden_outer = {
        f"{projection}surface",
        "substitute.presentation.editor.prompt_editor.widget",
        "substitute.presentation.editor.prompt_editor.overlays.reorder_overlay",
        "substitute.presentation.editor.prompt_editor.interactions.reorder_interaction",
    }

    assert graph[values].isdisjoint((focused_modules - {values}) | forbidden_outer)
    assert not (
        PROMPT_PRESENTATION_ROOT / "projection" / "reorder_partition_targets.py"
    ).exists()
    assert values in graph[drop_builder]
    assert graph[drop_builder].isdisjoint(
        {
            drop_publication,
            drag_preparation,
            pointer,
            keyboard_geometry,
            keyboard_navigation,
            keyboard_transition,
            state,
            identity,
            preview_layout_policy,
            preview_layout_state,
            preview_transition,
            owner,
        }
        | forbidden_outer
    )
    assert {values, drop_builder} <= graph[drop_publication]
    assert graph[drop_publication].isdisjoint(
        {
            drag_preparation,
            pointer,
            keyboard_geometry,
            keyboard_navigation,
            keyboard_transition,
            state,
            identity,
            preview_layout_policy,
            preview_layout_state,
            preview_transition,
            owner,
        }
        | forbidden_outer
    )
    assert values in graph[pointer]
    assert graph[pointer].isdisjoint(
        {
            drop_builder,
            drag_preparation,
            keyboard_geometry,
            keyboard_navigation,
            owner,
        }
        | forbidden_outer
    )
    assert values in graph[keyboard_geometry]
    assert graph[keyboard_geometry].isdisjoint(
        {
            pointer,
            drop_builder,
            drag_preparation,
            keyboard_navigation,
            keyboard_transition,
            state,
            identity,
            owner,
        }
        | forbidden_outer
    )
    assert {values, keyboard_geometry} <= graph[keyboard_navigation]
    assert graph[keyboard_navigation].isdisjoint(
        {
            pointer,
            drop_builder,
            drag_preparation,
            keyboard_transition,
            state,
            identity,
            owner,
        }
        | forbidden_outer
    )
    assert {keyboard_navigation, state} <= graph[keyboard_transition]
    assert graph[keyboard_transition].isdisjoint(
        {
            values,
            pointer,
            drop_builder,
            drop_publication,
            drag_preparation,
            keyboard_geometry,
            identity,
            preview_layout_policy,
            preview_layout_state,
            preview_transition,
            owner,
        }
        | forbidden_outer
    )
    assert state in graph[identity]
    assert {
        drop_publication,
        keyboard_navigation,
        state,
    } <= graph[drag_preparation]
    assert geometry_owner not in graph[drag_preparation]
    assert graph[drag_preparation].isdisjoint(
        {
            values,
            pointer,
            drop_builder,
            keyboard_geometry,
            keyboard_transition,
            identity,
            preview_layout_policy,
            preview_layout_state,
            preview_transition,
            owner,
        }
        | forbidden_outer
    )
    assert state in graph[preview_layout_policy]
    assert graph[preview_layout_policy].isdisjoint(
        {
            values,
            pointer,
            drop_builder,
            drop_publication,
            drag_preparation,
            keyboard_geometry,
            keyboard_navigation,
            keyboard_transition,
            identity,
            preview_layout_state,
            preview_transition,
            owner,
        }
        | forbidden_outer
    )
    assert {
        identity,
        keyboard_navigation,
        state,
        preview_layout_policy,
    } <= graph[preview_layout_state]
    assert graph[preview_layout_state].isdisjoint(
        {
            values,
            pointer,
            drop_builder,
            drop_publication,
            drag_preparation,
            keyboard_geometry,
            keyboard_transition,
            preview_transition,
            owner,
        }
        | forbidden_outer
    )
    assert {
        drop_publication,
        geometry_owner,
        state,
        identity,
        preview_layout_policy,
    } <= graph[preview_transition]
    assert graph[preview_transition].isdisjoint(
        {
            drag_preparation,
            pointer,
            keyboard_geometry,
            keyboard_navigation,
            owner,
        }
        | forbidden_outer
    )
    assert {
        drop_publication,
        drag_preparation,
        geometry_owner,
        keyboard_navigation,
        keyboard_transition,
        state,
        identity,
        preview_layout_state,
        preview_transition,
    } <= graph[owner]
    assert graph[owner].isdisjoint({pointer} | forbidden_outer)
    owner_source = module_paths[owner].read_text(encoding="utf-8")
    drag_preparation_source = module_paths[drag_preparation].read_text(encoding="utf-8")
    preview_layout_state_source = module_paths[preview_layout_state].read_text(
        encoding="utf-8"
    )
    assert "def build_live_chip_snapshot(" not in drag_preparation_source
    assert "class PromptReorderGeometryRefresh" not in owner_source
    assert "def drop_geometry_from_placements(" not in owner_source
    assert "def _layout_for_painted_preview(" not in owner_source
    assert "built_preview_layout =" not in owner_source
    assert '"preview_layout.build_drop_layout"' not in owner_source
    assert "def ensure_keyboard_context(" not in owner_source
    assert "def _keyboard_navigation_input(" not in owner_source
    assert "def _apply_keyboard_navigation_result(" not in owner_source
    assert "def _apply_logged_keyboard_navigation_result(" not in owner_source
    assert "live_placement_snapshot(" not in owner_source
    assert "def layout_for_painted_preview(" not in owner_source
    assert "def ordered_indices_for_layout(" not in owner_source
    transition_sources = drag_preparation_source + preview_layout_state_source
    assert "build_base_drag_reorder_state_from_state(" not in transition_sources
    assert "build_base_drag_layout_view_from_layout(" not in transition_sources
    assert "build_preview_drop_reorder_state_from_state(" not in transition_sources
    assert "build_preview_drop_layout_view_from_layout(" not in transition_sources
    assert "build_base_drag_state(" in drag_preparation_source
    assert "build_preview_drop_state(" in preview_layout_state_source
    assert '"start.live_placement_prime"' not in owner_source
