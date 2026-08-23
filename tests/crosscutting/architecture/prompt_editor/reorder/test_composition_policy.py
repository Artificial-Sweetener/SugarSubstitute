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

"""Keep reorder composition, policy, and session ownership directional."""

from __future__ import annotations

from ..inventory import (
    PROMPT_PRESENTATION_ROOT,
    prompt_editor_architecture_inventory,
)


def test_reorder_preview_publications_flow_through_typed_composition() -> None:
    """Keep preview facts coherent and below controller/composition adapters."""

    architecture = prompt_editor_architecture_inventory()
    module_paths = architecture.module_paths
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    value = f"{prefix}projection.reorder_preview_build_facts"
    interaction_state = f"{prefix}projection.reorder_interaction_geometry_state"
    visual_policy = f"{prefix}overlays.reorder_visual_mode_policy"
    facts_owner = f"{prefix}overlays.reorder_preview_build_facts"
    sync_context_owner = f"{prefix}overlays.reorder_preview_sync_context"
    publication_owner = f"{prefix}interactions.reorder_preview_publication"
    overlay = f"{prefix}overlays.reorder_overlay"
    visual_lifecycle = f"{prefix}overlays.reorder_overlay_visual_lifecycle"
    session_activation = f"{prefix}overlays.reorder_overlay_session_activation"
    port = f"{prefix}interactions.reorder_overlay_port"
    session = f"{prefix}interactions.reorder_overlay_session"
    factory = f"{prefix}composition.reorder_overlay_factory"
    composition_factory = f"{prefix}composition.factory"
    application_views = "substitute.application.prompt_editor.reorder.views"
    application_preview_sync = (
        "substitute.application.prompt_editor.reorder.preview_sync"
    )
    document_service = "substitute.application.prompt_editor.document.service"
    document_views = "substitute.application.prompt_editor.document.views"
    preview_builder = f"{prefix}projection.reorder_preview_state_builder"
    projection_provider = f"{prefix}projection.reorder_projection_snapshot_provider"
    interaction_metrics = f"{prefix}interactions.reorder_interaction_metrics"
    sync_adapter = f"{prefix}interactions.reorder_preview_sync"
    landing_models = f"{prefix}overlays.reorder_landing_models"
    placement_geometry = f"{prefix}projection.reorder_placement_geometry"

    assert graph[value] == {application_views}
    assert graph[visual_policy] == {application_views, interaction_state}
    assert graph[facts_owner] == {
        application_views,
        interaction_state,
        value,
        visual_policy,
    }
    assert graph[sync_context_owner] == {
        application_preview_sync,
        interaction_state,
        landing_models,
        placement_geometry,
    }
    assert graph[publication_owner] == {
        application_preview_sync,
        document_service,
        document_views,
        f"{prefix}core.state.revisions",
        f"{prefix}projection.observability",
        f"{prefix}projection.reorder_preview",
        preview_builder,
        projection_provider,
        interaction_metrics,
        port,
        sync_adapter,
    }
    assert facts_owner in graph[overlay]
    assert sync_context_owner in graph[overlay]
    assert visual_lifecycle in graph[overlay]
    assert session_activation in graph[overlay]
    assert graph[visual_lifecycle].isdisjoint(
        {
            overlay,
            session,
            factory,
            composition_factory,
            publication_owner,
            preview_builder,
            projection_provider,
        }
    )
    assert graph[session_activation].isdisjoint(
        {
            overlay,
            session,
            factory,
            composition_factory,
            publication_owner,
            preview_builder,
            projection_provider,
        }
    )
    assert publication_owner in graph[session]
    assert port in graph[session]
    assert graph[session].isdisjoint(
        {
            facts_owner,
            sync_context_owner,
            overlay,
            visual_policy,
            landing_models,
            interaction_state,
            placement_geometry,
            preview_builder,
            projection_provider,
            sync_adapter,
        }
    )
    assert graph[port].isdisjoint(
        {
            session,
            facts_owner,
            sync_context_owner,
            overlay,
            visual_policy,
            landing_models,
            interaction_state,
            placement_geometry,
            publication_owner,
        }
    )
    assert {overlay, port} <= graph[factory]
    assert publication_owner in graph[composition_factory]

    overlay_source = module_paths[overlay].read_text(encoding="utf-8")
    controller_source = module_paths[session].read_text(encoding="utf-8")
    factory_source = module_paths[factory].read_text(encoding="utf-8")
    for removed_query in (
        "def preview_reorder_state(",
        "def base_drag_reorder_state(",
        "def preview_layout_view(",
        "def drop_target(",
        "def dragged_segment_index(",
        "def base_drag_layout_view(",
        "def has_base_drag_placement_geometry(",
        "def should_flush_initial_landing_shadow_sync(",
        "def _clear_reorder_visual_snapshots(",
        "def _apply_theme_colors(",
        "def _delete_existing_chips(",
    ):
        assert removed_query not in overlay_source
    for obsolete_reach_through in (
        "overlay.preview_reorder_state(",
        "overlay.base_drag_reorder_state(",
        "overlay.preview_layout_view(",
        "overlay.drop_target(",
        "overlay.commit_snapshot().ordered_chip_indices",
        "overlay.dragged_segment_index(",
        "overlay.base_drag_layout_view(",
        "overlay.has_base_drag_placement_geometry(",
        "overlay.should_flush_initial_landing_shadow_sync(",
        "def schedule_reorder_preview_sync(",
        "def flush_pending_reorder_preview_sync(",
        "def _sync_reorder_preview_from_overlay(",
        "def _preview_sync_context(",
    ):
        assert obsolete_reach_through not in controller_source
    assert "-> object:" not in factory_source
    assert "cast(" not in factory_source


def test_reorder_autoscroll_state_flows_outward_from_one_owner() -> None:
    """Keep timer, coalescing, pending state, and counters under one owner."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor."
    autoscroll = f"{prefix}overlays.reorder_autoscroll"
    gesture_controller = f"{prefix}overlays.reorder_gesture_controller"
    interaction_diagnostics = f"{prefix}overlays.reorder_interaction_diagnostics"
    interaction_metrics = f"{prefix}interactions.reorder_interaction_metrics"
    observability = f"{prefix}projection.observability"
    overlay_ports = f"{prefix}overlays.reorder_overlay_ports"
    factory = f"{prefix}composition.reorder_overlay_factory"
    overlay = f"{prefix}overlays.reorder_overlay"

    assert graph[autoscroll] == {
        gesture_controller,
        interaction_diagnostics,
        interaction_metrics,
        observability,
    }
    assert autoscroll not in graph[overlay_ports]
    assert autoscroll not in graph[factory]
    assert autoscroll in graph[overlay]
    source = (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_autoscroll.py"
    ).read_text(encoding="utf-8")
    assert "class PromptReorderAutoscrollController" not in source
    overlay_sources = "\n".join(
        (PROMPT_PRESENTATION_ROOT / "overlays" / module_name).read_text(
            encoding="utf-8"
        )
        for module_name in ("reorder_overlay.py",)
    )
    removed_state = (
        "self._pending_autoscroll_invalidation",
        "self._instrumentation_autoscroll_schedule_count",
        "self._instrumentation_autoscroll_coalesced_count",
        "self._instrumentation_autoscroll_flush_count",
        "self._instrumentation_autoscroll_target_refresh_count",
        "def _autoscroll_context",
        "def _handle_autoscroll_step",
    )
    assert all(name not in overlay_sources for name in removed_state)
    assert "class PromptReorderAutoscrollFactory" not in (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_ports.py"
    ).read_text(encoding="utf-8")


def test_reorder_preview_policy_flows_outward_to_qt_adapters() -> None:
    """Keep preview freshness in application policy and Qt at the outer edge."""

    architecture = prompt_editor_architecture_inventory()
    module_paths = architecture.module_paths
    graph = architecture.graph
    schedule_policy = "substitute.application.prompt_editor.reorder.preview_schedule"
    sync_policy = "substitute.application.prompt_editor.reorder.preview_sync"
    timer_adapter = (
        "substitute.presentation.editor.prompt_editor.interactions."
        "reorder_preview_timer"
    )
    sync_adapter = (
        "substitute.presentation.editor.prompt_editor.interactions.reorder_preview_sync"
    )
    session = (
        "substitute.presentation.editor.prompt_editor.interactions."
        "reorder_overlay_session"
    )

    for policy_module in (schedule_policy, sync_policy):
        assert not {
            imported_module
            for imported_module in graph[policy_module]
            if imported_module.startswith("substitute.presentation.")
        }
        source = module_paths[policy_module].read_text(encoding="utf-8")
        assert "PySide6" not in source
    assert schedule_policy in graph[timer_adapter]
    assert sync_policy in graph[sync_adapter]
    assert timer_adapter in graph[sync_adapter]
    publication_owner = (
        "substitute.presentation.editor.prompt_editor.interactions."
        "reorder_preview_publication"
    )
    assert sync_policy in graph[publication_owner]
    assert sync_adapter in graph[publication_owner]
    assert publication_owner in graph[session]
    assert sync_policy not in graph[session]
    assert sync_adapter not in graph[session]

    preview_interaction_sources = tuple(
        (PROMPT_PRESENTATION_ROOT / "interactions").glob("reorder_preview*.py")
    )
    qt_timer_owners = {
        source_path.name
        for source_path in preview_interaction_sources
        if "QTimer" in source_path.read_text(encoding="utf-8")
    }
    assert qt_timer_owners == {"reorder_preview_timer.py"}
    assert "PromptReorderPreviewScheduler" not in "".join(
        source_path.read_text(encoding="utf-8")
        for source_path in preview_interaction_sources
    )


def test_reorder_selection_policy_flows_outward_to_qt_adapter() -> None:
    """Keep cursor interpretation in application policy and Qt at the outer edge."""

    architecture = prompt_editor_architecture_inventory()
    module_paths = architecture.module_paths
    graph = architecture.graph
    selection_policy = "substitute.application.prompt_editor.reorder.selection"
    lifecycle_owner = "substitute.application.prompt_editor.reorder.lifecycle"
    session = (
        "substitute.presentation.editor.prompt_editor.interactions."
        "reorder_overlay_session"
    )
    policy_source = module_paths[selection_policy].read_text(encoding="utf-8")
    session_source = module_paths[session].read_text(encoding="utf-8")

    assert graph[selection_policy] == {
        "substitute.application.prompt_editor.document.views"
    }
    assert "PySide6" not in policy_source
    assert graph[lifecycle_owner] == {
        "substitute.application.prompt_editor.document.service",
        "substitute.application.prompt_editor.document.views",
        selection_policy,
        "substitute.application.prompt_editor.reorder.session",
        "substitute.application.prompt_editor.reorder.views",
    }
    assert lifecycle_owner in graph[session]
    assert selection_policy not in graph[session]
    assert all(
        obsolete_method not in session_source
        for obsolete_method in (
            "_active_segment_index_for_reorder",
            "_nearest_preceding_reorder_chip",
            "_segment_reorder_selection_bounds",
            "_segment_reorder_selection_offsets_within_active_chip",
            "_position_within_reorder_chip",
        )
    )


def test_reorder_session_and_intents_are_application_owned() -> None:
    """Keep commit truth immutable and upstream of presentation adapters."""

    architecture = prompt_editor_architecture_inventory()
    module_paths = architecture.module_paths
    graph = architecture.graph
    application_owners = {
        "substitute.application.prompt_editor.reorder.intents",
        "substitute.application.prompt_editor.reorder.lifecycle",
        "substitute.application.prompt_editor.reorder.session",
    }
    for owner in application_owners:
        assert not {
            imported_module
            for imported_module in graph[owner]
            if imported_module.startswith("substitute.presentation.")
        }
        assert "PySide6" not in module_paths[owner].read_text(encoding="utf-8")
    session_owner = "substitute.application.prompt_editor.reorder.session"
    lifecycle_owner = "substitute.application.prompt_editor.reorder.lifecycle"
    commit_owner = "substitute.application.prompt_editor.reorder.commit"
    assert graph[session_owner] == {
        commit_owner,
        "substitute.application.prompt_editor.reorder.views",
    }
    assert graph[commit_owner] == {"substitute.application.prompt_editor.reorder.views"}
    commit_source = module_paths[commit_owner].read_text(encoding="utf-8")
    assert "PySide6" not in commit_source
    deleted_owners = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "reorder_session.py",
        PROMPT_PRESENTATION_ROOT / "interactions" / "reorder_controller.py",
    )
    assert not any(path.exists() for path in deleted_owners)
    mixed_models_source = (PROMPT_PRESENTATION_ROOT / "models.py").read_text(
        encoding="utf-8"
    )
    assert "SegmentReorderSession" not in mixed_models_source
    assert "class PromptReorderCommitSnapshot" not in mixed_models_source
    assert "class PromptReorderCommitIntent" not in mixed_models_source
    assert "class PromptReorderCancelIntent" not in mixed_models_source
    assert "class PromptReorderKeyboardMoveIntent" not in mixed_models_source
    interaction_module = (
        "substitute.presentation.editor.prompt_editor.interactions.reorder_interaction"
    )
    overlay_session_module = (
        "substitute.presentation.editor.prompt_editor.interactions."
        "reorder_overlay_session"
    )
    interaction_source = module_paths[interaction_module].read_text(encoding="utf-8")
    overlay_session_source = module_paths[overlay_session_module].read_text(
        encoding="utf-8"
    )
    command_module = (
        "substitute.presentation.editor.prompt_editor.commands.reorder_commands"
    )
    command_source = module_paths[command_module].read_text(encoding="utf-8")
    assert commit_owner in graph[command_module]
    assert "class PromptReorderLayoutCommitRequest" not in command_source
    assert '"PromptReorderLayoutCommitRequest"' not in command_source
    assert "core.state.revisions" not in command_source
    assert all(
        obsolete_fragment not in interaction_source
        for obsolete_fragment in (
            ".prepare_commit(",
            "restore_selection_on_close",
            "_session_owner.reset(",
            "_restore_segment_reorder_selection",
            "def _close_segment_overlay(",
            "self._close_segment_overlay(",
            "getattr(",
        )
    )
    assert lifecycle_owner in graph[interaction_module]
    assert lifecycle_owner in graph[overlay_session_module]
    assert "PromptReorderOverlaySessionOwner" in overlay_session_source
