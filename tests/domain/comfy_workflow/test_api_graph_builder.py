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

"""Verify executable API graph construction."""

from __future__ import annotations

from substitute.domain.comfy_workflow import ComfyApiGraphBuilder


def test_api_builder_strips_metadata_and_rewires_bypassed_node() -> None:
    """Remove a bypassed node and route compatible connections around it."""
    graph = {
        "nodes": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {"image": "input.png"},
                "mode": 0,
                "_workflow": {"inputs": [], "outputs": []},
            },
            "2": {
                "class_type": "ImageScale",
                "inputs": {"image": ["1", 0], "width": 512},
                "mode": 4,
                "_meta": {"title": "Optional scale"},
                "_workflow": {
                    "inputs": [
                        {"name": "image", "type": "IMAGE"},
                        {"name": "width", "type": "INT"},
                    ],
                    "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                },
            },
            "3": {
                "class_type": "PreviewImage",
                "inputs": {"images": ["2", 0]},
                "mode": 0,
                "_workflow": {"inputs": [], "outputs": []},
            },
        }
    }

    payload = ComfyApiGraphBuilder().build(graph)

    assert tuple(payload) == ("1", "3")
    assert payload["3"]["inputs"]["images"] == ["1", 0]  # type: ignore[index]
    assert "mode" not in payload["1"]  # type: ignore[operator]
    assert "_workflow" not in payload["1"]  # type: ignore[operator]


def test_api_builder_disconnects_unroutable_bypass_output() -> None:
    """Disconnect a bypass output without a compatible upstream input."""
    graph = {
        "nodes": {
            "1": {
                "class_type": "Constant",
                "inputs": {},
                "mode": 4,
                "_workflow": {
                    "inputs": [],
                    "outputs": [{"name": "VALUE", "type": "INT"}],
                },
            },
            "2": {
                "class_type": "Consumer",
                "inputs": {"value": ["1", 0]},
                "mode": 0,
            },
        }
    }

    payload = ComfyApiGraphBuilder().build(graph)

    assert payload["2"]["inputs"] == {}  # type: ignore[index]
