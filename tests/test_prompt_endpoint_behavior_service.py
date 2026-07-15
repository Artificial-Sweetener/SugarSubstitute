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

"""Contract tests for prompt endpoint extraction from resolved node behavior."""

from __future__ import annotations

from substitute.application.node_behavior import FieldPresentation, PromptRole
from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


def test_behavior_snapshot_indexes_title_inferred_prompt_endpoint() -> None:
    """Layout title prompt inference should produce role-based prompt endpoints."""

    definitions: dict[str, dict[str, object]] = {
        "CustomPromptNode": {
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            }
        }
    }
    cube = cube_state(
        nodes={
            "node_17": {
                "class_type": "CustomPromptNode",
                "inputs": {"text": "a forest"},
            }
        },
        definitions=definitions,
    )
    cube.buffer["layout"] = {"nodes": {"node_17": {"title": "Positive Prompt"}}}

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )

    field = snapshot.resolved_nodes_by_alias["A"]["node_17"].fields["text"]
    endpoint = snapshot.prompt_endpoint_index.endpoint_for("A", PromptRole.POSITIVE)
    assert field.presentation == FieldPresentation.PROMPT_BOX
    assert field.prompt is not None
    assert field.prompt.role == PromptRole.POSITIVE
    assert endpoint is not None
    assert endpoint.node_name == "node_17"
    assert endpoint.field_key == "text"


def test_behavior_snapshot_omits_ambiguous_duplicate_prompt_endpoints() -> None:
    """Duplicate linkable endpoints for one cube role should not be guessed."""

    definitions: dict[str, dict[str, object]] = {
        "CustomPromptNode": {
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            }
        }
    }
    cube = cube_state(
        nodes={
            "first": {"class_type": "CustomPromptNode", "inputs": {"text": "a"}},
            "second": {"class_type": "CustomPromptNode", "inputs": {"text": "b"}},
        },
        definitions=definitions,
    )
    cube.buffer["layout"] = {
        "nodes": {
            "first": {"title": "Positive Prompt"},
            "second": {"title": "Positive Prompt"},
        }
    }

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )

    assert snapshot.prompt_endpoint_index.endpoint_for("A", PromptRole.POSITIVE) is None
    assert ("A", PromptRole.POSITIVE) in snapshot.prompt_endpoint_index.ambiguous_keys
    assert snapshot.node_link_endpoint_index.identities_for_cube("A") == ()


def test_behavior_snapshot_prioritizes_label_prompt_nodes_before_other_nodes() -> None:
    """Prompt labels should determine prompt-first node ordering for arbitrary ids."""

    definitions: dict[str, dict[str, object]] = {
        "CustomPromptNode": {
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            }
        },
        "OtherNode": {"input": {"required": {"value": ["INT"]}}},
    }
    cube = cube_state(
        nodes={
            "sampler": {"class_type": "OtherNode", "inputs": {"value": 1}},
            "neg": {"class_type": "CustomPromptNode", "inputs": {"text": "bad"}},
            "pos": {"class_type": "CustomPromptNode", "inputs": {"text": "good"}},
        },
        definitions=definitions,
    )
    cube.buffer["layout"] = {
        "nodes": {
            "pos": {"title": "Positive Prompt"},
            "neg": {"title": "Negative Prompt"},
        }
    }

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )

    assert list(snapshot.resolved_nodes_by_alias["A"].keys())[:2] == ["pos", "neg"]


def test_behavior_snapshot_exposes_prompt_node_link_endpoint() -> None:
    """Prompt endpoints should also be represented as whole-node link endpoints."""

    definitions: dict[str, dict[str, object]] = {
        "CustomPromptNode": {
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            }
        }
    }
    cube = cube_state(
        nodes={
            "node_17": {
                "class_type": "CustomPromptNode",
                "inputs": {"text": "a forest"},
            }
        },
        definitions=definitions,
    )
    cube.buffer["layout"] = {"nodes": {"node_17": {"title": "Positive Prompt"}}}

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )

    identities = snapshot.node_link_endpoint_index.identities_for_cube("A")
    assert len(identities) == 1
    endpoint = snapshot.node_link_endpoint_index.endpoint_for("A", identities[0])
    assert endpoint is not None
    assert endpoint.family == "prompt:positive"
    assert endpoint.node_name == "node_17"
    assert endpoint.editable_value_keys == ("text",)
    assert endpoint.reset_values == {"text": ""}


def test_behavior_snapshot_exposes_vectorscope_node_link_endpoint() -> None:
    """VectorscopeCC should be exposed as a multi-field whole-node endpoint."""

    definitions: dict[str, dict[str, object]] = {
        "VectorscopeCC": {
            "input": {
                "required": {
                    "model": ["MODEL"],
                    "alt": ["BOOLEAN"],
                    "brightness": ["FLOAT"],
                    "contrast": ["FLOAT"],
                    "saturation": ["FLOAT"],
                    "r": ["FLOAT"],
                    "g": ["FLOAT"],
                    "b": ["FLOAT"],
                    "method": [["Straight Abs.", "None"]],
                    "scaling": [["Flat", "Linear"]],
                }
            }
        }
    }
    cube = cube_state(
        nodes={
            "vectorscopecc": {
                "class_type": "VectorscopeCC",
                "inputs": {
                    "model": ["checkpoint", 0],
                    "alt": False,
                    "brightness": 0.5,
                    "contrast": 0.0,
                    "saturation": 1.0,
                    "r": 0.0,
                    "g": 0.0,
                    "b": 0.0,
                    "method": "Straight Abs.",
                    "scaling": "Flat",
                },
            }
        },
        definitions=definitions,
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class=definitions,
    )

    identities = snapshot.node_link_endpoint_index.identities_for_cube("A")
    endpoint = snapshot.node_link_endpoint_index.endpoint_for("A", identities[0])
    assert endpoint is not None
    assert endpoint.family == "vectorscopecc"
    assert endpoint.node_name == "vectorscopecc"
    assert endpoint.editable_value_keys == (
        "alt",
        "brightness",
        "contrast",
        "saturation",
        "r",
        "g",
        "b",
        "method",
        "scaling",
    )
    assert endpoint.graph_signature == (("model", ("checkpoint", 0)),)


def test_behavior_snapshot_omits_vectorscope_when_value_key_is_graph_connected() -> (
    None
):
    """Literal-vs-graph differences should produce different node-link identities."""

    definitions: dict[str, dict[str, object]] = {
        "VectorscopeCC": {
            "input": {
                "required": {
                    "model": ["MODEL"],
                    "brightness": ["FLOAT"],
                    "contrast": ["FLOAT"],
                }
            }
        }
    }
    cube_a = cube_state(
        nodes={
            "vectorscopecc": {
                "class_type": "VectorscopeCC",
                "inputs": {
                    "model": ["checkpoint", 0],
                    "brightness": 0.5,
                    "contrast": 0.0,
                },
            }
        },
        definitions=definitions,
    )
    cube_b = cube_state(
        nodes={
            "vectorscopecc": {
                "class_type": "VectorscopeCC",
                "inputs": {
                    "model": ["checkpoint", 0],
                    "brightness": ["source", 0],
                    "contrast": 0.0,
                },
            }
        },
        definitions=definitions,
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_a, "B": cube_b},
        stack_order=["A", "B"],
        definitions_by_class=definitions,
    )

    identities_a = snapshot.node_link_endpoint_index.identities_for_cube("A")
    identities_b = snapshot.node_link_endpoint_index.identities_for_cube("B")
    assert identities_a
    assert identities_b
    assert identities_a != identities_b
    assert (
        snapshot.node_link_endpoint_index.valid_link_targets(
            ["A", "B"],
            "B",
            identities_b[0],
        )
        == ()
    )
