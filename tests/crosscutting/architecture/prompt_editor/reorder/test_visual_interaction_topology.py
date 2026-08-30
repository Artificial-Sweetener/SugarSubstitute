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

"""Keep reorder visual and interaction topology below Qt adapters."""

from __future__ import annotations

from ..inventory import (
    prompt_editor_architecture_inventory,
)


def test_reorder_visual_interaction_topology_flows_outward() -> None:
    """Keep visual, animation, pointer, and viewport topology focused."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    visual_geometry = f"{prefix}overlays.reorder_visual_geometry"
    visual_style = f"{prefix}overlays.reorder_visual_style"
    interaction_visual = f"{prefix}overlays.reorder_interaction_visual"
    render_state = f"{prefix}overlays.reorder_render_state"
    animation_paint_policy = f"{prefix}overlays.reorder_animation_paint_policy"
    animation_plan = f"{prefix}projection.reorder_animation"
    animation_state = f"{prefix}projection.reorder_state"
    animation_presenter = f"{prefix}overlays.reorder_animation_presenter"
    held_chip_presenter = f"{prefix}overlays.reorder_held_chip_presenter"
    animation_visual_owner = f"{prefix}overlays.reorder_animation_visual_owner"
    animation_presentation = f"{prefix}overlays.reorder_animation_presentation"
    displacement_intent = f"{prefix}overlays.reorder_displacement_intent"
    displacement_session = f"{prefix}overlays.reorder_displacement_session"
    pointer_regions = f"{prefix}overlays.reorder_pointer_regions"
    pointer_move_owner = f"{prefix}overlays.reorder_pointer_move_owner"
    pointer_drag_start_owner = f"{prefix}overlays.reorder_pointer_drag_start_owner"
    pointer_drag_completion_owner = (
        f"{prefix}overlays.reorder_pointer_drag_completion_owner"
    )
    pointer_region_visual = f"{prefix}overlays.reorder_pointer_region_visual_owner"
    pointer_target_resolution = f"{prefix}overlays.reorder_pointer_target_resolution"
    pointer_target_transition = f"{prefix}overlays.reorder_pointer_target_transition"
    autoscroll = f"{prefix}overlays.reorder_autoscroll"
    chip_visuals = f"{prefix}overlays.chip_visuals"
    drag_proxy_visual_owner = f"{prefix}overlays.reorder_drag_proxy_visual_owner"
    held_drag_context = f"{prefix}overlays.reorder_held_drag_context"
    performance_counters = f"{prefix}overlays.reorder_performance_counters"
    event_ports = f"{prefix}overlays.reorder_event_ports"
    landing_session = f"{prefix}overlays.reorder_landing_session"
    landing_paint_owner = f"{prefix}overlays.reorder_landing_paint"
    landing_visual_owner = landing_paint_owner
    reorder_telemetry = f"{prefix}overlays.reorder_telemetry"
    interaction_metrics = f"{prefix}interactions.reorder_interaction_metrics"
    interaction_diagnostics = f"{prefix}overlays.reorder_interaction_diagnostics"
    drop_commit_diagnostics = f"{prefix}overlays.reorder_drop_commit_diagnostics"
    commit_snapshot = f"{prefix}overlays.reorder_commit_snapshot"
    interaction_intents = f"{prefix}overlays.reorder_interaction_intents"
    prepared_visual = f"{prefix}overlays.reorder_prepared_visual"
    render_publication_owner = f"{prefix}overlays.reorder_render_publication_owner"
    raster_publication = f"{prefix}overlays.reorder_raster_publication"
    live_visual_owner = f"{prefix}overlays.reorder_live_visual_owner"
    preview_layout_transition_owner = (
        f"{prefix}overlays.reorder_preview_layout_transition_owner"
    )
    visual_mode = f"{prefix}overlays.reorder_visual_mode"
    visual_session = f"{prefix}overlays.reorder_visual_session"
    visual_owner = f"{prefix}overlays.reorder_preview_visual_owner"
    viewport_geometry = f"{prefix}overlays.reorder_viewport_geometry"
    view = f"{prefix}overlays.reorder_view"
    overlay = f"{prefix}overlays.reorder_overlay"
    factory = f"{prefix}composition.reorder_overlay_factory"
    gesture_controller = f"{prefix}overlays.reorder_gesture_controller"
    interaction_geometry = f"{prefix}projection.reorder_interaction_geometry"
    interaction_state = f"{prefix}projection.reorder_interaction_geometry_state"
    forbidden_outer = {
        view,
        overlay,
        f"{prefix}projection.surface",
        f"{prefix}interactions.reorder_interaction",
        f"{prefix}widget",
        factory,
    }
    assert graph[visual_style].isdisjoint(
        {visual_geometry, interaction_visual, render_state, visual_owner, view}
        | forbidden_outer
    )
    assert graph[visual_geometry].isdisjoint({visual_owner} | forbidden_outer)
    assert visual_style in graph[interaction_visual]
    assert graph[interaction_visual].isdisjoint(
        {visual_geometry, render_state, visual_owner, view} | forbidden_outer
    )
    assert {visual_geometry, visual_style} <= graph[render_state]
    assert graph[render_state].isdisjoint(
        {interaction_visual, visual_owner, view} | forbidden_outer
    )
    assert graph[animation_paint_policy].isdisjoint(
        {
            visual_geometry,
            visual_style,
            interaction_visual,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {animation_presenter, held_chip_presenter} <= graph[animation_visual_owner]
    assert graph[animation_presenter].isdisjoint(
        {held_chip_presenter, animation_visual_owner, render_state, view}
        | forbidden_outer
    )
    assert graph[held_chip_presenter].isdisjoint(
        {animation_presenter, animation_visual_owner, render_state, view}
        | forbidden_outer
    )
    assert graph[animation_visual_owner].isdisjoint(
        {render_state, prepared_visual, visual_owner, view} | forbidden_outer
    )
    assert {
        animation_plan,
        animation_state,
        animation_visual_owner,
        chip_visuals,
        displacement_intent,
        displacement_session,
        pointer_regions,
    } <= graph[animation_presentation]
    assert event_ports in graph[pointer_regions]
    assert {
        chip_visuals,
        gesture_controller,
        interaction_diagnostics,
        interaction_metrics,
        interaction_visual,
        pointer_regions,
        visual_mode,
        visual_style,
    } <= graph[pointer_region_visual]
    assert graph[pointer_region_visual].isdisjoint(
        {
            animation_presentation,
            drag_proxy_visual_owner,
            landing_visual_owner,
            live_visual_owner,
            prepared_visual,
            raster_publication,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {
        gesture_controller,
        interaction_diagnostics,
        interaction_metrics,
        interaction_state,
        reorder_telemetry,
        f"{prefix}projection.reorder_pointer_hit_testing",
    } <= graph[pointer_target_resolution]
    assert graph[pointer_target_resolution].isdisjoint(forbidden_outer)
    assert pointer_target_resolution in graph[overlay]
    assert {
        animation_presentation,
        displacement_intent,
        drag_proxy_visual_owner,
        gesture_controller,
        interaction_diagnostics,
        interaction_metrics,
        landing_session,
        live_visual_owner,
        pointer_regions,
        pointer_target_resolution,
        visual_owner,
        reorder_telemetry,
        viewport_geometry,
        visual_mode,
        interaction_geometry,
        f"{prefix}projection.observability",
    } <= graph[pointer_target_transition]
    assert graph[pointer_target_transition].isdisjoint(
        {
            landing_visual_owner,
            prepared_visual,
            raster_publication,
            render_state,
            view,
        }
        | forbidden_outer
    )
    assert pointer_target_transition in graph[overlay]
    assert graph[pointer_move_owner] == {
        autoscroll,
        drag_proxy_visual_owner,
        gesture_controller,
        interaction_diagnostics,
        interaction_geometry,
        interaction_intents,
        interaction_metrics,
        pointer_target_transition,
        reorder_telemetry,
        f"{prefix}projection.observability",
    }
    assert graph[pointer_move_owner].isdisjoint(
        {
            animation_presentation,
            landing_visual_owner,
            live_visual_owner,
            pointer_regions,
            prepared_visual,
            raster_publication,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert pointer_move_owner in graph[overlay]
    assert graph[pointer_drag_start_owner] == {
        animation_presentation,
        autoscroll,
        drag_proxy_visual_owner,
        drop_commit_diagnostics,
        gesture_controller,
        held_drag_context,
        interaction_diagnostics,
        interaction_geometry,
        interaction_intents,
        interaction_metrics,
        landing_visual_owner,
        live_visual_owner,
        performance_counters,
        pointer_region_visual,
        pointer_target_transition,
        preview_layout_transition_owner,
        render_publication_owner,
        visual_mode,
        visual_session,
        f"{prefix}overlays.reorder_live_placement",
        f"{prefix}projection.observability",
    }
    assert graph[pointer_drag_start_owner].isdisjoint(
        {pointer_drag_completion_owner, commit_snapshot} | forbidden_outer
    )
    assert graph[commit_snapshot] == {
        "substitute.application.prompt_editor.reorder.session",
        interaction_state,
    }
    assert graph[commit_snapshot].isdisjoint(
        {pointer_drag_start_owner, pointer_drag_completion_owner} | forbidden_outer
    )
