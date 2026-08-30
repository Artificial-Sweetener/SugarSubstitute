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

"""Verify literal preservation and CSV wildcard normalization."""

from __future__ import annotations

from pathlib import Path

from substitute.application.recipes.workflow_export_service import (
    normalize_csv_wildcard_nodes,
)
from tests.application.recipes.workflow_export.support import build_service


def test_compile_workflow_payload_preserves_backslashes_in_node_string_literals() -> (
    None
):
    """Preserve literal backslashes in checkpoint names and node metadata."""
    service, _repository, _compiler = build_service(
        {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": r"Flux\flux1-dev-bnb-nf4.safetensors"},
                "_meta": {
                    "title": "txt.checkpoint",
                    "substitute": {
                        "cube_alias": "txt",
                        "node_name": "checkpoint",
                    },
                },
            }
        }
    )

    workflow_payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as txt",
        output_dir=Path("projects"),
    )

    checkpoint_nodes = [
        node
        for node in workflow_payload.values()
        if isinstance(node, dict) and node.get("class_type") == "CheckpointLoaderSimple"
    ]
    assert checkpoint_nodes
    assert checkpoint_nodes[0]["inputs"]["ckpt_name"] == (
        r"Flux\flux1-dev-bnb-nf4.safetensors"
    )
    metadata = checkpoint_nodes[0].get("_meta")
    assert isinstance(metadata, dict)
    assert metadata["title"] == "txt.checkpoint"
    assert metadata["substitute"] == {
        "cube_alias": "txt",
        "node_name": "checkpoint",
    }


def test_compile_workflow_payload_preserves_escaped_prompt_parentheses() -> None:
    """Preserve escaped literal parentheses in prompt node inputs."""
    service, _repository, _compiler = build_service(
        {
            "1": {
                "class_type": "String",
                "inputs": {"prompt_template": r"painting \(medium\)"},
            }
        }
    )

    workflow_payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as txt",
        output_dir=Path("projects"),
    )

    prompt_nodes = [
        node
        for node in workflow_payload.values()
        if isinstance(node, dict)
        and isinstance(node.get("inputs"), dict)
        and node["inputs"].get("prompt_template") == r"painting \(medium\)"
    ]
    assert prompt_nodes
    assert prompt_nodes[0]["inputs"]["prompt_template"] == r"painting \(medium\)"


def test_normalize_csv_wildcard_nodes_replaces_backend_node_with_string() -> None:
    """Remove the backend CSV wildcard dependency from executable payloads."""
    workflow_nodes: dict[str, object] = {
        "1": {
            "class_type": "CSVWildcardNode",
            "inputs": {"prompt_template": "A wolf", "seed": 999},
        },
        "2": {"class_type": "KSampler", "inputs": {}},
    }

    normalize_csv_wildcard_nodes(workflow_nodes)

    assert workflow_nodes["1"] == {
        "class_type": "String",
        "inputs": {"value": "A wolf"},
    }
    assert workflow_nodes["2"] == {"class_type": "KSampler", "inputs": {}}


def test_compile_workflow_payload_normalizes_csv_wildcard_nodes() -> None:
    """Normalize CSV wildcard nodes at the compilation boundary."""
    workflow_payload: dict[str, object] = {
        "1": {
            "class_type": "CSVWildcardNode",
            "inputs": {"prompt_template": "A fox", "seed": 1},
        }
    }
    service, _repository, _compiler = build_service(workflow_payload)

    payload = service.compile_workflow_payload(
        sugar_script_text="use Cube as A",
        output_dir=Path("projects"),
    )

    assert payload["1"] == {"class_type": "String", "inputs": {"value": "A fox"}}
