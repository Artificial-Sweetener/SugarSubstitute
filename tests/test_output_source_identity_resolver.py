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

"""Tests for Comfy output-source identity resolution."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceGraph,
    build_output_source_graph,
    collect_cube_output_node_ids,
    cube_number_for_source_identity,
    output_cube_numbers_by_alias,
    output_source_identity_for_node,
    resolve_output_source_identity_for_node,
    typed_prompt_nodes,
)


def test_resolver_module_keeps_infrastructure_boundary() -> None:
    """Output-source resolution must not import Qt, presentation, or listener code."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "output_source_identity_resolver.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
        "substitute.infrastructure.comfy.websocket_listener",
    }

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert not {
        module
        for module in imported_modules
        for forbidden in forbidden_roots
        if module == forbidden or module.startswith(f"{forbidden}.")
    }


def test_build_output_source_graph_prefers_nearest_downstream_output() -> None:
    """Nodes shared by multiple outputs should map to the nearest cube output."""

    workflow_payload = {
        "sampler": {"class_type": "KSampler"},
        "near-output": {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"value": ["sampler", 0]},
        },
        "upscale": {
            "class_type": "KSampler",
            "inputs": {"image": ["sampler", 0]},
        },
        "far-output": {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"value": ["upscale", 0]},
        },
    }

    graph = build_output_source_graph(
        workflow_payload,
        collect_cube_output_node_ids(workflow_payload),
    )

    assert graph.node_to_cube_output_node_id["sampler"] == "near-output"
    assert graph.node_to_cube_output_node_id["upscale"] == "far-output"


def test_build_output_source_graph_records_ambiguous_nearest_outputs() -> None:
    """Equidistant output mappings should be exposed as ambiguous."""

    workflow_payload = {
        "shared": {"class_type": "KSampler"},
        "output-b": {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"value": ["shared", 0]},
        },
        "output-a": {
            "class_type": "SugarCubes.CubeOutput",
            "inputs": {"value": ["shared", 0]},
        },
    }

    graph = build_output_source_graph(
        workflow_payload,
        collect_cube_output_node_ids(workflow_payload),
    )

    assert "shared" not in graph.node_to_cube_output_node_id
    assert graph.ambiguous_cube_output_node_ids_by_node["shared"] == (
        "output-a",
        "output-b",
    )


def test_resolve_output_source_identity_reports_ambiguous_mapping_once() -> None:
    """Repeated ambiguous mappings should downgrade from warning to debug."""

    workflow_payload: dict[str, object] = {
        "shared": {"_meta": {"title": "Shared.KSampler"}}
    }
    graph = OutputSourceGraph(
        node_to_cube_output_node_id={},
        ambiguous_cube_output_node_ids_by_node={"shared": ("output-a", "output-b")},
    )
    warning_keys: set[tuple[str, tuple[str, ...]]] = set()

    first = resolve_output_source_identity_for_node(
        "shared",
        workflow_id="wf-1",
        prompt_id="pid-1",
        workflow_payload=workflow_payload,
        output_source_graph=graph,
        cube_output_node_ids={"output-a", "output-b"},
        ambiguous_warning_keys=warning_keys,
    )
    second = resolve_output_source_identity_for_node(
        "shared",
        workflow_id="wf-1",
        prompt_id="pid-1",
        workflow_payload=workflow_payload,
        output_source_graph=graph,
        cube_output_node_ids={"output-a", "output-b"},
        ambiguous_warning_keys=warning_keys,
    )

    assert first.source_identity.source_key == "wf-1:shared"
    assert first.source_identity.source_label == "Shared"
    assert first.diagnostic is not None
    assert first.diagnostic.level == "warning"
    assert second.diagnostic is not None
    assert second.diagnostic.level == "debug"


def test_resolve_output_source_identity_reports_missing_mapping() -> None:
    """Unmapped nodes should fall back to node-local identity with context."""

    result = resolve_output_source_identity_for_node(
        "lonely",
        workflow_id="wf-1",
        prompt_id="pid-1",
        workflow_payload={"lonely": {"_meta": {"title": "Lonely.KSampler"}}},
        output_source_graph=OutputSourceGraph(
            node_to_cube_output_node_id={},
            ambiguous_cube_output_node_ids_by_node={},
        ),
        cube_output_node_ids={"output-b", "output-a"},
        ambiguous_warning_keys=set(),
    )

    assert result.source_identity.source_key == "wf-1:lonely"
    assert result.source_identity.source_label == "Lonely"
    assert result.diagnostic is not None
    assert result.diagnostic.level == "warning"
    assert result.diagnostic.fields["cube_output_node_ids"] == (
        "output-a",
        "output-b",
    )


def test_output_cube_numbers_match_alias_body_and_node_id() -> None:
    """Cube numbering should preserve legacy alias and node-id lookup keys."""

    workflow_payload: dict[str, object] = {
        "output-1": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "SDXL/Text to Image.CubeOutput"},
        },
        "output-2": {
            "class_type": "SugarCubes.CubeOutput",
            "_meta": {"title": "Upscale.CubeOutput"},
        },
    }

    numbers = output_cube_numbers_by_alias(workflow_payload)
    identity = output_source_identity_for_node(
        "output-1",
        workflow_id="wf-1",
        workflow_payload=workflow_payload,
    )

    assert numbers["output-1"] == 1
    assert numbers["Text to Image"] == 1
    assert numbers["Upscale"] == 2
    assert cube_number_for_source_identity(identity, numbers) == 1


def test_typed_prompt_nodes_unwraps_comfy_prompt_payload() -> None:
    """Wrapped Sugar payloads should expose executable prompt node mappings."""

    assert typed_prompt_nodes(
        {
            "prompt": {"1": {"class_type": "KSampler"}, "bad": "ignored"},
            "workflow": {"nodes": []},
        }
    ) == {"1": {"class_type": "KSampler"}}
