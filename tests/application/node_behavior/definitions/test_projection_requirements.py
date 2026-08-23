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

"""Editor projection node-definition requirement contracts."""

from __future__ import annotations

from substitute.application.node_behavior import (
    required_node_definition_classes_for_editor_projection,
)
from tests.domain.cubes.subgraph_wrappers.support import (
    _metadata_runtime_graph,
    _nested_metadata_runtime_graph,
)


UUID_WRAPPER = "644694cf-354b-4cc8-8a67-a78145a8180e"
UUID_NESTED_WRAPPER = "8f6c43da-07af-4666-9e9a-0b4c7f83bdad"


def test_required_node_definition_classes_include_direct_nodes() -> None:
    """Projection requirements should include rendered direct node classes."""

    classes = required_node_definition_classes_for_editor_projection(
        {
            "A": {
                "nodes": {
                    "sampler": {"class_type": "KSampler"},
                    "vae": {"class_type": "VAELoader"},
                    "wrapper": {"class_type": UUID_WRAPPER},
                },
                "definitions": {"UnusedNode": {"input": {}}},
            }
        }
    )

    assert classes == ("KSampler", "VAELoader")


def test_required_node_definition_classes_include_wrapper_body_nodes() -> None:
    """Projection requirements should include body node classes behind wrappers."""

    classes = required_node_definition_classes_for_editor_projection(
        {"A": _metadata_runtime_graph()}
    )

    assert classes == ("DetailerForEach",)


def test_required_node_definition_classes_include_nested_wrapper_body_nodes() -> None:
    """Projection requirements should include body nodes behind nested wrappers."""

    classes = required_node_definition_classes_for_editor_projection(
        {"A": _nested_metadata_runtime_graph()}
    )

    assert classes == ("PrimitiveFloat",)


def test_required_node_definition_classes_skip_hidden_implementation_nodes() -> None:
    """Projection requirements should ignore body nodes not backing wrapper fields."""

    classes = required_node_definition_classes_for_editor_projection(
        {
            "A": {
                "nodes": {
                    "sampler": {"class_type": "KSampler"},
                    "wrapper": {"class_type": UUID_WRAPPER},
                },
                "subgraphs": [
                    {
                        "id": UUID_WRAPPER,
                        "name": "Prompt internals",
                        "inputNode": {"id": -10},
                        "inputs": [],
                        "links": [],
                        "nodes": [
                            {"id": 42, "type": "RegexExtract"},
                            {"id": 43, "type": "PrimitiveStringMultiline"},
                        ],
                    }
                ],
            }
        }
    )

    assert classes == ("KSampler",)


def test_required_node_definition_classes_deduplicate_sort_and_exclude_wrappers() -> (
    None
):
    """Projection requirements should be stable and skip UUID wrapper classes."""

    classes = required_node_definition_classes_for_editor_projection(
        {
            "A": {
                "nodes": {
                    "a": {"class_type": "ZNode"},
                    "b": {"class_type": "ANode"},
                    "c": {"class_type": UUID_WRAPPER},
                },
                "subgraphs": [
                    {
                        "nodes": [
                            {"type": "ZNode"},
                            {"type": UUID_NESTED_WRAPPER},
                        ]
                    }
                ],
            }
        }
    )

    assert classes == ("ANode", "ZNode")


def test_required_node_definition_classes_tolerate_malformed_sections() -> None:
    """Projection requirements should ignore malformed graph sections."""

    classes = required_node_definition_classes_for_editor_projection(
        {"A": {"nodes": ["not-a-node-map"], "subgraphs": {"bad": "shape"}}}
    )

    assert classes == ()
