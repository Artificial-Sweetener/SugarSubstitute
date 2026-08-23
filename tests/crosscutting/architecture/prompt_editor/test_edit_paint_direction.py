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

"""Keep prompt-editor core, layout, edit, and paint boundaries directional."""

from __future__ import annotations

import ast

from .inventory import (
    PROMPT_PRESENTATION_ROOT,
    prompt_editor_architecture_inventory,
)


def test_prepared_paint_owners_remain_focused_and_directional() -> None:
    """Keep paint preparation flowing toward immutable layers and render sinks."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    prefix = "substitute.presentation.editor.prompt_editor.projection."
    render_state_modules = {
        f"{prefix}caret_render_state",
        f"{prefix}content_media_state",
        f"{prefix}input_method_render_state",
        f"{prefix}region_chrome_state",
        f"{prefix}search_highlight_layer",
        f"{prefix}source_line_render_state",
        f"{prefix}transient_edit_render_state",
    }
    render_owner_modules = {
        f"{prefix}caret_layer_owner",
        f"{prefix}content_media_owner",
        f"{prefix}diagnostic_layer_assets",
        f"{prefix}diagnostic_layer_owner",
        f"{prefix}diagnostic_layer_preparer",
        f"{prefix}input_method_controller",
        f"{prefix}input_method_layer_preparer",
        f"{prefix}region_chrome",
        f"{prefix}search_highlight_owner",
        f"{prefix}source_line_chrome",
        f"{prefix}transient_edit_layer_owner",
    }
    render_sink_modules = {
        f"{prefix}caret_renderer",
        f"{prefix}diagnostic_renderer",
        f"{prefix}input_method_renderer",
        f"{prefix}paint_cache",
        f"{prefix}region_chrome_renderer",
        f"{prefix}search_highlight_renderer",
        f"{prefix}source_line_renderer",
        f"{prefix}transient_edit_renderer",
    }
    aggregate_render_modules = {
        f"{prefix}render_frame",
        f"{prefix}render_frame_owner",
        f"{prefix}render_compositor",
        f"{prefix}surface",
    }
    upper_paint_owners = {
        f"{prefix}content_selection_owner",
        f"{prefix}diagnostic_layer_assets",
        f"{prefix}diagnostic_layer_owner",
        f"{prefix}diagnostic_layer_preparer",
        f"{prefix}diagnostic_layer_state",
        f"{prefix}diagnostic_renderer",
        f"{prefix}paint_cache",
        f"{prefix}paint_input",
        f"{prefix}painter",
        f"{prefix}prepared_frame",
        f"{prefix}surface",
    }
    forbidden_edges = {
        f"{prefix}content_inline_bindings": upper_paint_owners,
        f"{prefix}content_selection_layer": upper_paint_owners,
        f"{prefix}content_text_styles": upper_paint_owners,
        f"{prefix}diagnostic_fragment_cache": upper_paint_owners,
        f"{prefix}diagnostic_render_layer": upper_paint_owners,
        f"{prefix}diagnostic_wave_tiles": upper_paint_owners,
        f"{prefix}diagnostic_layer_assets": {
            f"{prefix}diagnostic_layer_owner",
            f"{prefix}diagnostic_layer_preparer",
            f"{prefix}diagnostic_layer_state",
            f"{prefix}diagnostic_renderer",
            f"{prefix}surface",
        },
        f"{prefix}diagnostic_layer_state": {
            f"{prefix}diagnostic_layer_assets",
            f"{prefix}diagnostic_layer_owner",
            f"{prefix}diagnostic_layer_preparer",
            f"{prefix}diagnostic_renderer",
            f"{prefix}surface",
        },
        f"{prefix}diagnostic_renderer": {
            f"{prefix}diagnostic_layer_assets",
            f"{prefix}diagnostic_layer_owner",
            f"{prefix}diagnostic_layer_preparer",
            f"{prefix}diagnostic_layer_state",
            f"{prefix}surface",
        },
        f"{prefix}diagnostic_layer_preparer": {
            f"{prefix}diagnostic_layer_assets",
            f"{prefix}diagnostic_layer_owner",
            f"{prefix}diagnostic_renderer",
            f"{prefix}diagnostic_layer_state",
            f"{prefix}surface",
        },
        f"{prefix}region_chrome": {f"{prefix}surface"},
        f"{prefix}search_highlight_layer": {f"{prefix}surface"},
        f"{prefix}source_line_chrome": {f"{prefix}surface"},
    }
    state_forbidden = (
        render_owner_modules | render_sink_modules | aggregate_render_modules
    )
    owner_forbidden = render_sink_modules | {
        f"{prefix}render_frame",
        f"{prefix}render_frame_owner",
        f"{prefix}render_compositor",
        f"{prefix}surface",
    }
    sink_forbidden = render_owner_modules | aggregate_render_modules
    forbidden_edges.update(
        {
            module_name: forbidden_edges.get(module_name, set()) | state_forbidden
            for module_name in render_state_modules
        }
    )
    forbidden_edges.update(
        {
            module_name: forbidden_edges.get(module_name, set()) | owner_forbidden
            for module_name in render_owner_modules
        }
    )
    forbidden_edges.update(
        {
            module_name: forbidden_edges.get(module_name, set()) | sink_forbidden
            for module_name in render_sink_modules
        }
    )
    forbidden_edges[f"{prefix}render_frame"] = (
        render_owner_modules
        | render_sink_modules
        | {
            f"{prefix}render_frame_owner",
            f"{prefix}render_compositor",
            f"{prefix}surface",
        }
    )
    forbidden_edges[f"{prefix}render_frame_owner"] = render_sink_modules | {
        f"{prefix}render_compositor",
        f"{prefix}surface",
    }
    forbidden_edges[f"{prefix}render_compositor"] = render_owner_modules | {
        f"{prefix}surface"
    }

    assert {
        module_name: tuple(sorted(graph[module_name] & forbidden))
        for module_name, forbidden in forbidden_edges.items()
        if graph[module_name] & forbidden
    } == {}


def test_edit_classifier_remains_pure_and_bounded() -> None:
    """Keep path selection independent of Qt, layout, and mutable editor hosts."""

    modules = ("edit_classifier.py", "edit_strategy.py")
    forbidden_prefixes = (
        "PySide6",
        "qfluentwidgets",
        "substitute.application",
        "substitute.domain",
        "substitute.presentation",
    )
    violations: dict[str, object] = {}
    for file_name in modules:
        source_path = PROMPT_PRESENTATION_ROOT / "projection" / file_name
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        forbidden_imports = {
            imported
            for imported in imported_modules
            if imported.startswith(forbidden_prefixes)
        }
        if forbidden_imports:
            violations[file_name] = {
                "forbidden_imports": tuple(sorted(forbidden_imports)),
            }

    assert violations == {}


def test_edit_fact_owners_remain_focused_and_outward_independent() -> None:
    """Keep bounded edit facts outside mutable surface and Qt ownership."""

    modules = ("edit_fact_resolver.py", "source_edit_projection_policy.py")
    forbidden_prefixes = (
        "PySide6",
        "qfluentwidgets",
        "substitute.application",
        "substitute.domain",
    )
    forbidden_projection_modules = {
        "substitute.presentation.editor.prompt_editor.projection.freshness_controller",
        "substitute.presentation.editor.prompt_editor.projection.session",
        "substitute.presentation.editor.prompt_editor.projection.surface",
    }
    violations: dict[str, object] = {}
    for file_name in modules:
        source_path = PROMPT_PRESENTATION_ROOT / "projection" / file_name
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        forbidden_imports = {
            imported
            for imported in imported_modules
            if imported.startswith(forbidden_prefixes)
            or imported in forbidden_projection_modules
        }
        if forbidden_imports:
            violations[file_name] = {
                "forbidden_imports": tuple(sorted(forbidden_imports)),
            }

    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )
    obsolete_surface_policy = {
        method_name
        for method_name in (
            "_can_defer_syntax_sensitive_autocomplete_prefix",
            "_comma_requires_immediate_projection",
            "_source_edit_requires_canonical_rebuild",
            "_source_range_intersects_projected_token",
            "_typed_character_requires_immediate_projection",
        )
        if f"def {method_name}(" in surface_source
    }

    assert violations == {}
    assert obsolete_surface_policy == set()


def test_edit_pipeline_owns_selection_without_reentering_integration_roots() -> None:
    """Keep edit orchestration focused and remove controller-side selection."""

    modules = (
        "deferred_feedback_strategy.py",
        "direct_feedback_strategy.py",
        "edit_pipeline.py",
        "edit_pipeline_contracts.py",
        "edit_publication.py",
        "history_checkpoint_strategy.py",
        "incremental_edit_contracts.py",
        "incremental_layout_editor.py",
        "incremental_reflow_strategy.py",
        "plain_text_document_editor.py",
        "plain_text_document_remapper.py",
        "plain_text_edit_policy.py",
        "projection_build_context.py",
        "prompt_state_projection_strategy.py",
        "render_plan_ranges.py",
        "source_text_edit.py",
        "source_edit_projection_facts.py",
        "source_commit_application.py",
        "source_commit_ports.py",
        "source_document_commit_application.py",
        "source_history_commit_application.py",
        "source_range_commit_application.py",
        "source_change_transaction.py",
        "source_projection_application.py",
        "semantic_transition_strategy.py",
        "trailing_document_editor.py",
        "trailing_edit_strategy.py",
    )
    forbidden_fragments = {
        "qfluentwidgets",
        "projection.surface",
        "projection.source_change_applier",
    }
    violations: dict[str, object] = {}
    for file_name in modules:
        source_path = PROMPT_PRESENTATION_ROOT / "projection" / file_name
        source = source_path.read_text(encoding="utf-8")
        qt_boundary_modules = {
            "deferred_feedback_strategy.py",
            "direct_feedback_strategy.py",
            "edit_publication.py",
            "source_commit_ports.py",
            "source_document_commit_application.py",
            "source_edit_projection_facts.py",
        }
        file_forbidden_fragments = forbidden_fragments | (
            set() if file_name in qt_boundary_modules else {"PySide6"}
        )
        tree = ast.parse(source)
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        forbidden_imports = {
            imported
            for imported in imported_modules
            if any(fragment in imported for fragment in file_forbidden_fragments)
        }
        if forbidden_imports:
            violations[file_name] = {
                "forbidden_imports": tuple(sorted(forbidden_imports)),
            }

    controller_path = (
        PROMPT_PRESENTATION_ROOT / "projection" / "incremental_apply_controller.py"
    )
    source_applier_path = (
        PROMPT_PRESENTATION_ROOT / "projection" / "source_change_applier.py"
    )
    source_projection_application_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "source_projection_application.py"
    ).read_text(encoding="utf-8")
    source_change_transaction_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "source_change_transaction.py"
    ).read_text(encoding="utf-8")
    incremental_editor_path = (
        PROMPT_PRESENTATION_ROOT / "projection" / "incremental_editor.py"
    )
    plain_text_document_editor_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "plain_text_document_editor.py"
    ).read_text(encoding="utf-8")
    prompt_state_applier_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "prompt_state_applier.py"
    ).read_text(encoding="utf-8")
    edit_classifier_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "edit_classifier.py"
    ).read_text(encoding="utf-8")
    edit_pipeline_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "edit_pipeline.py"
    ).read_text(encoding="utf-8")
    edit_pipeline_ports_path = (
        PROMPT_PRESENTATION_ROOT / "projection" / "edit_pipeline_ports.py"
    )
    edit_terminal_effects_path = (
        PROMPT_PRESENTATION_ROOT / "projection" / "edit_terminal_effects.py"
    )
    prompt_state_strategy_source = (
        PROMPT_PRESENTATION_ROOT / "projection" / "prompt_state_projection_strategy.py"
    ).read_text(encoding="utf-8")
    surface_source = (PROMPT_PRESENTATION_ROOT / "projection" / "surface.py").read_text(
        encoding="utf-8"
    )

    assert violations == {}
    assert not controller_path.exists()
    assert not incremental_editor_path.exists()
    assert not source_applier_path.exists()
    assert not edit_pipeline_ports_path.exists()
    assert not edit_terminal_effects_path.exists()
    assert "REUSE_PREPARED_STATE" not in edit_classifier_source
    assert (
        "try_apply_source_changed_prompt_state_without_geometry_rebuild"
        not in edit_pipeline_source
    )
    assert "def fast_trailing_" not in plain_text_document_editor_source
    assert "host._" not in source_change_transaction_source
    assert "_incremental_apply_controller" not in surface_source
    assert "_source_change_applier" not in surface_source
    assert "self._pipeline.apply(" in source_projection_application_source
    assert "self._strategy.try_trailing_insert(" in (prompt_state_applier_source)
    assert "PromptStateSemanticTransitionPort" not in prompt_state_strategy_source
    assert "self._semantic_transition.try_apply(" in prompt_state_strategy_source


def test_paint_pipeline_consumes_prepared_inputs_not_layout_host() -> None:
    """Keep projection drawing independent of the transitional layout aggregate."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
    paint_modules = {
        "substitute.presentation.editor.prompt_editor.projection.chip_painter",
        "substitute.presentation.editor.prompt_editor.projection.paint_cache",
        "substitute.presentation.editor.prompt_editor.projection.paint_input",
        "substitute.presentation.editor.prompt_editor.projection.painter",
    }
    forbidden_host = (
        "substitute.presentation.editor.prompt_editor.projection.layout_engine"
    )

    assert {
        module_name: forbidden_host
        for module_name in paint_modules
        if forbidden_host in graph[module_name]
    } == {}
