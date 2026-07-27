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

"""Prevent prompt-editor architecture debt from growing during migration."""

from __future__ import annotations

import ast
from pathlib import Path

from tests.architecture_import_graph import (
    internal_import_graph,
    python_module_paths,
    strongly_connected_components,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_DOMAIN_ROOT = PROJECT_ROOT / "substitute" / "domain" / "prompt"
PROMPT_APPLICATION_ROOT = PROJECT_ROOT / "substitute" / "application" / "prompt_editor"
PROMPT_PRESENTATION_ROOT = (
    PROJECT_ROOT / "substitute" / "presentation" / "editor" / "prompt_editor"
)
EDITOR_PANEL_ROOT = PROJECT_ROOT / "substitute" / "presentation" / "editor" / "panel"
PROMPT_ARCHITECTURE_ROOTS = (
    PROMPT_DOMAIN_ROOT,
    PROMPT_APPLICATION_ROOT,
    PROMPT_PRESENTATION_ROOT,
    EDITOR_PANEL_ROOT,
)
PANEL_MODULE_PREFIX = "substitute.presentation.editor.panel"
_TARGET_DOMAIN_PACKAGES = frozenset(
    {
        "document",
        "emphasis",
        "features",
        "preferences",
        "regions",
        "reorder",
        "scenes",
        "wildcards",
    }
)
_TARGET_APPLICATION_PACKAGES = frozenset(
    {
        "autocomplete",
        "diagnostics",
        "document",
        "editing",
        "features",
        "lora",
        "projection",
        "reorder",
        "scenes",
    }
)

_EXPECTED_PROMPT_TO_PANEL_IMPORTS: dict[str, frozenset[str]] = {}
_EXPECTED_IMPORT_CYCLES: tuple[tuple[str, ...], ...] = ()


def test_prompt_editor_does_not_depend_on_its_panel_host() -> None:
    """Keep every prompt-editor owner independent of its panel host."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
    actual = {
        module_name: frozenset(
            imported_module
            for imported_module in graph[module_name]
            if imported_module.startswith(PANEL_MODULE_PREFIX)
        )
        for module_name in module_paths
        if module_name.startswith(
            "substitute.presentation.editor.prompt_editor",
        )
    }

    assert {
        module_name: imports for module_name, imports in actual.items() if imports
    } == _EXPECTED_PROMPT_TO_PANEL_IMPORTS


def test_prompt_editor_import_cycles_do_not_grow() -> None:
    """Freeze known cycles so each authority transfer can only remove debt."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)

    assert strongly_connected_components(graph) == _EXPECTED_IMPORT_CYCLES


def test_prompt_editor_core_cannot_depend_on_qt_or_outer_presentation() -> None:
    """Keep lower prompt-editor policy independent of Qt and presentation edges."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
    core_prefix = "substitute.presentation.editor.prompt_editor.core"
    graph_violations = {
        module_name: tuple(
            sorted(
                imported_module
                for imported_module in graph[module_name]
                if imported_module.startswith(
                    "substitute.presentation.editor.prompt_editor"
                )
                and not imported_module.startswith(core_prefix)
            )
        )
        for module_name in graph
        if module_name.startswith(f"{core_prefix}.")
    }
    graph_violations = {
        module_name: imports
        for module_name, imports in graph_violations.items()
        if imports
    }
    qt_violations: list[str] = []
    for source_path in (PROMPT_PRESENTATION_ROOT / "core").rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        qt_violations.extend(
            f"{source_path.relative_to(PROJECT_ROOT).as_posix()}:{node.lineno}"
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == "PySide6"
                    or node.module.startswith("PySide6.")
                    or node.module == "qfluentwidgets"
                    or node.module.startswith("qfluentwidgets.")
                )
            )
            or (
                isinstance(node, ast.Import)
                and any(
                    alias.name == "PySide6"
                    or alias.name.startswith("PySide6.")
                    or alias.name == "qfluentwidgets"
                    or alias.name.startswith("qfluentwidgets.")
                    for alias in node.names
                )
            )
        )

    assert graph_violations == {}
    assert qt_violations == []


def test_layout_and_geometry_dependencies_point_toward_immutable_inputs() -> None:
    """Keep layout and geometry independent of mutable presentation hosts."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
    layout_prefix = "substitute.presentation.editor.prompt_editor.layout."
    geometry_prefix = "substitute.presentation.editor.prompt_editor.geometry."
    forbidden_prefixes = (
        "substitute.presentation.editor.panel",
        "substitute.presentation.editor.prompt_editor.composition",
        "substitute.presentation.editor.prompt_editor.features",
        "substitute.presentation.editor.prompt_editor.interactions",
        "substitute.presentation.editor.prompt_editor.overlays",
        "substitute.presentation.editor.prompt_editor.shell",
        "substitute.presentation.editor.prompt_editor.widget",
    )
    forbidden_modules = {
        "substitute.presentation.editor.prompt_editor.projection.layout_engine",
        "substitute.presentation.editor.prompt_editor.projection.painter",
        "substitute.presentation.editor.prompt_editor.projection.surface",
    }
    violations = {
        module_name: tuple(
            sorted(
                imported_module
                for imported_module in graph[module_name]
                if imported_module in forbidden_modules
                or imported_module.startswith(forbidden_prefixes)
                or (
                    module_name.startswith(layout_prefix)
                    and imported_module.startswith(geometry_prefix)
                )
            )
        )
        for module_name in graph
        if module_name.startswith((layout_prefix, geometry_prefix))
    }

    assert {
        module_name: imports for module_name, imports in violations.items() if imports
    } == {}


def test_layout_state_remains_an_atomic_holder_not_an_algorithm_facade() -> None:
    """Keep the layout state owner free of engine, paint, and feature behavior."""

    state_path = PROMPT_PRESENTATION_ROOT / "layout" / "state.py"
    tree = ast.parse(state_path.read_text(encoding="utf-8"))
    state_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PromptLayoutState"
    )
    methods = {
        node.name
        for node in state_class.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    imported_modules = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert methods == {"__init__", "current", "publish", "restore"}
    assert imported_modules == {"__future__", "contracts"}


def test_prepared_frame_publishes_values_without_owning_layout_algorithms() -> None:
    """Keep edit strategy and layout construction out of frame publication."""

    frame_path = PROMPT_PRESENTATION_ROOT / "projection" / "prepared_frame.py"
    source = frame_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    forbidden_imports = {
        "substitute.presentation.editor.prompt_editor.layout.canonical_builder",
        "substitute.presentation.editor.prompt_editor.layout.canonical_engine",
        "substitute.presentation.editor.prompt_editor.layout.hard_line_engine",
        "substitute.presentation.editor.prompt_editor.layout.incremental_engine",
        "substitute.presentation.editor.prompt_editor.layout.same_line_engine",
        "substitute.presentation.editor.prompt_editor.layout.trailing_engine",
    }

    assert imported_modules.isdisjoint(forbidden_imports)
    assert "PromptLayoutRequest" not in source


def test_edit_to_frame_owner_cannot_gain_presentation_value_facades() -> None:
    """Keep the coordinator limited to edit-to-frame transitions."""

    host_path = PROMPT_PRESENTATION_ROOT / "projection" / "edit_to_frame.py"
    tree = ast.parse(host_path.read_text(encoding="utf-8"))
    host_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "PromptLayoutEditToFrameCoordinator"
    )
    forbidden_methods = {
        "projection_document",
        "paint_state",
        "paint_input",
        "document_margin",
        "metrics",
        "line_snapshots",
        "snapshot",
        "width_key",
        "content_size",
        "geometry",
        "output",
        "prepared_frame",
        "set_palette",
        "set_semantic_palette",
        "restore_output",
        "fork_for_incremental_reflow",
    }

    assert not {
        node.name
        for node in host_class.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name in forbidden_methods
    }


def test_layout_edit_mechanisms_remain_focused_and_directional() -> None:
    """Keep edit policy, mutation, remapping, and recovery as separate owners."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
    prefix = "substitute.presentation.editor.prompt_editor.layout."
    forbidden_edges = {
        f"{prefix}tag_keep_policy": {
            f"{prefix}canonical_builder",
            f"{prefix}edit_policy",
            f"{prefix}snapshot_edits",
        },
        f"{prefix}edit_policy": {
            f"{prefix}canonical_builder",
            f"{prefix}canonical_edit_window",
            f"{prefix}line_break_edits",
            f"{prefix}snapshot_edits",
        },
        f"{prefix}canonical_edit_window": {
            f"{prefix}canonical_builder",
            f"{prefix}edit_policy",
            f"{prefix}line_break_edits",
            f"{prefix}snapshot_edits",
        },
        f"{prefix}snapshot_edits": {
            f"{prefix}canonical_builder",
            f"{prefix}canonical_edit_window",
            f"{prefix}edit_policy",
            f"{prefix}line_break_edits",
        },
        f"{prefix}same_line_engine": {
            f"{prefix}hard_line_engine",
            f"{prefix}trailing_engine",
        },
        f"{prefix}hard_line_engine": {
            f"{prefix}same_line_engine",
            f"{prefix}trailing_engine",
        },
        f"{prefix}trailing_engine": {
            f"{prefix}hard_line_engine",
            f"{prefix}same_line_engine",
        },
    }

    assert {
        module_name: tuple(sorted(graph[module_name] & forbidden))
        for module_name, forbidden in forbidden_edges.items()
        if graph[module_name] & forbidden
    } == {}


def test_prepared_paint_owners_remain_focused_and_directional() -> None:
    """Keep paint preparation flowing toward immutable layers and render sinks."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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


def test_reorder_geometry_depends_on_geometry_not_paint_or_layout_hosts() -> None:
    """Keep reorder queries downstream of published geometry alone."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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


def test_reorder_interaction_geometry_has_directional_focused_owners() -> None:
    """Keep target values, queries, publication, and coordination one-way."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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


def test_reorder_preview_visual_publication_flows_outward_to_qt_adapters() -> None:
    """Keep prepared visual ownership below overlay, view, and composition adapters."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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
    drag_proxy_state = f"{prefix}reorder_drag_proxy_state"
    drag_proxy_widget = f"{prefix}overlays.reorder_drag_proxy"
    drag_proxy_visual_owner = f"{prefix}overlays.reorder_drag_proxy_visual_owner"
    held_drag_context = f"{prefix}overlays.reorder_held_drag_context"
    performance_counters = f"{prefix}overlays.reorder_performance_counters"
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
    landing_session = f"{prefix}overlays.reorder_landing_session"
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

    overlay_sources = "\n".join(
        (PROMPT_PRESENTATION_ROOT / "overlays" / module_name).read_text(
            encoding="utf-8"
        )
        for module_name in ("reorder_overlay.py",)
    )
    removed_mirrors = (
        "_preview_visuals_by_index",
        "_preview_chip_geometry_snapshot",
        "_base_drag_chip_geometry_snapshot",
        "_placement_snapshot",
        "_active_placement",
        "_drop_target_visuals",
        "_drop_target_lanes",
        "_preview_geometry_target_identity",
        "_live_raster_entries_render_key",
        "_live_raster_entries_by_index",
        "_preview_raster_entries_render_key",
        "_preview_raster_entries_by_index",
        "_animation_presenter",
        "_held_chip_presenter",
        "_animation_frame_batch_depth",
        "_animation_frame_sync_pending",
        "_animation_visual_owner",
        "_animation_planner",
        "_displacement_session",
        "_animation_generation_id",
        "_animated_pointer_region_indices",
        "_instrumentation_animation_plan_build_count",
        "_drag_proxy",
        "_drag_proxy_host",
        "_drag_proxy_state_factory",
        "_drag_proxy_placement",
        "_last_suppressed_chip_snapshots_by_index",
        "_render_state_sync_revision",
        "_last_drop_commit_visual",
        "_last_drop_commit_geometry",
        "_last_drop_commit_target",
        "_last_drop_commit_placement",
        "_last_drop_commit_segment_index",
        "_last_drop_commit_gesture_id",
        "_last_drop_commit_event_id",
        "_prepared_drag_proxy_segment_index",
        "_drop_target_tracker",
        "_visuals_by_index",
        "_live_visual_snapshots_by_index",
        "_chip_geometry_snapshot",
        "_last_live_visual_geometry_key",
        "_visual_snapshot_cache",
        "_preview_visual_snapshots_by_index",
        "_segments_by_index",
        "_source_identity",
    )
    assert all(f"self.{field} =" not in overlay_sources for field in removed_mirrors)
    assert "self._instrumentation_" not in overlay_sources
    assert "self._pointer_loop_depth" not in overlay_sources
    assert "def _log_interaction_event" not in overlay_sources
    assert "def log_interaction_event" not in overlay_sources
    assert "def _log_interaction_timing" not in overlay_sources
    assert "def _log_reorder_anomaly" not in overlay_sources
    assert "self._drag_handler" not in overlay_sources
    assert "self._commit_handler" not in overlay_sources
    assert "self._cancel_handler" not in overlay_sources
    assert "def _emit_drag_intent" not in overlay_sources
    removed_metric_adapters = (
        "current_instrumentation_work_unit_id",
        "instrumentation_gesture_id",
        "instrumentation_event_id",
        "is_drag_pointer_loop_active",
        "record_preview_scheduler_event",
        "record_preview_sync_decision",
        "record_preview_sync_elapsed",
        "record_render_plan_elapsed",
    )
    assert all(
        f"def {method_name}(" not in overlay_sources
        for method_name in removed_metric_adapters
    )
    removed_keyboard_adapters = (
        "move_active_chip_left",
        "move_active_chip_right",
        "move_active_chip_up",
        "move_active_chip_down",
        "_move_active_chip_by_keyboard",
    )
    reorder_interaction_sources = "\n".join(
        (PROMPT_PRESENTATION_ROOT / "interactions" / filename).read_text(
            encoding="utf-8"
        )
        for filename in ("reorder_interaction.py", "reorder_overlay_session.py")
    )
    assert all(
        f"def {method_name}(" not in overlay_sources
        and f".{method_name}(" not in reorder_interaction_sources
        for method_name in removed_keyboard_adapters
    )
    pointer_source = (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_pointer_regions.py"
    ).read_text(encoding="utf-8")
    assert "class PromptReorderPointerController" not in pointer_source
    assert "self._controller" not in pointer_source
    assert "_drag_intent_rect_from_global_position" not in overlay_sources
    assert "def _update_drop_target_from_global_position" not in overlay_sources
    assert "def _overlay_position_geometry_key" not in overlay_sources
    assert "def reorder_position_geometry_key" not in overlay_sources
    assert "def _emit_preview_layout_changed" not in overlay_sources
    assert "_live_chip_owned_ranges_by_index" not in overlay_sources
    assert "def _update_pointer_region_geometry" not in overlay_sources
    assert "def _update_chip_states" not in overlay_sources
    assert "def _capture_drag_intent_context" not in overlay_sources
    assert "def _drag_intent_source_rect" not in overlay_sources
    assert "def _clear_drag_intent_context" not in overlay_sources
    assert "def _capture_held_shadow_geometry" not in overlay_sources
    assert "self._last_overlay_position_geometry_key" not in overlay_sources
    assert "self._last_overlay_refresh_geometry_key" not in overlay_sources
    assert "self._last_pointer_region_geometry_key" not in overlay_sources
    assert "def _overlay_refresh_geometry_key" not in overlay_sources
    assert "def _pointer_region_geometry_key" not in overlay_sources
    assert "def _sync_pointer_region_geometry_if_needed" not in overlay_sources
    assert "def _autoscroll_context" not in overlay_sources
    assert "def _handle_autoscroll_step" not in overlay_sources
    assert "def _chip_visual_snapshots_from_projection" not in overlay_sources
    assert "def _prepare_preview_visual_snapshots" not in overlay_sources
    assert "def _preview_mode_active" not in overlay_sources
    assert "def _layout_for_painted_preview" not in overlay_sources
    assert "def _landing_visual_request" not in overlay_sources
    assert "def _preview_chip_geometry_for_segment" not in overlay_sources
    assert "def _drop_target_visual_for_target" not in overlay_sources
    assert "def _preview_target_identity_for_active_target" not in overlay_sources
    assert "def _preview_target_identity_matches_active_target" not in overlay_sources
    assert "def _refresh_preview_geometry(" not in overlay_sources
    assert "def _update_preview_layout(" not in overlay_sources
    assert "def _insertion_marker_rect(" not in overlay_sources
    assert "def _placement_owned_landing_geometry(" not in overlay_sources
    assert "def _pending_landing_visual_rect(" not in overlay_sources
    assert "def _pending_shadow_preview_visual(" not in overlay_sources
    assert "def _landing_preview_for_active_target(" not in overlay_sources
    assert "def _sync_reorder_view_state(" not in overlay_sources
    assert "def _publish_reorder_prepared_visual(" not in overlay_sources
    assert "def _prepare_reorder_visual_publication(" not in overlay_sources
    assert "def _chip_styles_by_index(" not in overlay_sources
    assert "def _visible_visual_for_segment(" not in overlay_sources
    assert "def _chip_geometry_for_segment(" not in overlay_sources
    assert "self._prepared_visual_owner" not in overlay_sources
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_landing_visual_owner.py"
    ).exists()
    assert {
        landing_capture,
        landing_diagnostics,
        landing_events,
        landing_state,
    } <= graph[landing_session]
    assert graph[landing_session].isdisjoint(
        {
            landing_visual_owner,
            landing_request_owner,
            overlay,
            factory,
            interaction_geometry,
            view,
        }
    )
    assert {
        landing_diagnostics,
        landing_events,
        landing_paint_cache,
        landing_paint_policy,
        landing_state,
    } <= graph[landing_visual_owner]
    assert landing_capture not in graph[landing_visual_owner]
    assert not (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_interaction.py"
    ).exists()
    visual_cache_source = (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_visual_cache.py"
    ).read_text(encoding="utf-8")
    assert "class PromptReorderVisualSnapshotCache" not in visual_cache_source
    assert "class PromptReorderVisualCacheCounters" not in visual_cache_source
    overlay_ports_source = (
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_ports.py"
    ).read_text(encoding="utf-8")
    assert "class PromptReorderOverlayRenderState" not in overlay_ports_source
    assert "def set_render_state(" not in overlay_ports_source

    obsolete_split_publication_apis = (
        "set_reorder_overlay_suppression_snapshots",
        "set_reorder_surface_chrome",
        "replace_suppression",
        "replace_chrome",
        "clear_suppression",
    )
    for source_path in (
        PROMPT_PRESENTATION_ROOT / "projection" / "surface.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "reorder_surface_visual_state.py",
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay_ports.py",
        PROMPT_PRESENTATION_ROOT / "shell" / "widget.py",
        PROMPT_PRESENTATION_ROOT / "widget.py",
        PROMPT_PRESENTATION_ROOT / "widget.pyi",
    ):
        source = source_path.read_text(encoding="utf-8")
        assert not any(
            obsolete_api in source for obsolete_api in obsolete_split_publication_apis
        )


def test_reorder_preview_publications_flow_through_typed_composition() -> None:
    """Keep preview facts coherent and below controller/composition adapters."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
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


def test_region_chrome_consumes_immutable_output_without_a_host_protocol() -> None:
    """Keep separator preparation keyed by layout values, not broad hosts."""

    source_path = PROMPT_PRESENTATION_ROOT / "projection" / "region_chrome.py"
    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
    module_name = (
        "substitute.presentation.editor.prompt_editor.projection.region_chrome"
    )

    assert (
        "substitute.presentation.editor.prompt_editor.projection.layout_engine"
        not in graph[module_name]
    )
    assert _protocol_class_count(source_path) == 0


def test_projection_values_have_focused_qt_free_core_owners() -> None:
    """Keep immutable projection values below layout without a compatibility barrel."""

    projection_root = PROMPT_PRESENTATION_ROOT / "core" / "projection"
    assert _immediate_python_files(projection_root) == {
        "__init__.py",
        "caret.py",
        "document.py",
        "mapping.py",
        "runs.py",
        "tokens.py",
    }
    assert not (PROMPT_PRESENTATION_ROOT / "projection" / "model.py").exists()

    package_tree = ast.parse(
        (projection_root / "__init__.py").read_text(encoding="utf-8")
    )
    assert not any(
        isinstance(node, ast.Import | ast.ImportFrom)
        for node in package_tree.body
        if not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    )


def test_immutable_geometry_owners_do_not_depend_on_mutable_hosts() -> None:
    """Keep focused geometry owners below layout, paint, and surface hosts."""

    module_paths = python_module_paths(PROJECT_ROOT, PROMPT_ARCHITECTURE_ROOTS)
    graph = internal_import_graph(module_paths)
    geometry_prefix = "substitute.presentation.editor.prompt_editor.geometry."
    forbidden_hosts = {
        "substitute.presentation.editor.prompt_editor.projection.layout_engine",
        "substitute.presentation.editor.prompt_editor.projection.painter",
        "substitute.presentation.editor.prompt_editor.projection.surface",
    }
    violations = {
        module_name: tuple(sorted(graph[module_name] & forbidden_hosts))
        for module_name in graph
        if module_name.startswith(geometry_prefix)
        and graph[module_name] & forbidden_hosts
    }

    assert violations == {}


def test_geometry_aggregate_cannot_become_a_forwarding_facade() -> None:
    """Keep publication as composition instead of a list of delegated queries."""

    aggregate_path = PROMPT_PRESENTATION_ROOT / "geometry" / "aggregate.py"
    tree = ast.parse(aggregate_path.read_text(encoding="utf-8"))
    aggregate_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PromptProjectionGeometry"
    )
    methods = {
        node.name
        for node in aggregate_class.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    public_fields = {
        node.target.id
        for node in aggregate_class.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and not node.target.id.startswith("_")
    }

    assert methods == {"__post_init__"}
    assert public_fields == {
        "input",
        "caret",
        "hit_testing",
        "selection",
        "source_lines",
        "tokens",
        "viewport",
    }


def test_pure_prompt_owners_use_cohesive_subpackages() -> None:
    """Keep pure prompt owners out of flat mixed-responsibility packages."""

    assert _immediate_python_files(PROMPT_DOMAIN_ROOT) == {"__init__.py"}
    assert _immediate_python_files(PROMPT_APPLICATION_ROOT) == {"__init__.py"}
    assert _immediate_package_names(PROMPT_DOMAIN_ROOT) == _TARGET_DOMAIN_PACKAGES
    assert (
        _immediate_package_names(PROMPT_APPLICATION_ROOT)
        == _TARGET_APPLICATION_PACKAGES
    )


def test_prompt_internal_imports_bypass_package_barrels() -> None:
    """Require internal consumers to import the authoritative owner directly."""

    forbidden_modules = {
        "substitute.application.prompt_editor",
        "substitute.domain.prompt",
    }
    violations: list[str] = []
    source_paths = (
        *(PROJECT_ROOT / "substitute").rglob("*.py"),
        *(PROJECT_ROOT / "substitute").rglob("*.pyi"),
    )
    for source_path in source_paths:
        if source_path.name == "__init__.py":
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in forbidden_modules:
                relative_path = source_path.relative_to(PROJECT_ROOT).as_posix()
                violations.append(f"{relative_path}:{node.lineno}:{node.module}")

    assert violations == []


def test_prompt_package_roots_do_not_dispatch_lazy_exports() -> None:
    """Keep package roots inert and free of service-locator export registries."""

    violations: dict[str, list[str]] = {}
    for package_root in (PROMPT_DOMAIN_ROOT, PROMPT_APPLICATION_ROOT):
        init_path = package_root / "__init__.py"
        tree = ast.parse(init_path.read_text(encoding="utf-8"))
        forbidden_nodes = [
            f"{type(node).__name__}:{getattr(node, 'lineno', 0)}"
            for node in tree.body
            if isinstance(
                node,
                ast.Assign
                | ast.AnnAssign
                | ast.FunctionDef
                | ast.AsyncFunctionDef
                | ast.ClassDef,
            )
        ]
        forbidden_imports = [
            f"{type(node).__name__}:{getattr(node, 'lineno', 0)}"
            for node in tree.body
            if isinstance(node, ast.Import)
            or (isinstance(node, ast.ImportFrom) and node.module != "__future__")
        ]
        if forbidden_nodes or forbidden_imports:
            violations[init_path.relative_to(PROJECT_ROOT).as_posix()] = [
                *forbidden_nodes,
                *forbidden_imports,
            ]

    assert violations == {}


def test_lora_catalog_values_do_not_depend_on_catalog_algorithms() -> None:
    """Keep immutable LoRA values below catalog construction and ranking."""

    models_path = PROMPT_APPLICATION_ROOT / "lora" / "catalog_models.py"
    tree = ast.parse(models_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not {
        module_name
        for module_name in imported_modules
        if module_name.startswith("substitute.application.prompt_editor.lora.")
    }


def test_revision_owner_replaces_obsolete_prompt_state_mirrors() -> None:
    """Prevent deleted raw revision and derived-state authorities from returning."""

    forbidden_fragments = {
        PROMPT_PRESENTATION_ROOT / "projection" / "surface.py": (
            "self._source_revision",
            "self._projection_document",
            "self._document_view",
            "self._render_plan",
        ),
        PROMPT_PRESENTATION_ROOT / "projection" / "diagnostic_layer_owner.py": (
            "self._layout_revision",
            "advance_layout_revision",
        ),
        PROMPT_PRESENTATION_ROOT / "async_work" / "execution.py": (
            "source_revision: int | None",
            "source_length: int | None",
        ),
        PROMPT_PRESENTATION_ROOT / "projection" / "transient_edit_overlays.py": (
            "source_revision: int",
            "committed_source_revision",
        ),
        PROMPT_PRESENTATION_ROOT / "overlays" / "reorder_overlay.py": (
            "self._source_revision",
            "source_revision: int | None",
        ),
        PROMPT_PRESENTATION_ROOT / "core" / "state" / "editor_state.py": (
            "_require_source_text(",
            "_require_matching_source_text(",
            "derived.source_text != ",
            "downstream.source_text != ",
        ),
        PROMPT_PRESENTATION_ROOT / "syntax_renderers.py": ("self._state.revisions",),
        PROMPT_PRESENTATION_ROOT / "core" / "editing" / "source_commands.py": (
            "self._source_buffer.source_text =",
            "self._source_buffer.source_revision +=",
            "self._source_buffer.parenthesis_intents =",
            "self._source_buffer.generated_emphases =",
        ),
        PROJECT_ROOT / "tests" / "real_shell_prompt_editor_harness.py": (
            'getattr(surface, "_source_revision"',
            'getattr(surface, "_projection_document"',
            'getattr(surface, "_document_view"',
            'getattr(surface, "_render_plan"',
        ),
    }
    violations: list[str] = []
    for source_path, fragments in forbidden_fragments.items():
        source = source_path.read_text(encoding="utf-8")
        violations.extend(
            f"{source_path.relative_to(PROJECT_ROOT).as_posix()}:{fragment}"
            for fragment in fragments
            if fragment in source
        )

    assert violations == []


def test_prompt_editor_private_and_protocol_debt_does_not_grow() -> None:
    """Freeze broad protocols, casts, and private-access exemptions for removal."""

    presentation_sources = tuple(PROMPT_PRESENTATION_ROOT.rglob("*.py"))
    prompt_test_sources = tuple(
        source_path
        for source_path in PROJECT_ROOT.glob("tests/*prompt*.py")
        if source_path != Path(__file__)
    )
    protocol_count = sum(
        _protocol_class_count(source_path) for source_path in presentation_sources
    )
    cast_count = sum(
        source_path.read_text(encoding="utf-8").count("cast(")
        for source_path in presentation_sources
    )
    production_private_exemptions = sum(
        source_path.read_text(encoding="utf-8").count("SLF001")
        for source_path in presentation_sources
    )
    test_private_exemptions = sum(
        source_path.read_text(encoding="utf-8").count("SLF001")
        for source_path in prompt_test_sources
    )

    actual = {
        "protocols": protocol_count,
        "casts": cast_count,
        "production_private_exemptions": production_private_exemptions,
        "test_private_exemptions": test_private_exemptions,
    }
    maximums = {
        "protocols": 199,
        "casts": 194,
        "production_private_exemptions": 0,
        "test_private_exemptions": 292,
    }

    assert {
        name: {"actual": actual[name], "maximum": maximum}
        for name, maximum in maximums.items()
        if actual[name] > maximum
    } == {}


def test_autocomplete_presentation_lifecycle_is_the_only_panel_and_preview_owner() -> (
    None
):
    """Keep the Qt coordinator free of session and passive presentation state."""

    controller_path = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "autocomplete_controller.py"
    )
    lifecycle_path = (
        PROMPT_PRESENTATION_ROOT
        / "interactions"
        / "autocomplete_presentation_lifecycle.py"
    )
    publication_path = (
        PROMPT_PRESENTATION_ROOT
        / "interactions"
        / "autocomplete_session_publication.py"
    )
    controller_source = controller_path.read_text(encoding="utf-8")
    lifecycle_source = lifecycle_path.read_text(encoding="utf-8")
    publication_source = publication_path.read_text(encoding="utf-8")

    assert "self._presenter" not in controller_source
    assert "self._ghost_text_publisher" not in controller_source
    assert "self._autocomplete_ghost_text_enabled" not in controller_source
    assert "def _present_active_surfaces(" not in controller_source
    assert "def _publish_inline_completion_preview(" not in controller_source
    assert "def _clear_inline_completion_preview(" not in controller_source
    assert "self._sessions" not in controller_source
    assert "self._presentation" not in controller_source
    assert "PromptAutocompletePresentationLifecycle" not in controller_source
    assert "class PromptAutocompletePresentationLifecycle" in lifecycle_source
    assert "application.prompt_editor.autocomplete" not in lifecycle_source
    assert "PromptAutocompleteResultController" not in lifecycle_source
    assert "class PromptAutocompleteSessionPublication" in publication_source
    assert "PromptAutocompletePresentationLifecycle" in publication_source


def test_autocomplete_query_result_lifecycle_is_the_only_query_cache_owner() -> None:
    """Keep query freshness and result work below the Qt interaction coordinator."""

    controller_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "autocomplete_controller.py"
    ).read_text(encoding="utf-8")
    lifecycle_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "autocomplete_query_result_lifecycle.py"
    ).read_text(encoding="utf-8")

    forbidden_controller_fragments = (
        "PromptAutocompleteResultController",
        "PromptAutocompleteSceneContextController",
        "PromptAutocompleteScheduledLoraContextController",
        "PromptAutocompleteQueryRefreshController",
        "def refresh_for_query(",
        "def refresh_for_scene_query(",
        "def refresh_for_wildcard_query(",
        "def refresh_for_lora_query(",
        "current_query_identity",
        "refresh_current_query",
    )
    assert not any(
        fragment in controller_source for fragment in forbidden_controller_fragments
    )
    assert "class PromptAutocompleteQueryResultLifecycle" in lifecycle_source
    assert "PySide6" not in lifecycle_source
    assert "PromptAutocompletePresentationLifecycle" not in lifecycle_source
    assert "publication=session_publication" in (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")


def test_autocomplete_acceptance_lifecycle_owns_session_command_transactions() -> None:
    """Keep command acceptance and mandatory session closure outside Qt input routing."""

    controller_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "autocomplete_controller.py"
    ).read_text(encoding="utf-8")
    lifecycle_source = (
        PROMPT_PRESENTATION_ROOT
        / "interactions"
        / "autocomplete_acceptance_lifecycle.py"
    ).read_text(encoding="utf-8")

    assert "PromptAutocompleteAcceptanceController" not in controller_source
    assert "self._acceptance_controller" not in controller_source
    assert "class PromptAutocompleteAcceptanceLifecycle" in lifecycle_source
    assert "PromptAutocompleteAcceptanceController" in lifecycle_source
    assert "PromptAutocompleteSessionPublication" in lifecycle_source


def test_autocomplete_input_adapter_stays_at_the_qt_boundary() -> None:
    """Prevent the Qt adapter from reclaiming query, session, or command ownership."""

    adapter_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "autocomplete_controller.py"
    ).read_text(encoding="utf-8")

    assert "class PromptAutocompleteInputAdapter" in adapter_source
    assert "class PromptAutocompleteCoordinator" not in adapter_source
    assert "PromptAutocompleteQueryResultLifecycle" not in adapter_source
    assert "PromptAutocompleteResultController" not in adapter_source
    assert "PromptAutocompleteAcceptanceController" not in adapter_source
    assert "self._sessions" not in adapter_source


def test_autocomplete_test_stack_exposes_real_owners_without_proxy_routing() -> None:
    """Keep test composition explicit instead of recreating autocomplete ownership."""

    helper_source = (
        PROJECT_ROOT / "tests" / "prompt_autocomplete_test_helpers.py"
    ).read_text(encoding="utf-8")

    assert "class PromptAutocompleteTestStack" in helper_source
    assert "def build_test_autocomplete_stack(" in helper_source
    assert "PromptAutocompleteInputAdapter" in helper_source
    assert "PromptAutocompleteQueryResultLifecycle" in helper_source
    assert "PromptAutocompleteSessionController" in helper_source
    forbidden_fragments = (
        "PromptAutocompleteLifecycleTestOwner",
        "PromptAutocompleteQueryRefreshTestHarness",
        "build_test_autocomplete_coordinator",
        "def __getattr__(",
        "def refresh_for_query(",
        "def refresh_for_wildcard_query(",
        "def refresh_for_scene_query(",
        "def refresh_for_lora_query(",
        'name == "_sessions"',
    )
    assert not any(fragment in helper_source for fragment in forbidden_fragments)


def test_diagnostics_provider_and_refresh_owners_stay_outside_feature_controller() -> (
    None
):
    """Keep diagnostics lifecycle below its sole presentation/action owner."""

    controller_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_controller.py"
    ).read_text(encoding="utf-8")
    provider_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_provider_lifecycle.py"
    ).read_text(encoding="utf-8")
    refresh_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_refresh_lifecycle.py"
    ).read_text(encoding="utf-8")
    presentation_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_presentation.py"
    ).read_text(encoding="utf-8")
    context_menu_snapshot_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_snapshot_assembly.py"
    ).read_text(encoding="utf-8")
    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")

    assert "class PromptDiagnosticsProviderLifecycle" in provider_source
    assert "class PromptDiagnosticsRefreshLifecycle" in refresh_source
    assert "class PromptDiagnosticsPresentation" in presentation_source
    assert "PromptDiagnosticsProviderLifecycle" in controller_source
    assert "PromptDiagnosticsRefreshLifecycle" in controller_source
    assert "PromptDiagnosticsPresentation" in controller_source
    forbidden_controller_fragments = (
        "def _build_service(",
        "def _scoped_provider(",
        "def _handle_async_outcome(",
        "def _async_identity(",
        "self._request_id",
        "self._stale_guard",
        "self._spellcheck_provider",
        "self._service",
        "self._snapshot",
        "self._published_snapshot",
        "self._visible_diagnostics",
        "self._ignored_diagnostic_ids",
        "def actions_for_diagnostic(",
        "def prepared_menu_actions_for_source_position(",
        "def publish_diagnostics_result(",
        "def publish_empty_diagnostics(",
        "def publish_diagnostics_failure(",
    )
    assert not any(
        fragment in controller_source for fragment in forbidden_controller_fragments
    )
    assert "PySide6" not in provider_source
    assert "PySide6" not in refresh_source
    assert "PySide6" not in presentation_source
    assert "from .diagnostics_controller import" not in context_menu_snapshot_source
    assert "PromptContextMenuDiagnosticsPort" in context_menu_snapshot_source
    assert (
        "diagnostics=self._diagnostics_feature_controller.presentation" in widget_source
    )


def test_weight_interaction_stays_below_general_interaction_routing() -> None:
    """Keep emphasis and exact-weight state out of generic input orchestration."""

    controller_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "controller.py"
    ).read_text(encoding="utf-8")
    weight_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "weight_interaction.py"
    ).read_text(encoding="utf-8")
    keymap_source = (PROMPT_PRESENTATION_ROOT / "interactions" / "keymap.py").read_text(
        encoding="utf-8"
    )
    mouse_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "mouse_selection_controller.py"
    ).read_text(encoding="utf-8")
    factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")
    signal_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "signal_bindings.py"
    ).read_text(encoding="utf-8")

    forbidden_controller_fragments = (
        "PromptEmphasisController",
        "PromptExactWeightController",
        "PromptWeightActionRequest",
        "def modify_emphasis(",
        "def apply_syntax_action(",
        "def apply_overlay_syntax_action(",
        "def apply_token_weight_step_intent(",
        "def apply_token_weight_wheel_step_intent(",
        "def begin_exact_weight_edit(",
        "def start_exact_weight_edit(",
        "def handle_exact_weight_key_press(",
        "def clear_keyboard_emphasis_session(",
        "def clear_mouse_emphasis_session(",
        "def _apply_weight_command_result(",
    )
    assert not any(
        fragment in controller_source for fragment in forbidden_controller_fragments
    )
    assert "class PromptWeightInteraction" in weight_source
    assert "PromptEmphasisController" in weight_source
    assert "PromptExactWeightController" in weight_source
    assert "class PromptKeymapWeightPort" in keymap_source
    assert "self._weights.handle_exact_weight_key_press(event)" in keymap_source
    assert "class PromptMouseSelectionWeightPort" in mouse_source
    assert "self._weights.apply_syntax_action(syntax_action)" in mouse_source
    assert "weight_interaction = PromptWeightInteraction(" in factory_source
    assert "exact_edit_host=weight_interaction" in factory_source
    assert "weight_interaction.modify_emphasis" in signal_source
    assert "weight_interaction.apply_token_weight_step_intent" in signal_source


def test_lora_metadata_refresh_and_presentation_owners_stay_separate() -> None:
    """Keep dispatcher lifecycle and prepared LoRA metadata in direct owners."""

    deleted_controller = (
        PROMPT_PRESENTATION_ROOT / "features" / "lora_metadata_controller.py"
    )
    presentation_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "lora_metadata_presentation.py"
    ).read_text(encoding="utf-8")
    refresh_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "lora_metadata_refresh_lifecycle.py"
    ).read_text(encoding="utf-8")
    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")

    assert not deleted_controller.exists()
    assert "class PromptLoraMetadataPresentation" in presentation_source
    assert "PromptLoraPickerSnapshotController" in presentation_source
    assert "PromptLoraContextActionController" in presentation_source
    assert "QtPromptEditorMainThreadDispatcher" not in presentation_source
    assert "class PromptLoraMetadataRefreshLifecycle" in refresh_source
    assert "self._dirty" in refresh_source
    assert "self._refresh_pending" in refresh_source
    assert "self._catchup_pending" in refresh_source
    assert "PromptLoraPickerSnapshotController" not in refresh_source
    assert "PySide6" not in refresh_source
    assert "self._lora_metadata_presentation" in widget_source
    assert "self._lora_metadata_refresh" in widget_source
    assert "_lora_metadata_feature_controller" not in widget_source
    assert "lora_metadata: PromptLoraMetadataPresentation" in factory_source


def test_wildcard_diagnostics_and_autocomplete_owners_stay_separate() -> None:
    """Keep wildcard diagnostics and asynchronous autocomplete in direct owners."""

    deleted_controller = (
        PROMPT_PRESENTATION_ROOT / "features" / "wildcard_controller.py"
    )
    autocomplete_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "wildcard_autocomplete.py"
    ).read_text(encoding="utf-8")
    cache_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "wildcard_autocomplete_cache.py"
    ).read_text(encoding="utf-8")
    diagnostics_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "wildcard_diagnostics.py"
    ).read_text(encoding="utf-8")
    factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")
    diagnostics_lifecycle_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_provider_lifecycle.py"
    ).read_text(encoding="utf-8")

    assert not deleted_controller.exists()
    assert "class PromptWildcardAutocompletePresentation" in autocomplete_source
    assert "PromptWildcardAutocompleteCache" in autocomplete_source
    assert "PromptWildcardDiagnosticProvider" not in autocomplete_source
    assert "actions_for_diagnostic" not in autocomplete_source
    assert "PySide6" not in autocomplete_source
    assert "class PromptWildcardAutocompleteCache" in cache_source
    assert "OrderedDict" in cache_source
    assert "PromptEditorRequestChannel" not in cache_source
    assert "class PromptWildcardDiagnosticsPresentation" in diagnostics_source
    assert "PromptWildcardDiagnosticProvider" in diagnostics_source
    assert "actions_for_diagnostic" in diagnostics_source
    assert "PromptEditorRequestChannel" not in diagnostics_source
    assert "PromptWildcardDiagnosticProviderSource" in diagnostics_lifecycle_source
    assert "PromptWildcardFeatureController" not in diagnostics_lifecycle_source
    assert "wildcard_autocomplete_presentation" in factory_source
    assert "wildcard_diagnostics_presentation" in factory_source


def test_context_menu_preparation_stays_out_of_snapshot_assembly() -> None:
    """Keep explicit feature prewarm work outside passive context-menu reads."""

    preparation_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_preparation.py"
    ).read_text(encoding="utf-8")
    models_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_models.py"
    ).read_text(encoding="utf-8")
    ports_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_ports.py"
    ).read_text(encoding="utf-8")
    snapshot_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_snapshot_assembly.py"
    ).read_text(encoding="utf-8")
    presenter_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "prompt_menu_presenter.py"
    ).read_text(encoding="utf-8")
    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")
    deleted_action_adapter = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_actions.py"
    )
    deleted_mixed_snapshot_module = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_snapshot.py"
    )

    assert "class PromptContextMenuPreparationLifecycle" in preparation_source
    assert "class PromptContextMenuSnapshotRequest" in models_source
    assert "class PromptContextMenuSnapshot" in models_source
    assert "Protocol" not in models_source
    assert "class PromptContextMenuDiagnosticsPort" in ports_source
    assert "class PromptContextMenuDanbooruPort" in ports_source
    assert "dataclass" not in ports_source
    assert "class PromptContextMenuSnapshotAssembler" in snapshot_source
    assert "class PromptContextMenuDiagnosticsPort" not in snapshot_source
    assert "class PromptContextMenuSnapshotRequest" not in snapshot_source
    assert "prepare_selection" in preparation_source
    assert "prepare_opening" in preparation_source
    assert "PySide6" not in preparation_source
    assert "def prepare_menu_selection(" not in snapshot_source
    assert "def prepare_menu_opening(" not in snapshot_source
    assert not deleted_action_adapter.exists()
    assert not deleted_mixed_snapshot_module.exists()
    assert "class PromptContextMenuSnapshotReader" in presenter_source
    assert "class PromptContextMenuPreparationPort" in presenter_source
    assert "self._preparation.prepare_selection(" in presenter_source
    assert "self._preparation.prepare_opening(" in presenter_source
    assert "self._snapshot_reader.snapshot_for_menu(" in presenter_source
    assert "self._context_menu_snapshot_assembler" in widget_source
    assert "self._context_menu_preparation" in widget_source
    assert "snapshot_reader: PromptContextMenuSnapshotAssembler" in factory_source
    assert "preparation: PromptContextMenuPreparationLifecycle" in factory_source


def test_deleted_editing_graph_cannot_return() -> None:
    """Keep the obsolete mutation graph and package-root barrel deleted."""

    deleted_files = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "command_adapter.py",
        PROMPT_PRESENTATION_ROOT / "interactions" / "edit_command_router.py",
    )
    assert all(not path.exists() for path in deleted_files)
    editing_session_root = PROMPT_PRESENTATION_ROOT / "editing_session"
    assert not tuple(editing_session_root.glob("*.py"))
    assert not tuple(editing_session_root.glob("*.pyi"))

    forbidden_fragments = (
        "PromptEditController",
        "PromptEditCommandRouter",
        "PromptEditorCommandAdapter",
        "PromptProjectionSourceChangeApplication",
        "PromptProjectionRestoreApplication",
        "PromptEditingSessionSourceChange",
        "apply_source_change_application",
        "apply_restore_application",
        "attach_runtime_mutation_actions",
    )
    source_paths = (
        *(PROMPT_PRESENTATION_ROOT.rglob("*.py")),
        *(PROMPT_PRESENTATION_ROOT.rglob("*.pyi")),
    )
    violations = {
        fragment: tuple(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in source_paths
            if fragment in path.read_text(encoding="utf-8")
        )
        for fragment in forbidden_fragments
    }
    assert {fragment: paths for fragment, paths in violations.items() if paths} == {}

    command_root = PROMPT_PRESENTATION_ROOT / "commands" / "__init__.py"
    tree = ast.parse(command_root.read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)


def test_deleted_layout_transition_host_cannot_return() -> None:
    """Keep the replaced layout-host module out of the projection graph."""

    deleted_files = (
        PROMPT_PRESENTATION_ROOT / "projection" / "layout_engine.py",
        PROMPT_PRESENTATION_ROOT / "layout" / "edit_algorithms.py",
        PROMPT_PRESENTATION_ROOT / "layout" / "incremental_engine.py",
    )

    assert all(not path.exists() for path in deleted_files)


def test_deleted_geometry_graph_cannot_return() -> None:
    """Keep replaced geometry modules and the forwarding facade deleted."""

    deleted_files = (
        PROMPT_PRESENTATION_ROOT / "projection" / "hit_testing.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "selection_geometry.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "snapshot.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "source_line_geometry.py",
        PROMPT_PRESENTATION_ROOT / "projection" / "visible_line_range.py",
        PROMPT_PRESENTATION_ROOT / "geometry.py",
    )
    deleted_source_roots = (
        PROMPT_PRESENTATION_ROOT / "core" / "geometry",
        PROMPT_PRESENTATION_ROOT / "core" / "layout",
    )

    assert all(not path.exists() for path in deleted_files)
    assert all(
        not tuple(path.glob("*.py")) and not tuple(path.glob("*.pyi"))
        for path in deleted_source_roots
    )


def _protocol_class_count(source_path: Path) -> int:
    """Return Protocol-derived class count in one source module."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    return sum(
        isinstance(node, ast.ClassDef)
        and any(
            (isinstance(base, ast.Name) and base.id == "Protocol")
            or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
            for base in node.bases
        )
        for node in ast.walk(tree)
    )


def _immediate_python_files(package_root: Path) -> set[str]:
    """Return Python filenames placed directly in one package."""

    return {path.name for path in package_root.glob("*.py")}


def _immediate_package_names(package_root: Path) -> frozenset[str]:
    """Return immediate child packages beneath one package root."""

    return frozenset(
        path.name
        for path in package_root.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
