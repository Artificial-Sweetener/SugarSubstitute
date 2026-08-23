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

"""Subgraph-wrapper virtual-definition contracts."""

from __future__ import annotations

from typing import Any, cast

from substitute.domain.cubes import SubgraphWrapperDefinitionIndex
from tests.domain.cubes.subgraph_wrappers.support import (
    _metadata_runtime_graph,
    _nested_metadata_runtime_graph,
    _runtime_graph,
)


UUID_WRAPPER = "644694cf-354b-4cc8-8a67-a78145a8180e"
UUID_NESTED_WRAPPER = "8f6c43da-07af-4666-9e9a-0b4c7f83bdad"


def test_wrapper_definition_index_derives_definition_from_subgraph_interface() -> None:
    """Virtual wrapper definitions should expose only the public subgraph interface."""

    index = SubgraphWrapperDefinitionIndex.from_runtime_graph(_runtime_graph())

    definition = index.definition_for_class_type(UUID_WRAPPER)

    assert definition is not None
    assert definition["display_name"] == "Detailer"
    assert definition["output"] == ["IMAGE", "MASK"]
    assert definition["output_name"] == ["Image", "Mask"]
    input_section = definition["input"]
    assert isinstance(input_section, dict)
    required = input_section["required"]
    assert isinstance(required, dict)
    assert list(required) == ["image", "steps", "cfg"]
    assert required["image"][0] == "IMAGE"
    assert required["steps"][0] == "INT"
    assert required["cfg"][0] == "ANY"
    assert required["image"][1]["subgraph_wrapper"] is True
    assert required["image"][1]["subgraph_id"] == UUID_WRAPPER
    assert required["image"][1]["localized_name"] == "Image"
    assert required["image"][1]["shape"] == 7
    assert required["image"][1]["interface_id"] == 101


def test_wrapper_definition_index_ignores_subgraph_body_widgets() -> None:
    """Internal body widgets must not leak into the wrapper virtual definition."""

    index = SubgraphWrapperDefinitionIndex.from_runtime_graph(_runtime_graph())

    definition = index.definition_for_class_type(UUID_WRAPPER)

    assert definition is not None
    input_section = definition["input"]
    assert isinstance(input_section, dict)
    required = input_section["required"]
    assert isinstance(required, dict)
    assert "internal_widget" not in required
    assert "widgets_values" not in required


def test_wrapper_definition_enriches_public_input_from_linked_body_definition() -> None:
    """Linked body definitions should fill missing public wrapper field metadata."""

    index = SubgraphWrapperDefinitionIndex.from_runtime_graph(_metadata_runtime_graph())

    definition = index.definition_for_class_type(UUID_WRAPPER)

    assert definition is not None
    input_section = definition["input"]
    assert isinstance(input_section, dict)
    required = input_section["required"]
    assert isinstance(required, dict)
    assert list(required) == ["image", "denoise"]
    denoise = required["denoise"]
    assert denoise[0] == "FLOAT"
    assert denoise[1]["default"] == 0.5
    assert denoise[1]["default_source"] == "body_definition_fallback"
    assert denoise[1]["has_authored_default"] is False
    assert denoise[1]["min"] == 0.0001
    assert denoise[1]["max"] == 1.0
    assert denoise[1]["step"] == 0.01
    assert denoise[1]["body_node_type"] == "DetailerForEach"
    assert denoise[1]["body_input_name"] == "denoise"
    assert "DetailerForEach" not in required
    assert "1470" not in required


def test_wrapper_definition_prefers_body_widget_default_before_body_definition() -> (
    None
):
    """Body widget values should become wrapper defaults before body definition defaults."""

    index = SubgraphWrapperDefinitionIndex.from_runtime_graph(
        _metadata_runtime_graph(body_widget_values=[0.65])
    )

    definition = index.definition_for_class_type(UUID_WRAPPER)

    assert definition is not None
    input_section = definition["input"]
    assert isinstance(input_section, dict)
    required = input_section["required"]
    assert isinstance(required, dict)
    assert required["denoise"][1]["default"] == 0.65
    assert required["denoise"][1]["default_source"] == "authored_body_widget"
    assert required["denoise"][1]["has_authored_default"] is True


def test_wrapper_definition_prefers_link_id_over_stale_target_slot() -> None:
    """Public wrapper inputs should resolve the body widget by link identity first."""

    graph = _metadata_runtime_graph(body_widget_values=[0, 0.65])
    subgraphs = cast(list[Any], graph["subgraphs"])
    subgraph = subgraphs[0]
    assert isinstance(subgraph, dict)
    links = subgraph["links"]
    assert isinstance(links, dict)
    denoise_link = links["1041"]
    assert isinstance(denoise_link, dict)
    denoise_link["target_slot"] = 1
    nodes = subgraph["nodes"]
    assert isinstance(nodes, dict)
    body_node = nodes["1470"]
    assert isinstance(body_node, dict)
    inputs = body_node["inputs"]
    assert isinstance(inputs, list)
    inputs.insert(
        1,
        {
            "localized_name": "unlinked_mode",
            "name": "unlinked_mode",
            "type": "COMBO",
            "widget": {"name": "unlinked_mode"},
        },
    )

    index = SubgraphWrapperDefinitionIndex.from_runtime_graph(graph)

    definition = index.definition_for_class_type(UUID_WRAPPER)

    assert definition is not None
    input_section = definition["input"]
    assert isinstance(input_section, dict)
    required = input_section["required"]
    assert isinstance(required, dict)
    denoise = required["denoise"]
    assert denoise[0] == "FLOAT"
    assert denoise[1]["body_input_name"] == "denoise"
    assert denoise[1]["default"] == 0.65
    assert denoise[1]["min"] == 0.0001


def test_wrapper_definition_preserves_public_default_before_body_defaults() -> None:
    """Explicit public interface defaults should remain authoritative."""

    index = SubgraphWrapperDefinitionIndex.from_runtime_graph(
        _metadata_runtime_graph(body_widget_values=[0.65], public_default=0.7)
    )

    definition = index.definition_for_class_type(UUID_WRAPPER)

    assert definition is not None
    input_section = definition["input"]
    assert isinstance(input_section, dict)
    required = input_section["required"]
    assert isinstance(required, dict)
    assert required["denoise"][1]["default"] == 0.7
    assert required["denoise"][1]["default_source"] == "authored_public_interface"
    assert required["denoise"][1]["has_authored_default"] is True


def test_wrapper_definition_enriches_public_input_from_nested_wrapper() -> None:
    """Nested wrapper definitions should enrich parent wrapper public fields."""

    index = SubgraphWrapperDefinitionIndex.from_runtime_graph(
        _nested_metadata_runtime_graph()
    )

    definition = index.definition_for_class_type(UUID_WRAPPER)

    assert definition is not None
    input_section = definition["input"]
    assert isinstance(input_section, dict)
    required = input_section["required"]
    assert isinstance(required, dict)
    assert list(required) == ["c"]
    scale_factor = required["c"]
    assert scale_factor[0] == "FLOAT"
    assert scale_factor[1]["label"] == "Scale Factor"
    assert scale_factor[1]["interface_type"] == "INT,FLOAT,IMAGE,LATENT"
    assert scale_factor[1]["subgraph_id"] == UUID_WRAPPER
    assert scale_factor[1]["default"] == 1.5
    assert scale_factor[1]["default_source"] == "authored_body_widget"
    assert scale_factor[1]["has_authored_default"] is True
    assert scale_factor[1]["min"] == 0.25
    assert scale_factor[1]["max"] == 3.0
    assert scale_factor[1]["step"] == 0.05
    assert UUID_NESTED_WRAPPER not in required
    assert "PrimitiveFloat" not in required
