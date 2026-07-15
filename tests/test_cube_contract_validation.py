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

"""Contract tests for Substitute cube load-boundary validation."""

from __future__ import annotations

from typing import Any

import pytest

from substitute.domain.workflow.cube_contract_validator import (
    CubeContractError,
    validate_cube_contract,
)


UUID_WRAPPER = "94f725d5-39bf-4060-be68-f573214a2055"
CHILD_UUID_WRAPPER = "53f09d1e-0364-4cb3-b5e7-535f63d1323f"


def _valid_wrapper_cube() -> dict[str, Any]:
    """Build a minimal valid wrapper-backed cube payload."""

    return {
        "cube_id": "wrapper_cube",
        "version": "1.0.0",
        "nodes": {
            "wrapper": {"class_type": UUID_WRAPPER, "inputs": {"prompt": "hello"}},
            "consumer": {
                "class_type": "ConsumerNode",
                "inputs": {"text": ["wrapper", 0]},
            },
        },
        "outputs": {"output.text": "consumer"},
        "definitions": {
            "RegexExtract": {"input": {"required": {"regex_pattern": ["STRING"]}}}
        },
        "subgraphs": [
            {
                "id": UUID_WRAPPER,
                "inputs": [{"name": "prompt", "label": "Prompt", "linkIds": [11]}],
                "outputs": [{"name": "text", "label": "Text", "linkIds": [12]}],
                "links": [
                    [11, -10, 0, 1, "text", "STRING"],
                    [12, 1, 0, -20, 0, "STRING"],
                ],
                "nodes": [{"id": 1, "type": "RegexExtract"}],
            }
        ],
    }


def _valid_nested_wrapper_cube() -> dict[str, Any]:
    """Build a valid wrapper cube with one nested wrapper dependency."""

    payload = _valid_wrapper_cube()
    payload["subgraphs"][0]["nodes"] = [
        {"id": 1, "type": CHILD_UUID_WRAPPER},
    ]
    payload["subgraphs"].append(
        {
            "id": CHILD_UUID_WRAPPER,
            "inputs": [{"name": "value", "label": "Value", "linkIds": [21]}],
            "outputs": [{"name": "text", "label": "Text", "linkIds": [22]}],
            "links": [
                [21, -10, 0, 2, "value", "STRING"],
                [22, 2, 0, -20, 0, "STRING"],
            ],
            "nodes": [{"id": 2, "type": "RegexExtract"}],
        }
    )
    return payload


def test_validate_cube_contract_rejects_missing_wrapper_subgraph_definition() -> None:
    """Wrapper cubes must include matching subgraph definitions by wrapper class_type id."""

    payload = _valid_wrapper_cube()
    payload["subgraphs"] = []

    with pytest.raises(CubeContractError, match="no subgraph definitions"):
        validate_cube_contract(payload, cube_name="wrapper_cube")


def test_validate_cube_contract_accepts_compact_subgraph_without_node_definitions() -> (
    None
):
    """Subgraph node definitions can be compact and supplied by live Comfy metadata."""

    payload = _valid_wrapper_cube()
    payload["definitions"] = {}

    validate_cube_contract(payload, cube_name="wrapper_cube")


def test_validate_cube_contract_rejects_wrapper_subgraph_without_interface_arrays() -> (
    None
):
    """Wrapper-backed subgraphs must expose explicit inputs and outputs arrays."""

    payload = _valid_wrapper_cube()
    del payload["subgraphs"][0]["inputs"]

    with pytest.raises(CubeContractError, match="inputs array"):
        validate_cube_contract(payload, cube_name="wrapper_cube")


def test_validate_cube_contract_rejects_missing_input_interface_link_mapping() -> None:
    """Interface links from input bridge node must be declared in inputs.linkIds."""

    payload = _valid_wrapper_cube()
    payload["subgraphs"][0]["inputs"] = [
        {"name": "prompt", "label": "Prompt", "linkIds": []}
    ]

    with pytest.raises(CubeContractError, match="missing inputs\\.linkIds mappings"):
        validate_cube_contract(payload, cube_name="wrapper_cube")


def test_validate_cube_contract_rejects_missing_output_interface_link_mapping() -> None:
    """Interface links to output bridge node must be declared in outputs.linkIds."""

    payload = _valid_wrapper_cube()
    payload["subgraphs"][0]["outputs"] = [
        {"name": "text", "label": "Text", "linkIds": []}
    ]

    with pytest.raises(CubeContractError, match="missing outputs\\.linkIds mappings"):
        validate_cube_contract(payload, cube_name="wrapper_cube")


def test_validate_cube_contract_rejects_missing_public_interface_label() -> None:
    """Current wrapper interfaces must store explicit user-visible labels."""

    payload = _valid_wrapper_cube()
    del payload["subgraphs"][0]["inputs"][0]["label"]

    with pytest.raises(CubeContractError, match="non-empty 'label'"):
        validate_cube_contract(payload, cube_name="wrapper_cube")


def test_validate_cube_contract_rejects_duplicate_public_interface_labels() -> None:
    """Duplicate labels in one public wrapper interface scope are ambiguous."""

    payload = _valid_wrapper_cube()
    payload["subgraphs"][0]["inputs"].append(
        {"name": "other", "label": "Prompt", "linkIds": []}
    )

    with pytest.raises(CubeContractError, match="duplicate inputs label 'Prompt'"):
        validate_cube_contract(payload, cube_name="wrapper_cube")


def test_validate_cube_contract_accepts_valid_wrapper_cube() -> None:
    """Valid wrapper cube payloads should pass boundary validation."""

    validate_cube_contract(_valid_wrapper_cube(), cube_name="wrapper_cube")


def test_cube_contract_validator_accepts_complete_nested_subgraphs() -> None:
    """Reachable nested subgraph dependencies should pass when definitions exist."""

    validate_cube_contract(_valid_nested_wrapper_cube(), cube_name="wrapper_cube")


def test_cube_contract_validator_rejects_missing_nested_subgraph() -> None:
    """Reachable nested wrapper references must have matching subgraph definitions."""

    payload = _valid_nested_wrapper_cube()
    payload["subgraphs"] = payload["subgraphs"][:1]

    with pytest.raises(
        CubeContractError,
        match=(
            f"subgraph '{UUID_WRAPPER}' references missing nested subgraph definition "
            f"'{CHILD_UUID_WRAPPER}'"
        ),
    ):
        validate_cube_contract(payload, cube_name="wrapper_cube")


def test_cube_contract_validator_rejects_nested_subgraph_cycle() -> None:
    """Cyclic nested subgraph dependencies should fail clearly at load time."""

    payload = _valid_nested_wrapper_cube()
    payload["subgraphs"][1]["nodes"] = [{"id": 2, "type": UUID_WRAPPER}]

    with pytest.raises(CubeContractError, match="cyclic subgraph wrapper references"):
        validate_cube_contract(payload, cube_name="wrapper_cube")
