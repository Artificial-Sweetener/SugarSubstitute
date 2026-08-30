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

"""Verify canonical ownership of authored and boundary-owned cube inputs."""

from __future__ import annotations

import pytest
from substitute.domain.cubes import (
    CubeAuthoringContract,
    CubeAuthoringContractError,
    CubeInputField,
)


def _control(node_key: str, input_key: str) -> dict[str, str]:
    """Return one complete canonical surface control."""

    return {
        "control_id": f"{node_key}.{input_key}",
        "symbol": node_key,
        "input_name": input_key,
        "label": input_key,
        "class_type": "TestNode",
        "value_type": "object",
    }


def _graph() -> dict[str, object]:
    """Return a graph containing structural, scalar, and ordered authored inputs."""

    return {
        "nodes": {
            "node": {
                "inputs": {
                    "image": ["@binding", "input.image"],
                    "strength": 0.5,
                    "masks": ["first.png", "second.png"],
                }
            }
        },
        "inputs": {
            "input.image": {"targets": [["node", "image"]]},
        },
        "surface": {
            "controls": [
                _control("node", "strength"),
                _control("node", "masks"),
            ]
        },
    }


def _native_subgraph_graph() -> dict[str, object]:
    """Return a native wrapper with structural and widget-backed public inputs."""

    return {
        "nodes": {
            "sampler": {
                "class_type": "subgraph-sampler",
                "inputs": {"model": ["checkpoint", 0], "batch_size": 2},
            }
        },
        "inputs": {},
        "surface": {"controls": []},
        "subgraphs": [
            {
                "id": "subgraph-sampler",
                "inputs": [
                    {"name": "model", "linkIds": [10]},
                    {"name": "batch_size", "linkIds": [11]},
                ],
                "nodes": [
                    {"inputs": [{"name": "model", "link": 10}]},
                    {
                        "inputs": [
                            {
                                "name": "batch_size",
                                "link": 11,
                                "widget": {"name": "batch_size"},
                            }
                        ]
                    },
                ],
            }
        ],
    }


def test_authoring_contract_uses_surface_fields_in_declared_order() -> None:
    """The surface contract should be the sole ordered authored-field authority."""

    contract = CubeAuthoringContract.from_graph(_graph())

    assert contract.authored_fields == (
        CubeInputField("node", "strength"),
        CubeInputField("node", "masks"),
    )


def test_authoring_contract_includes_only_widget_backed_subgraph_inputs() -> None:
    """Native wrapper widgets should be authored without claiming structural links."""

    contract = CubeAuthoringContract.from_graph(_native_subgraph_graph())

    assert contract.authored_fields == (CubeInputField("sampler", "batch_size"),)


def test_authoring_contract_rejects_boundary_surface_ownership_conflicts() -> None:
    """A concrete input cannot be both externally bound and surface-authored."""

    graph = _graph()
    surface = graph["surface"]
    assert isinstance(surface, dict)
    controls = surface["controls"]
    assert isinstance(controls, list)
    controls.append(_control("node", "image"))

    with pytest.raises(
        CubeAuthoringContractError,
        match="node.image",
    ):
        CubeAuthoringContract.from_graph(graph)
