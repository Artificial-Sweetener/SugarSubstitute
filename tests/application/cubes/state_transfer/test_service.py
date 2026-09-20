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

"""Tests for cube instance state transfer across definition updates."""

from __future__ import annotations

import copy
from typing import cast

import pytest

from substitute.application.cubes.cube_instance_state_transfer import (
    CubeInstanceStateTransferService,
    structural_patch_keys,
)
from substitute.domain.workflow import CubeState


def test_transfer_preserves_surface_value_by_control_id() -> None:
    """Reordered and renamed controls should preserve values by control id."""

    old = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=_cube_definition(control_symbol="sampler", input_name="denoise"),
        buffer=_cube_definition(
            control_symbol="sampler",
            input_name="denoise",
            value=0.35,
        ),
    )
    new_definition = _cube_definition(
        control_symbol="ksampler",
        input_name="denoise",
        value=0.75,
    )

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old,
        new_cube_definition=new_definition,
    )
    patch_nodes = cast(dict[str, object], result.buffer_patch["nodes"])
    patch_sampler = cast(dict[str, object], patch_nodes["ksampler"])
    patch_inputs = cast(dict[str, object], patch_sampler["inputs"])

    assert patch_inputs["denoise"] == 0.35
    assert result.report.preserved_surface_value_count == 1
    assert not structural_patch_keys().intersection(result.buffer_patch)


def test_transfer_reports_removed_surface_control() -> None:
    """Removed controls are dropped rather than patched onto the new definition."""

    old = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=_cube_definition(control_id="denoise"),
        buffer=_cube_definition(control_id="denoise", value=0.25),
    )
    new_definition = _cube_definition(control_id="steps")

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old,
        new_cube_definition=new_definition,
    )

    assert "denoise" in result.report.removed_control_ids
    assert result.report.dropped_surface_value_count == 1
    assert "nodes" not in result.buffer_patch or result.buffer_patch["nodes"] == {}


def test_removed_surface_value_is_not_reintroduced_as_node_input() -> None:
    """Surface-owned node inputs should not be copied after control removal."""

    old = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=_cube_definition(control_id="denoise"),
        buffer=_cube_definition(control_id="denoise", value=0.25),
    )
    new_definition = _cube_definition(control_id="steps", value=20.0)

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old,
        new_cube_definition=new_definition,
    )

    assert result.buffer_patch.get("nodes") == {}
    assert result.report.removed_control_ids == ("denoise",)


def test_incompatible_surface_value_is_not_reintroduced_as_node_input() -> None:
    """Incompatible surface controls should not fall through to node transfer."""

    old = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=_cube_definition(value_type="FLOAT"),
        buffer=_cube_definition(value=0.25, value_type="FLOAT"),
    )
    new_definition = _cube_definition(value=0.5, value_type="STRING")

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old,
        new_cube_definition=new_definition,
    )

    assert result.buffer_patch.get("nodes") == {}
    assert result.report.incompatible_control_ids == ("denoise",)


def test_non_surface_node_input_still_transfers_when_compatible() -> None:
    """Generic node transfer should still preserve compatible non-surface inputs."""

    old_definition = _cube_definition()
    _inputs_for(old_definition)["cfg"] = 7.0
    old_buffer = _cube_definition(value=0.25)
    _inputs_for(old_buffer)["cfg"] = 8.0
    new_definition = _cube_definition(value=0.5)
    _inputs_for(new_definition)["cfg"] = 7.0
    old = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=old_definition,
        buffer=old_buffer,
    )

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old,
        new_cube_definition=new_definition,
    )
    patch_nodes = cast(dict[str, object], result.buffer_patch["nodes"])
    patch_sampler = cast(dict[str, object], patch_nodes["sampler"])
    patch_inputs = cast(dict[str, object], patch_sampler["inputs"])

    assert patch_inputs["value"] == 0.25
    assert patch_inputs["cfg"] == 8.0


def test_transfer_reads_surface_from_document_and_values_from_implementation() -> None:
    """Graph-backed projections must preserve authored values across shape boundaries."""

    old_document = _canonical_cube_definition(value=0.5, cfg=7.0)
    old_implementation = cast(dict[str, object], old_document["implementation"])
    live_implementation = copy.deepcopy(old_implementation)
    _inputs_for(live_implementation)["value"] = 0.35
    _inputs_for(live_implementation)["cfg"] = 8.0
    old = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=old_document,
        buffer=live_implementation,
    )
    new_document = _canonical_cube_definition(
        version="2",
        control_symbol="sampler",
        value=0.75,
        cfg=6.0,
    )

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old,
        new_cube_definition=new_document,
    )
    patch_nodes = cast(dict[str, object], result.buffer_patch["nodes"])
    patch_sampler = cast(dict[str, object], patch_nodes["sampler"])
    patch_inputs = cast(dict[str, object], patch_sampler["inputs"])

    assert patch_inputs == {"value": 0.35, "cfg": 8.0}
    assert result.report.preserved_surface_value_count == 1
    assert result.report.preserved_node_input_count == 1
    assert result.report.dropped_authored_input_ids == ()


def test_transfer_never_restores_definition_owned_links() -> None:
    """The updated definition must remain the sole owner of internal topology."""

    old_definition = _cube_definition()
    _inputs_for(old_definition)["model"] = ["old-loader", 0]
    old_buffer = copy.deepcopy(old_definition)
    new_definition = _cube_definition()
    _inputs_for(new_definition)["model"] = ["new-loader", 0]
    old = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=old_definition,
        buffer=old_buffer,
    )

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old,
        new_cube_definition=new_definition,
    )

    patch_nodes = cast(dict[str, object], result.buffer_patch["nodes"])
    patch_sampler = cast(dict[str, object], patch_nodes["sampler"])
    patch_inputs = cast(dict[str, object], patch_sampler["inputs"])
    assert "model" not in patch_inputs


def test_transfer_reports_authored_value_that_new_definition_cannot_accept() -> None:
    """Removed authored inputs must be explicit destructive-loss evidence."""

    old_definition = _cube_definition()
    _inputs_for(old_definition)["cfg"] = 7.0
    old_buffer = copy.deepcopy(old_definition)
    _inputs_for(old_buffer)["cfg"] = 8.0
    old = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=old_definition,
        buffer=old_buffer,
    )

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old,
        new_cube_definition=_cube_definition(),
    )

    assert result.report.dropped_authored_input_ids == ("sampler.cfg",)
    assert result.report.has_destructive_loss is True


def test_graph_backed_transfer_preserves_hostile_authored_values_byte_for_byte() -> (
    None
):
    """Every compatible JSON value should survive without text normalization."""

    defaults: dict[str, object] = {
        "positive": "",
        "negative": "default",
        "steps": 28,
        "cfg": 5.5,
        "enabled": False,
        "sampler": "euler",
        "seed": 0,
        "batch": ["default"],
        "nested": {"default": [1, 2]},
    }
    authored: dict[str, object] = {
        "positive": ("α e\u0301 🧁 שלום\n" * 700) + "[SEP|right] end",
        "negative": " \t\r\n  ",
        "steps": 8,
        "cfg": 1.6,
        "enabled": True,
        "sampler": "dpmpp_2m_sde",
        "seed": 9_223_372_036_854_775_000,
        "batch": ["one", 2, False, None],
        "nested": {"unicode": "نص", "items": [1, {"value": "🧁"}]},
    }
    old_document = _multi_control_document(defaults)
    live_implementation = copy.deepcopy(old_document["implementation"])
    live_inputs = _named_inputs(live_implementation, "controls")
    live_inputs.update(copy.deepcopy(authored))
    old_cube = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=old_document,
        buffer=cast(dict[str, object], live_implementation),
    )
    new_defaults: dict[str, object] = {
        "positive": "new positive",
        "negative": "new negative",
        "steps": 40,
        "cfg": 7.0,
        "enabled": True,
        "sampler": "heun",
        "seed": 123,
        "batch": ["new"],
        "nested": {"new": [3]},
    }
    new_document = _multi_control_document(new_defaults, version="2")
    new_surface = cast(dict[str, object], new_document["surface"])
    new_controls = cast(list[object], new_surface["controls"])
    new_controls.reverse()
    new_inputs = _named_inputs(new_document["implementation"], "controls")
    new_inputs["model"] = ["new-loader", 0]

    first = CubeInstanceStateTransferService().transfer(
        old_cube=old_cube,
        new_cube_definition=new_document,
    )
    second = CubeInstanceStateTransferService().transfer(
        old_cube=old_cube,
        new_cube_definition=new_document,
    )
    patch_inputs = _named_inputs(first.buffer_patch, "controls")

    assert patch_inputs == authored
    assert first.buffer_patch == second.buffer_patch
    assert first.report.dropped_authored_input_ids == ()
    assert first.report.preserved_surface_value_count == len(authored)
    assert _named_inputs(new_document["implementation"], "controls")["model"] == [
        "new-loader",
        0,
    ]
    assert "model" not in patch_inputs


@pytest.mark.parametrize("authored", [False, True])
def test_removed_control_blocks_only_when_value_differs_from_old_default(
    authored: bool,
) -> None:
    """A removed unchanged default is safe while a removed authored value is not."""

    old_document = _canonical_cube_definition(value=0.5)
    old_implementation = copy.deepcopy(old_document["implementation"])
    if authored:
        _inputs_for(cast(dict[str, object], old_implementation))["value"] = 0.25
    old_cube = CubeState(
        cube_id="cube",
        version="1",
        alias="Demo",
        original_cube=old_document,
        buffer=cast(dict[str, object], old_implementation),
    )
    new_document = _canonical_cube_definition(version="2")
    cast(dict[str, object], new_document["surface"])["controls"] = []

    result = CubeInstanceStateTransferService().transfer(
        old_cube=old_cube,
        new_cube_definition=new_document,
    )

    assert result.report.has_destructive_loss is authored
    assert result.report.dropped_authored_input_ids == (
        ("surface.denoise",) if authored else ()
    )


def _cube_definition(
    *,
    control_id: str = "denoise",
    control_symbol: str = "sampler",
    input_name: str = "value",
    value: float = 0.5,
    value_type: str = "FLOAT",
) -> dict[str, object]:
    """Return a minimal runtime cube definition with one surface control."""

    return {
        "cube_id": "cube",
        "version": "1",
        "nodes": {
            control_symbol: {
                "class_type": "KSampler",
                "inputs": {input_name: value},
            }
        },
        "surface": {
            "controls": [
                {
                    "control_id": control_id,
                    "symbol": control_symbol,
                    "input_name": input_name,
                    "value_type": value_type,
                }
            ]
        },
    }


def _canonical_cube_definition(
    *,
    version: str = "1",
    control_symbol: str = "sampler",
    value: float = 0.5,
    cfg: float = 7.0,
) -> dict[str, object]:
    """Return a production-shaped canonical Cube document."""

    implementation = _cube_definition(
        control_symbol=control_symbol,
        value=value,
    )
    implementation.pop("surface")
    nodes = cast(dict[str, object], implementation["nodes"])
    node = cast(dict[str, object], nodes[control_symbol])
    inputs = cast(dict[str, object], node["inputs"])
    inputs["cfg"] = cfg
    return {
        "cube_id": "cube",
        "version": version,
        "implementation": implementation,
        "surface": {
            "controls": [
                {
                    "control_id": "denoise",
                    "symbol": control_symbol,
                    "input_name": "value",
                    "value_type": "FLOAT",
                }
            ]
        },
    }


def _inputs_for(cube_definition: dict[str, object]) -> dict[str, object]:
    """Return sampler inputs from the minimal cube test definition."""

    nodes = cast(dict[str, object], cube_definition["nodes"])
    sampler = cast(dict[str, object], nodes["sampler"])
    return cast(dict[str, object], sampler["inputs"])


def _multi_control_document(
    values: dict[str, object],
    *,
    version: str = "1",
) -> dict[str, object]:
    """Return one canonical document with stable controls for every value."""

    return {
        "cube_id": "cube",
        "version": version,
        "implementation": {
            "nodes": {
                "controls": {
                    "class_type": "HostileValueNode",
                    "inputs": copy.deepcopy(values),
                }
            }
        },
        "surface": {
            "controls": [
                {
                    "control_id": name,
                    "symbol": "controls",
                    "input_name": name,
                    "value_type": type(value).__name__,
                }
                for name, value in values.items()
            ]
        },
    }


def _named_inputs(payload: object, node_name: str) -> dict[str, object]:
    """Return one node's input mapping from a canonical or implementation shape."""

    mapping = cast(dict[str, object], payload)
    implementation = cast(
        dict[str, object],
        mapping.get("implementation", mapping),
    )
    nodes = cast(dict[str, object], implementation["nodes"])
    node = cast(dict[str, object], nodes[node_name])
    return cast(dict[str, object], node["inputs"])
