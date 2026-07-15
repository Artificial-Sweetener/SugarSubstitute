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

"""Tests for compiled prompt graph traversal helpers."""

from __future__ import annotations

from substitute.application.prompt_editor.prompt_workflow_graph import (
    downstream_node_ids,
    prompt_node_ids,
    upstream_node_ids,
)


def test_prompt_node_ids_reads_wrapped_prompt_nodes() -> None:
    """Prompt node matching should inspect executable nodes inside artifacts."""

    payload = {
        "prompt": {
            "1": {
                "class_type": "PrimitiveString",
                "_meta": {"title": "Cube.positive_prompt"},
                "inputs": {},
            }
        },
        "workflow": {"nodes": []},
    }

    assert prompt_node_ids(
        workflow_payload=payload,
        cube_alias="Cube",
        prompt_node_name="positive_prompt",
    ) == ("1",)


def test_downstream_node_ids_reads_wrapped_prompt_nodes() -> None:
    """Downstream traversal should follow links inside executable prompt nodes."""

    payload = {
        "prompt": {
            "1": {"class_type": "PrimitiveString", "inputs": {}},
            "2": {"class_type": "RegexExtract", "inputs": {"text": ["1", 0]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": ["2", 0]}},
        },
        "workflow": {"nodes": []},
    }

    assert downstream_node_ids(workflow_payload=payload, start_node_ids=("1",)) == (
        "2",
        "3",
    )


def test_upstream_node_ids_reads_wrapped_prompt_nodes() -> None:
    """Upstream traversal should follow links inside executable prompt nodes."""

    payload = {
        "prompt": {
            "1": {"class_type": "PrimitiveString", "inputs": {}},
            "2": {"class_type": "RegexExtract", "inputs": {"text": ["1", 0]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": ["2", 0]}},
        },
        "workflow": {"nodes": []},
    }

    assert upstream_node_ids(
        workflow_payload=payload,
        start_node_id="3",
        visited=set(),
    ) == ("2", "1")


def test_graph_helpers_preserve_raw_node_map_support() -> None:
    """Legacy raw prompt node maps should remain supported by graph traversal."""

    payload = {
        "1": {
            "class_type": "PrimitiveString",
            "_meta": {"title": "Cube.positive_prompt"},
            "inputs": {},
        },
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": ["1", 0]}},
    }

    assert prompt_node_ids(
        workflow_payload=payload,
        cube_alias="Cube",
        prompt_node_name="positive_prompt",
    ) == ("1",)
    assert downstream_node_ids(workflow_payload=payload, start_node_ids=("1",)) == (
        "2",
    )
