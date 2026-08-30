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

"""Keep landing capture, resolution, state, and paint ownership focused."""

from __future__ import annotations

from ..inventory import (
    prompt_editor_architecture_inventory,
)


def test_reorder_landing_publication_flows_outward_to_qt_adapters() -> None:
    """Keep landing capture, resolution, state, and paint ownership focused."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    visual_geometry = f"{prefix}overlays.reorder_visual_geometry"
    visual_style = f"{prefix}overlays.reorder_visual_style"
    render_state = f"{prefix}overlays.reorder_render_state"
    animation_presentation = f"{prefix}overlays.reorder_animation_presentation"
    chip_visuals = f"{prefix}overlays.chip_visuals"
    drag_proxy_visual_owner = f"{prefix}overlays.reorder_drag_proxy_visual_owner"
    event_ports = f"{prefix}overlays.reorder_event_ports"
    landing_models = f"{prefix}overlays.reorder_landing_models"
    landing_capture = f"{prefix}overlays.reorder_landing_capture"
    landing_diagnostics = f"{prefix}overlays.reorder_landing_diagnostics"
    landing_events = f"{prefix}overlays.reorder_landing_events"
    landing_geometry = f"{prefix}overlays.reorder_landing_geometry"
    landing_paint_cache = f"{prefix}overlays.reorder_landing_paint_cache"
    landing_paint_policy = f"{prefix}overlays.reorder_landing_paint_policy"
    landing_request_owner = f"{prefix}overlays.reorder_landing_request_owner"
    landing_state = f"{prefix}overlays.reorder_landing_state"
    landing_resolution_owner = f"{prefix}overlays.reorder_landing_resolution"
    landing_paint_owner = f"{prefix}overlays.reorder_landing_paint"
    landing_visual_owner = landing_paint_owner
    reorder_telemetry = f"{prefix}overlays.reorder_telemetry"
    interaction_metrics = f"{prefix}interactions.reorder_interaction_metrics"
    prepared_visual = f"{prefix}overlays.reorder_prepared_visual"
    render_publication_owner = f"{prefix}overlays.reorder_render_publication_owner"
    raster_publication = f"{prefix}overlays.reorder_raster_publication"
    visual_mode = f"{prefix}overlays.reorder_visual_mode"
    visual_session = f"{prefix}overlays.reorder_visual_session"
    visual_owner = f"{prefix}overlays.reorder_preview_visual_owner"
    viewport_geometry = f"{prefix}overlays.reorder_viewport_geometry"
    view = f"{prefix}overlays.reorder_view"
    overlay = f"{prefix}overlays.reorder_overlay"
    factory = f"{prefix}composition.reorder_overlay_factory"
    gesture_controller = f"{prefix}overlays.reorder_gesture_controller"
    interaction_geometry = f"{prefix}projection.reorder_interaction_geometry"
    interaction_geometry_identity = (
        f"{prefix}projection.reorder_interaction_geometry_identity"
    )
    forbidden_outer = {
        view,
        overlay,
        f"{prefix}projection.surface",
        f"{prefix}interactions.reorder_interaction",
        f"{prefix}widget",
        factory,
    }

    assert graph[landing_models].isdisjoint(
        {
            landing_paint_cache,
            landing_diagnostics,
            landing_events,
            landing_state,
            landing_visual_owner,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {chip_visuals, landing_models} <= graph[landing_capture]
    assert graph[landing_capture].isdisjoint(
        {
            reorder_telemetry,
            landing_diagnostics,
            landing_events,
            landing_paint_cache,
            landing_state,
            landing_visual_owner,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {chip_visuals, landing_models} <= graph[landing_geometry]
    assert graph[landing_geometry].isdisjoint(
        {
            reorder_telemetry,
            landing_capture,
            landing_diagnostics,
            landing_events,
            landing_paint_cache,
            landing_state,
            landing_visual_owner,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {landing_models, render_state, visual_style} <= graph[landing_paint_cache]
    assert graph[landing_paint_cache].isdisjoint(
        {
            landing_diagnostics,
            landing_events,
            landing_state,
            landing_visual_owner,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {
        chip_visuals,
        event_ports,
        interaction_geometry_identity,
        landing_models,
        reorder_telemetry,
        visual_geometry,
    } <= graph[landing_diagnostics]
    assert graph[landing_diagnostics].isdisjoint(
        {
            landing_capture,
            landing_geometry,
            landing_events,
            landing_paint_cache,
            landing_state,
            landing_visual_owner,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {chip_visuals, landing_models} <= graph[landing_state]
    assert graph[landing_state].isdisjoint(
        {
            landing_capture,
            landing_diagnostics,
            landing_events,
            landing_geometry,
            landing_paint_cache,
            landing_visual_owner,
            reorder_telemetry,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert graph[event_ports].isdisjoint(
        {
            landing_capture,
            landing_diagnostics,
            landing_events,
            landing_geometry,
            landing_models,
            landing_paint_cache,
            landing_state,
            landing_visual_owner,
            reorder_telemetry,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {
        chip_visuals,
        event_ports,
        interaction_geometry_identity,
        landing_capture,
        landing_models,
        landing_state,
        reorder_telemetry,
    } <= graph[landing_events]
    assert graph[landing_events].isdisjoint(
        {
            landing_diagnostics,
            landing_geometry,
            landing_paint_cache,
            landing_visual_owner,
            render_state,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {chip_visuals, render_state, visual_style} <= graph[landing_paint_policy]
    assert graph[landing_paint_policy].isdisjoint(
        {
            landing_capture,
            landing_diagnostics,
            landing_events,
            landing_geometry,
            landing_models,
            landing_paint_cache,
            landing_state,
            landing_visual_owner,
            reorder_telemetry,
            prepared_visual,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert all(
        landing_paint_policy not in graph[module]
        for module in (
            event_ports,
            landing_capture,
            landing_diagnostics,
            landing_events,
            landing_geometry,
            landing_models,
            landing_paint_cache,
            landing_state,
        )
    )
    assert {
        landing_models,
        landing_diagnostics,
        landing_events,
        landing_geometry,
        landing_state,
        reorder_telemetry,
    } <= graph[landing_resolution_owner]
    assert graph[landing_resolution_owner].isdisjoint(
        {
            landing_capture,
            landing_paint_cache,
            landing_paint_owner,
            landing_paint_policy,
            prepared_visual,
            render_publication_owner,
            visual_owner,
            view,
        }
        | forbidden_outer
    )
    assert {
        landing_diagnostics,
        landing_events,
        landing_models,
        landing_paint_cache,
        landing_paint_policy,
        landing_resolution_owner,
        landing_state,
        reorder_telemetry,
    } <= graph[landing_paint_owner]
    assert graph[landing_paint_owner].isdisjoint(
        {landing_capture, landing_geometry, prepared_visual, visual_owner, view}
        | forbidden_outer
    )
    assert graph[landing_request_owner] == {
        gesture_controller,
        interaction_metrics,
        landing_models,
        visual_owner,
        viewport_geometry,
        visual_mode,
        visual_session,
        interaction_geometry,
        interaction_geometry_identity,
    }
    assert graph[landing_request_owner].isdisjoint(
        {
            animation_presentation,
            drag_proxy_visual_owner,
            landing_visual_owner,
            prepared_visual,
            raster_publication,
            render_state,
            view,
        }
        | forbidden_outer
    )
