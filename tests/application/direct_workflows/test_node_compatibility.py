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

"""Tests for contract-proven direct-workflow node compatibility aliases."""

from __future__ import annotations

from copy import deepcopy

from substitute.application.direct_workflows import (
    DirectWorkflowNodeCompatibilityService,
)
from substitute.domain.common import JsonObject


class _Definitions:
    """Return one configured live MaskToImage definition."""

    def __init__(self, definition: JsonObject) -> None:
        """Store the definition exposed by both lookup paths."""

        self._definition = definition

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return the configured definition for its exact class."""

        return {node_class: deepcopy(self._definition)}

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return the same configured definition for synchronous lookup."""

        return self.get_node_definition(node_class)


def _definition(*, module: str, name: str) -> JsonObject:
    """Build the exact one-mask-to-one-image contract."""

    return {
        "input": {"required": {"mask": ["MASK"]}},
        "output": ["IMAGE"],
        "name": name,
        "python_module": module,
    }


def _workflow() -> JsonObject:
    """Build a workflow with one captured private legacy node."""

    return {
        "nodes": [],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "id": "detailer",
                    "nodes": [
                        {
                            "id": 920,
                            "type": "SafeMaskToImage",
                            "inputs": [{"name": "mask", "type": "MASK"}],
                            "properties": {
                                "Node name for S&R": "SafeMaskToImage",
                                "cnr_id": "unrelated-package",
                                "ver": "1.0.0",
                            },
                        }
                    ],
                    "extra": {
                        "sugarcubes_document": {
                            "implementation": {
                                "nodes": {
                                    "safe_mask": {
                                        "class_type": "SafeMaskToImage",
                                        "inputs": {"mask": ["source", 0]},
                                    }
                                },
                                "definitions": {
                                    "SafeMaskToImage": _definition(
                                        module="custom_nodes.comfyui_fearnworksnodes",
                                        name="SafeMaskToImage",
                                    )
                                },
                            }
                        }
                    },
                }
            ]
        },
    }


def _service(
    *, target_definition: JsonObject | None = None
) -> DirectWorkflowNodeCompatibilityService:
    """Build the compatibility service with a live core definition."""

    definition = target_definition or _definition(
        module="comfy_extras.nodes_mask",
        name="MaskToImage",
    )
    return DirectWorkflowNodeCompatibilityService(_Definitions(definition))


def test_rewrites_every_reference_only_when_saved_and_live_contracts_match() -> None:
    """A proven legacy alias should become the live core node without mutating input."""

    source = _workflow()

    normalized = _service().normalize(source)

    assert source == _workflow()
    subgraph = normalized["definitions"]["subgraphs"][0]  # type: ignore[index]
    ui_node = subgraph["nodes"][0]
    assert ui_node["type"] == "MaskToImage"
    assert ui_node["properties"] == {
        "Node name for S&R": "MaskToImage",
        "cnr_id": "comfy-core",
    }
    implementation = subgraph["extra"]["sugarcubes_document"]["implementation"]
    assert implementation["nodes"]["safe_mask"]["class_type"] == "MaskToImage"
    assert "SafeMaskToImage" not in implementation["definitions"]
    assert implementation["definitions"]["MaskToImage"]["python_module"] == (
        "comfy_extras.nodes_mask"
    )


def test_rejects_alias_when_saved_contract_does_not_match() -> None:
    """Captured definitions with additional inputs must remain visibly unresolved."""

    source = _workflow()
    definition = source["definitions"]["subgraphs"][0]["extra"][  # type: ignore[index]
        "sugarcubes_document"
    ]["implementation"]["definitions"]["SafeMaskToImage"]
    definition["input"]["required"]["image"] = ["IMAGE"]

    assert _service().normalize(source) == source


def test_rejects_alias_when_live_core_contract_does_not_match() -> None:
    """A changed live target must disable the compatibility rule fail-closed."""

    source = _workflow()
    incompatible = _definition(
        module="comfy_extras.nodes_mask",
        name="MaskToImage",
    )
    incompatible["output"] = ["MASK"]

    assert _service(target_definition=incompatible).normalize(source) == source
