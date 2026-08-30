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


def test_layout_and_geometry_dependencies_point_toward_immutable_inputs() -> None:
    """Keep layout and geometry independent of mutable presentation hosts."""

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
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

    architecture = prompt_editor_architecture_inventory()
    graph = architecture.graph
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
