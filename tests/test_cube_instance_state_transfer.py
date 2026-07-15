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

from typing import cast

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


def _inputs_for(cube_definition: dict[str, object]) -> dict[str, object]:
    """Return sampler inputs from the minimal cube test definition."""

    nodes = cast(dict[str, object], cube_definition["nodes"])
    sampler = cast(dict[str, object], nodes["sampler"])
    return cast(dict[str, object], sampler["inputs"])
