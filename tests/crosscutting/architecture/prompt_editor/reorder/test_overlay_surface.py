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

"""Keep prepared visuals, raster publication, and overlay telemetry focused."""

from __future__ import annotations

from ..inventory import (
    PROMPT_PRESENTATION_ROOT,
    prompt_editor_architecture_inventory,
)


def test_reorder_overlay_surface_publication_flows_outward_to_qt_adapters() -> None:
    """Keep prepared visuals, raster publication, and overlay telemetry focused."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    visual_geometry = f"{prefix}overlays.reorder_visual_geometry"
    visual_style = f"{prefix}overlays.reorder_visual_style"
    interaction_visual = f"{prefix}overlays.reorder_interaction_visual"
    render_state = f"{prefix}overlays.reorder_render_state"
    animation_paint_policy = f"{prefix}overlays.reorder_animation_paint_policy"
    animation_presentation = f"{prefix}overlays.reorder_animation_presentation"
    displacement_intent = f"{prefix}overlays.reorder_displacement_intent"
    pointer_move_owner = f"{prefix}overlays.reorder_pointer_move_owner"
    pointer_drag_start_owner = f"{prefix}overlays.reorder_pointer_drag_start_owner"
    pointer_drag_completion_owner = (
        f"{prefix}overlays.reorder_pointer_drag_completion_owner"
    )
    pointer_region_visual = f"{prefix}overlays.reorder_pointer_region_visual_owner"
    chip_visuals = f"{prefix}overlays.chip_visuals"
    drag_proxy_visual_owner = f"{prefix}overlays.reorder_drag_proxy_visual_owner"
    landing_models = f"{prefix}overlays.reorder_landing_models"
    landing_request_owner = f"{prefix}overlays.reorder_landing_request_owner"
    landing_resolution_owner = f"{prefix}overlays.reorder_landing_resolution"
    landing_paint_owner = f"{prefix}overlays.reorder_landing_paint"
    landing_visual_owner = landing_paint_owner
    reorder_telemetry = f"{prefix}overlays.reorder_telemetry"
    interaction_metrics = f"{prefix}interactions.reorder_interaction_metrics"
    interaction_diagnostics = f"{prefix}overlays.reorder_interaction_diagnostics"
    drop_actual_observation = f"{prefix}overlays.reorder_drop_actual_observation"
    drop_commit_diagnostics = f"{prefix}overlays.reorder_drop_commit_diagnostics"
    commit_snapshot = f"{prefix}overlays.reorder_commit_snapshot"
    interaction_intents = f"{prefix}overlays.reorder_interaction_intents"
    insertion_marker_owner = f"{prefix}overlays.reorder_insertion_marker_owner"
    keyboard_interaction = f"{prefix}overlays.reorder_keyboard_interaction"
    prepared_visual = f"{prefix}overlays.reorder_prepared_visual"
    render_publication_owner = f"{prefix}overlays.reorder_render_publication_owner"
    raster_cache = f"{prefix}overlays.reorder_raster_cache"
    raster_warm_scheduler = f"{prefix}overlays.reorder_raster_warm_scheduler"
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
    visual_mode = f"{prefix}overlays.reorder_visual_mode"
    visual_session = f"{prefix}overlays.reorder_visual_session"
    visual_owner = f"{prefix}overlays.reorder_preview_visual_owner"
    viewport_frame_refresh = f"{prefix}overlays.reorder_viewport_frame_refresh"
    view = f"{prefix}overlays.reorder_view"
    overlay = f"{prefix}overlays.reorder_overlay"
    factory = f"{prefix}composition.reorder_overlay_factory"
    gesture_controller = f"{prefix}overlays.reorder_gesture_controller"
    interaction_geometry = f"{prefix}projection.reorder_interaction_geometry"
    interaction_state = f"{prefix}projection.reorder_interaction_geometry_state"
    surface_chrome = f"{prefix}projection.reorder_surface_chrome"
    surface_visual_state = f"{prefix}projection.reorder_surface_visual_state"
    visual_snapshot = f"{prefix}projection.reorder_visual_snapshot"
    forbidden_outer = {
        view,
        overlay,
        f"{prefix}projection.surface",
        f"{prefix}interactions.reorder_interaction",
        f"{prefix}widget",
        factory,
    }

    assert {surface_chrome, visual_snapshot} <= graph[surface_visual_state]
    assert graph[surface_visual_state].isdisjoint(
        {
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert surface_visual_state in graph[f"{prefix}projection.surface"]
    assert {render_state, surface_visual_state} <= graph[prepared_visual]
    assert graph[prepared_visual].isdisjoint(
        {
            animation_paint_policy,
            interaction_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert graph[drop_actual_observation] == {
        chip_visuals,
        interaction_state,
        f"{prefix}projection.reorder_chip_geometry",
    }
    assert graph[drop_actual_observation].isdisjoint(forbidden_outer)
    assert graph[render_publication_owner] == {
        animation_presentation,
        insertion_marker_owner,
        interaction_diagnostics,
        interaction_geometry,
        interaction_metrics,
        landing_models,
        landing_request_owner,
        landing_visual_owner,
        live_visual_owner,
        prepared_visual,
        preview_paint_snapshot_owner,
        raster_cache,
        raster_publication,
        render_state,
        visual_mode,
        visual_owner,
        visual_style,
        gesture_controller,
        f"{prefix}overlays.chip_painter",
        f"{prefix}projection.reorder_chip_geometry",
        surface_visual_state,
    }
    assert graph[render_publication_owner].isdisjoint(forbidden_outer)
    assert {raster_cache, raster_warm_scheduler} <= graph[raster_publication]
    assert graph[raster_cache].isdisjoint(
        {
            raster_warm_scheduler,
            raster_publication,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert graph[raster_warm_scheduler].isdisjoint(
        {
            raster_publication,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert graph[raster_publication].isdisjoint(
        {
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {
        chip_visuals,
        interaction_diagnostics,
        interaction_state,
        interaction_metrics,
        visual_geometry,
        f"{prefix}projection.reorder_chip_geometry",
        f"{prefix}projection.reorder_state",
    } <= graph[live_visual_owner]
    assert graph[live_visual_owner].isdisjoint(
        {
            animation_presentation,
            drag_proxy_visual_owner,
            landing_visual_owner,
            prepared_visual,
            raster_publication,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {visual_geometry, interaction_state} <= graph[visual_owner]
    assert interaction_geometry not in graph[visual_owner]
    assert graph[visual_owner].isdisjoint(forbidden_outer)
    assert render_state in graph[view]
    assert {
        animation_presentation,
        commit_snapshot,
        landing_request_owner,
        live_visual_owner,
        pointer_drag_completion_owner,
        pointer_drag_start_owner,
        pointer_move_owner,
        pointer_region_visual,
        preview_geometry_refresh_owner,
        preview_frame_transition,
        preview_layout_transition_owner,
        preview_paint_snapshot_owner,
        render_publication_owner,
        visual_mode,
        visual_session,
        visual_owner,
        viewport_frame_refresh,
    } <= graph[overlay]
    assert drop_actual_observation not in graph[overlay]
    assert graph[interaction_metrics] == set()
    assert interaction_metrics in graph[overlay]
    assert interaction_metrics in graph[f"{prefix}interactions.reorder_overlay_port"]
    assert (
        f"{prefix}interactions.reorder_overlay_port"
        in graph[f"{prefix}interactions.reorder_overlay_session"]
    )
    assert interaction_metrics in graph[factory]
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_interaction_metrics.py"
    ).exists()
    assert graph[interaction_diagnostics] == {
        interaction_metrics,
        interaction_state,
        landing_models,
        f"{prefix}projection.reorder_chip_geometry",
    }
    assert interaction_diagnostics in graph[overlay]
    assert {
        chip_visuals,
        drop_actual_observation,
        interaction_diagnostics,
        reorder_telemetry,
    } <= graph[drop_commit_diagnostics]
    assert graph[drop_commit_diagnostics].isdisjoint(forbidden_outer)
    assert drop_commit_diagnostics in graph[overlay]
    assert graph[interaction_intents] == {
        "substitute.application.prompt_editor.reorder.intents",
        gesture_controller,
    }
    assert graph[interaction_intents].isdisjoint(forbidden_outer)
    assert interaction_intents in graph[overlay]
    assert graph[insertion_marker_owner] == {
        interaction_diagnostics,
        interaction_geometry,
        interaction_metrics,
        landing_models,
        landing_resolution_owner,
        gesture_controller,
        reorder_telemetry,
        f"{prefix}projection.observability",
    }
    assert graph[insertion_marker_owner].isdisjoint(
        {
            animation_presentation,
            drag_proxy_visual_owner,
            prepared_visual,
            raster_publication,
            render_state,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert insertion_marker_owner in graph[overlay]
    assert {
        chip_visuals,
        displacement_intent,
        gesture_controller,
        interaction_state,
        f"{prefix}projection.reorder_keyboard_navigation",
    } <= graph[keyboard_interaction]
    assert graph[keyboard_interaction].isdisjoint(forbidden_outer)
    assert keyboard_interaction in graph[overlay]
    assert drag_proxy_visual_owner in graph[overlay]
    assert {visual_owner, overlay} <= graph[factory]
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_paint_ownership.py"
    ).exists()
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_paint_publication.py"
    ).exists()
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_animation.py"
    ).exists()
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_landing_shadow.py"
    ).exists()
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_geometry.py"
    ).exists()
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_interaction.py"
    ).exists()
    overlay_ports_source = (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_ports.py"
    ).read_text(encoding="utf-8")
    assert "class PromptReorderDragProxyStateFactory" not in overlay_ports_source
