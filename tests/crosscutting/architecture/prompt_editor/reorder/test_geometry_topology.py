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

import ast

from ..inventory import (
    PROJECT_ROOT,
    PROMPT_PRESENTATION_ROOT,
    prompt_editor_architecture_inventory,
)


def test_reorder_geometry_depends_on_geometry_not_paint_or_layout_hosts() -> None:
    """Keep reorder queries downstream of published geometry alone."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    reorder_modules = {
        "substitute.presentation.editor.prompt_editor.projection.reorder_geometry",
        "substitute.presentation.editor.prompt_editor.projection.reorder_scroll_geometry",
    }
    forbidden_modules = {
        "substitute.presentation.editor.prompt_editor.projection.layout_engine",
        "substitute.presentation.editor.prompt_editor.projection.paint_input",
    }

    assert {
        module_name: tuple(sorted(graph[module_name] & forbidden_modules))
        for module_name in reorder_modules
        if graph[module_name] & forbidden_modules
    } == {}


def test_reorder_preview_layout_uses_engines_without_transitional_host() -> None:
    """Keep preview construction owned by engines and immutable prepared frames."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    builder_module = (
        "substitute.presentation.editor.prompt_editor.projection."
        "reorder_preview_layout_builder"
    )
    service_module = (
        "substitute.presentation.editor.prompt_editor.projection."
        "reorder_preview_projection_owner"
    )
    transitional_host = (
        "substitute.presentation.editor.prompt_editor.projection.layout_engine"
    )

    assert transitional_host not in graph[builder_module]
    assert transitional_host not in graph[service_module]
    assert {
        "substitute.presentation.editor.prompt_editor.layout.canonical_engine",
        "substitute.presentation.editor.prompt_editor.layout.configuration",
        "substitute.presentation.editor.prompt_editor.projection.prepared_frame",
    } <= graph[builder_module]


def test_reorder_preview_projection_has_one_way_focused_owners() -> None:
    """Keep semantic build, frame build, cache, and publication ownership distinct."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor.projection."
    provider = f"{prefix}reorder_projection_snapshot_provider"
    contracts = f"{prefix}reorder_preview_projection_contracts"
    metrics = f"{prefix}reorder_preview_projection_metrics"
    frame_cache = f"{prefix}reorder_preview_frame_cache"
    frame_builder = f"{prefix}reorder_preview_frame_builder"
    owner = f"{prefix}reorder_preview_projection_owner"
    state_builder = f"{prefix}reorder_preview_state_builder"
    interaction = (
        "substitute.presentation.editor.prompt_editor.interactions.reorder_interaction"
    )
    forbidden_outer = {
        f"{prefix}surface",
        "substitute.presentation.editor.prompt_editor.widget",
        interaction,
        "substitute.presentation.editor.prompt_editor.overlays.reorder_overlay",
    }

    assert not (
        PROJECT_ROOT
        / "substitute"
        / "presentation"
        / "editor"
        / "prompt_editor"
        / "projection"
        / "reorder_preview_projection.py"
    ).exists()
    assert graph[provider].isdisjoint(
        {contracts, metrics, frame_cache, frame_builder, owner} | forbidden_outer
    )
    assert graph[contracts].isdisjoint(
        {provider, metrics, frame_cache, frame_builder, owner} | forbidden_outer
    )
    assert graph[metrics].isdisjoint(
        {provider, contracts, frame_cache, frame_builder, owner} | forbidden_outer
    )
    assert graph[frame_cache].isdisjoint(
        {provider, frame_builder, owner} | forbidden_outer
    )
    assert graph[frame_builder].isdisjoint(
        {provider, contracts, frame_cache, owner} | forbidden_outer
    )
    assert {contracts, metrics, frame_cache, frame_builder} <= graph[owner]
    assert graph[owner].isdisjoint({provider} | forbidden_outer)
    assert graph[state_builder] == {
        "substitute.application.prompt_editor.document.service",
        "substitute.application.prompt_editor.document.views",
        "substitute.application.prompt_editor.reorder.views",
        f"{prefix}observability",
        f"{prefix}reorder_interaction_geometry_identity",
        f"{prefix}reorder_preview",
        provider,
    }
    assert graph[state_builder].isdisjoint(forbidden_outer)
    publication_owner = (
        "substitute.presentation.editor.prompt_editor.interactions."
        "reorder_preview_publication"
    )
    assert state_builder in graph[publication_owner]
    assert state_builder not in graph[interaction]
    interaction_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "reorder_interaction.py"
    ).read_text(encoding="utf-8")
    assert not any(
        obsolete_method in interaction_source
        for obsolete_method in (
            "_sync_base_drag_only_preview",
            "_sync_active_preview",
            "_publish_reorder_preview_state",
            "_build_reorder_preview_projection_result",
            "_current_preview_viewport_width",
            "_overlay_drop_target",
            "_active_drop_target_identity",
            "_preview_sync_requires_immediate_drag_geometry",
            "_preview_sync_requires_initial_landing_shadow",
        )
    )


def test_reorder_geometry_flows_from_published_inputs_without_widget_host() -> None:
    """Keep geometry construction below surface, overlay, and interaction adapters."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    geometry_owner = f"{prefix}projection.reorder_geometry_owner"
    interaction_geometry = f"{prefix}projection.reorder_interaction_geometry"
    forbidden_outer = {
        f"{prefix}projection.surface",
        f"{prefix}widget",
        f"{prefix}overlays.reorder_overlay",
        f"{prefix}overlays.reorder_overlay_ports",
        f"{prefix}composition.reorder_overlay_factory",
    }
    owner_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "reorder_geometry_owner.py"
    ).read_text(encoding="utf-8")
    interaction_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "reorder_interaction_geometry.py"
    ).read_text(encoding="utf-8")

    assert graph[geometry_owner].isdisjoint(forbidden_outer | {interaction_geometry})
    assert geometry_owner in graph[interaction_geometry]
    assert graph[interaction_geometry].isdisjoint(forbidden_outer)
    assert "PromptReorderGeometryHost" not in owner_source
    assert "PromptReorderGeometryHost" not in interaction_source
    assert "_geometry_host" not in interaction_source


def test_reorder_geometry_cache_has_one_way_focused_owners() -> None:
    """Keep identity, storage, metrics, and orchestration in their owning modules."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    projection = f"{prefix}projection."
    identity = f"{projection}reorder_chip_visual_identity"
    keys = f"{projection}reorder_geometry_cache_keys"
    metrics = f"{projection}reorder_geometry_metrics"
    diagnostics = f"{projection}reorder_geometry_diagnostics"
    chip_cache = f"{projection}reorder_chip_geometry_cache"
    placement_cache = f"{projection}reorder_placement_geometry_cache"
    owner = f"{projection}reorder_geometry_owner"
    focused_modules = {
        identity,
        keys,
        metrics,
        diagnostics,
        chip_cache,
        placement_cache,
        owner,
    }
    forbidden_outer = {
        f"{projection}surface",
        f"{prefix}widget",
        f"{prefix}overlays.reorder_overlay",
        f"{prefix}interactions.reorder_interaction",
    }

    assert not (
        PROMPT_PRESENTATION_ROOT / "projection" / "reorder_geometry_cache.py"
    ).exists()
    assert graph[identity].isdisjoint((focused_modules - {identity}) | forbidden_outer)
    assert graph[keys].isdisjoint((focused_modules - {keys}) | forbidden_outer)
    assert graph[metrics].isdisjoint((focused_modules - {metrics}) | forbidden_outer)
    assert graph[diagnostics].isdisjoint(
        {identity, metrics, chip_cache, placement_cache, owner} | forbidden_outer
    )
    assert {identity, keys, metrics} <= graph[chip_cache]
    assert graph[chip_cache].isdisjoint({placement_cache, owner} | forbidden_outer)
    assert {keys, metrics} <= graph[placement_cache]
    assert graph[placement_cache].isdisjoint(
        {identity, chip_cache, owner} | forbidden_outer
    )
    assert {keys, metrics, diagnostics, chip_cache, placement_cache} <= graph[owner]
    assert graph[owner].isdisjoint(forbidden_outer)


def test_reorder_interaction_geometry_publishes_one_immutable_state() -> None:
    """Forbid cross-object field mutation and independently mutable state shards."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    state_module = f"{prefix}projection.reorder_interaction_geometry_state"
    owner_module = f"{prefix}projection.reorder_interaction_geometry"
    forbidden_outer = {
        f"{prefix}projection.surface",
        f"{prefix}widget",
        f"{prefix}overlays.reorder_overlay",
        f"{prefix}interactions.reorder_interaction",
    }
    owner_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "reorder_interaction_geometry.py"
    ).read_text(encoding="utf-8")
    overlay_sources = "\n".join(
        (PROMPT_PRESENTATION_ROOT / "overlays" / module_name).read_text(
            encoding="utf-8"
        )
        for module_name in ("reorder_overlay.py",)
    )
    publication_fields = (
        "document_view",
        "original_layout_view",
        "current_layout_view",
        "base_drag_layout_view",
        "preview_layout_view",
        "original_reorder_state",
        "current_reorder_state",
        "base_drag_reorder_state",
        "preview_reorder_state",
        "preview_snapshot",
        "base_drag_snapshot",
        "preview_layout_target_identity",
        "preview_geometry_target_identity",
        "live_chip_geometry_snapshot",
        "preview_chip_geometry_snapshot",
        "base_drag_chip_geometry_snapshot",
        "placement_snapshot",
        "active_placement",
        "drop_target_visuals",
        "drop_target_lanes",
        "initial_ordered_indices",
        "ordered_segment_indices",
        "last_base_drag_geometry_key",
    )

    assert graph[state_module].isdisjoint({owner_module} | forbidden_outer)
    assert state_module in graph[owner_module]
    assert all(f"self.{field} =" not in owner_source for field in publication_fields)
    assert all(
        f"self._geometry.{field} =" not in overlay_sources
        for field in publication_fields
    )
    session_mirror_fields = (
        "document_view",
        "original_layout_view",
        "current_layout_view",
        "base_drag_layout_view",
        "preview_layout_view",
        "original_reorder_state",
        "current_reorder_state",
        "base_drag_reorder_state",
        "preview_reorder_state",
        "preview_snapshot",
        "base_drag_snapshot",
        "preview_layout_target_identity",
        "initial_ordered_indices",
        "ordered_segment_indices",
    )
    overlay_self_attributes = {
        node.attr
        for node in ast.walk(ast.parse(overlay_sources))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }
    assert all(
        f"_{field}" not in overlay_self_attributes for field in session_mirror_fields
    )
