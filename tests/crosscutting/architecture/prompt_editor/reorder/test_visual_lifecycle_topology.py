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
    PROMPT_PRESENTATION_ROOT,
    prompt_editor_architecture_inventory,
)


def test_reorder_visual_lifecycle_topology_flows_outward() -> None:
    """Keep visual mode, preview frame, drag proxy, and lifecycle topology focused."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    render_state = f"{prefix}overlays.reorder_render_state"
    animation_paint_policy = f"{prefix}overlays.reorder_animation_paint_policy"
    animation_state = f"{prefix}projection.reorder_state"
    animation_presentation = f"{prefix}overlays.reorder_animation_presentation"
    pointer_regions = f"{prefix}overlays.reorder_pointer_regions"
    pointer_drag_start_owner = f"{prefix}overlays.reorder_pointer_drag_start_owner"
    pointer_drag_completion_owner = (
        f"{prefix}overlays.reorder_pointer_drag_completion_owner"
    )
    pointer_region_visual = f"{prefix}overlays.reorder_pointer_region_visual_owner"
    pointer_target_transition = f"{prefix}overlays.reorder_pointer_target_transition"
    autoscroll = f"{prefix}overlays.reorder_autoscroll"
    chip_visuals = f"{prefix}overlays.chip_visuals"
    drag_proxy_state = f"{prefix}reorder_drag_proxy_state"
    drag_proxy_widget = f"{prefix}overlays.reorder_drag_proxy"
    drag_proxy_visual_owner = f"{prefix}overlays.reorder_drag_proxy_visual_owner"
    held_drag_context = f"{prefix}overlays.reorder_held_drag_context"
    performance_counters = f"{prefix}overlays.reorder_performance_counters"
    event_ports = f"{prefix}overlays.reorder_event_ports"
    landing_models = f"{prefix}overlays.reorder_landing_models"
    landing_request_owner = f"{prefix}overlays.reorder_landing_request_owner"
    landing_resolution_owner = f"{prefix}overlays.reorder_landing_resolution"
    landing_paint_owner = f"{prefix}overlays.reorder_landing_paint"
    landing_visual_owner = landing_paint_owner
    interaction_metrics = f"{prefix}interactions.reorder_interaction_metrics"
    interaction_diagnostics = f"{prefix}overlays.reorder_interaction_diagnostics"
    drop_actual_observation = f"{prefix}overlays.reorder_drop_actual_observation"
    drop_commit_diagnostics = f"{prefix}overlays.reorder_drop_commit_diagnostics"
    commit_snapshot = f"{prefix}overlays.reorder_commit_snapshot"
    interaction_intents = f"{prefix}overlays.reorder_interaction_intents"
    prepared_visual = f"{prefix}overlays.reorder_prepared_visual"
    render_publication_owner = f"{prefix}overlays.reorder_render_publication_owner"
    raster_publication = f"{prefix}overlays.reorder_raster_publication"
    live_visual_owner = f"{prefix}overlays.reorder_live_visual_owner"
    preview_paint_snapshot_owner = (
        f"{prefix}overlays.reorder_preview_paint_snapshot_owner"
    )
    preview_geometry_refresh_owner = (
        f"{prefix}overlays.reorder_preview_geometry_refresh_owner"
    )
    preview_layout_transition_owner = (
        f"{prefix}overlays.reorder_preview_layout_transition_owner"
    )
    preview_frame_transition = f"{prefix}overlays.reorder_preview_frame_transition"
    refresh_identity = f"{prefix}overlays.reorder_refresh_identity"
    visual_mode = f"{prefix}overlays.reorder_visual_mode"
    visual_mode_policy = f"{prefix}overlays.reorder_visual_mode_policy"
    visual_session = f"{prefix}overlays.reorder_visual_session"
    visual_owner = f"{prefix}overlays.reorder_preview_visual_owner"
    viewport_geometry = f"{prefix}overlays.reorder_viewport_geometry"
    viewport_frame_refresh = f"{prefix}overlays.reorder_viewport_frame_refresh"
    view = f"{prefix}overlays.reorder_view"
    overlay = f"{prefix}overlays.reorder_overlay"
    factory = f"{prefix}composition.reorder_overlay_factory"
    gesture_controller = f"{prefix}overlays.reorder_gesture_controller"
    widget_mapping = f"{prefix}geometry.widget_mapping"
    interaction_geometry = f"{prefix}projection.reorder_interaction_geometry"
    interaction_geometry_identity = (
        f"{prefix}projection.reorder_interaction_geometry_identity"
    )
    interaction_state = f"{prefix}projection.reorder_interaction_geometry_state"
    visual_snapshot = f"{prefix}projection.reorder_visual_snapshot"
    forbidden_outer = {
        view,
        overlay,
        f"{prefix}projection.surface",
        f"{prefix}interactions.reorder_interaction",
        f"{prefix}widget",
        factory,
    }
    assert graph[pointer_drag_completion_owner] == {
        animation_presentation,
        autoscroll,
        commit_snapshot,
        drag_proxy_visual_owner,
        drop_actual_observation,
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
        pointer_regions,
        preview_layout_transition_owner,
        render_publication_owner,
        visual_mode,
        visual_owner,
        visual_session,
        "substitute.application.prompt_editor.reorder.intents",
        f"{prefix}projection.observability",
    }
    assert graph[pointer_drag_completion_owner].isdisjoint(
        {pointer_drag_start_owner} | forbidden_outer
    )
    assert {
        commit_snapshot,
        pointer_drag_completion_owner,
        pointer_drag_start_owner,
    } <= graph[overlay]
    assert {
        widget_mapping,
        f"{prefix}projection.reorder_state",
    } <= graph[viewport_geometry]
    assert graph[viewport_geometry].isdisjoint(
        {
            interaction_geometry,
            pointer_target_transition,
            prepared_visual,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert viewport_geometry in graph[overlay]
    assert graph[viewport_frame_refresh] == {
        animation_presentation,
        drag_proxy_visual_owner,
        gesture_controller,
        interaction_diagnostics,
        interaction_geometry,
        interaction_metrics,
        live_visual_owner,
        pointer_region_visual,
        preview_geometry_refresh_owner,
        preview_layout_transition_owner,
        refresh_identity,
        render_publication_owner,
        viewport_geometry,
        visual_owner,
        visual_session,
        f"{prefix}projection.observability",
        f"{prefix}projection.reorder_state",
    }
    assert graph[viewport_frame_refresh].isdisjoint(
        {preview_frame_transition, view} | forbidden_outer
    )
    assert {
        interaction_geometry_identity,
        interaction_state,
        animation_state,
    } <= graph[refresh_identity]
    assert graph[refresh_identity].isdisjoint(
        {
            animation_presentation,
            autoscroll,
            drag_proxy_visual_owner,
            interaction_geometry,
            live_visual_owner,
            pointer_region_visual,
            pointer_target_transition,
            prepared_visual,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert refresh_identity in graph[overlay]
    assert graph[visual_mode] == {
        "substitute.application.prompt_editor.reorder.views",
        gesture_controller,
        interaction_state,
        visual_mode_policy,
    }
    assert graph[visual_mode].isdisjoint(forbidden_outer)
    assert graph[visual_session] == {
        "substitute.application.prompt_editor.document.views",
        f"{prefix}core.state.revisions",
    }
    assert graph[visual_session].isdisjoint(forbidden_outer)
    assert graph[preview_paint_snapshot_owner] == {
        chip_visuals,
        f"{prefix}overlays.reorder_visual_cache",
        f"{prefix}projection.reorder_chip_geometry",
        interaction_state,
        visual_snapshot,
    }
    assert graph[preview_paint_snapshot_owner].isdisjoint(
        {
            prepared_visual,
            raster_publication,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert graph[preview_geometry_refresh_owner] == {
        gesture_controller,
        interaction_diagnostics,
        interaction_geometry,
        interaction_metrics,
        landing_request_owner,
        landing_resolution_owner,
        preview_paint_snapshot_owner,
        visual_owner,
        viewport_geometry,
        f"{prefix}projection.observability",
    }
    assert graph[preview_geometry_refresh_owner].isdisjoint(
        {
            animation_presentation,
            drag_proxy_visual_owner,
            prepared_visual,
            raster_publication,
            render_state,
            view,
        }
        | forbidden_outer
    )
    assert graph[preview_layout_transition_owner] == {
        drag_proxy_visual_owner,
        gesture_controller,
        interaction_geometry,
        interaction_metrics,
        viewport_geometry,
    }
    assert graph[preview_layout_transition_owner].isdisjoint(
        {
            animation_presentation,
            landing_visual_owner,
            live_visual_owner,
            pointer_target_transition,
            prepared_visual,
            raster_publication,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert graph[preview_frame_transition] == {
        "substitute.application.prompt_editor.reorder.views",
        animation_paint_policy,
        animation_presentation,
        drop_actual_observation,
        drop_commit_diagnostics,
        gesture_controller,
        interaction_diagnostics,
        interaction_geometry,
        interaction_metrics,
        live_visual_owner,
        pointer_region_visual,
        pointer_regions,
        preview_geometry_refresh_owner,
        preview_paint_snapshot_owner,
        refresh_identity,
        render_publication_owner,
        viewport_geometry,
        visual_mode,
        visual_owner,
        visual_session,
        f"{prefix}projection.observability",
    }
    assert graph[preview_frame_transition].isdisjoint(
        {viewport_frame_refresh, view} | forbidden_outer
    )
    assert {
        preview_frame_transition,
        viewport_frame_refresh,
    } <= graph[overlay]
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_frame_transition_owner.py"
    ).exists()
    assert graph[animation_presentation].isdisjoint(
        {
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {
        drag_proxy_state,
        drag_proxy_widget,
        event_ports,
        gesture_controller,
        widget_mapping,
    } <= graph[drag_proxy_visual_owner]
    assert graph[drag_proxy_state].isdisjoint(
        {drag_proxy_visual_owner, visual_owner, view} | forbidden_outer
    )
    assert graph[drag_proxy_widget].isdisjoint(
        {drag_proxy_visual_owner, visual_owner, view} | forbidden_outer
    )
    assert graph[gesture_controller].isdisjoint(
        {drag_proxy_visual_owner, visual_owner, view} | forbidden_outer
    )
    assert graph[drag_proxy_visual_owner].isdisjoint(
        {
            landing_visual_owner,
            prepared_visual,
            raster_publication,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {
        chip_visuals,
        gesture_controller,
        landing_models,
        pointer_regions,
        f"{prefix}projection.reorder_chip_geometry",
        interaction_state,
    } <= graph[held_drag_context]
    assert graph[held_drag_context].isdisjoint(
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
    assert held_drag_context in graph[overlay]
    assert {
        animation_presentation,
        drag_proxy_visual_owner,
        interaction_metrics,
        landing_visual_owner,
        raster_publication,
    } <= graph[performance_counters]
    assert graph[performance_counters].isdisjoint(forbidden_outer)
    assert performance_counters in graph[overlay]
