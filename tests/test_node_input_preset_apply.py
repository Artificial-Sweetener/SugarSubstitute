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

"""Contract tests for applying node input presets."""

from __future__ import annotations

from typing import cast

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.domain.node_behavior import FieldBehavior
from substitute.domain.workflow import CubeState
from substitute.presentation.editor.panel.menus.node_input_preset_apply import (
    apply_node_input_preset,
)


class _ValueWidget:
    """Record a value written by preset application."""

    def __init__(self) -> None:
        """Initialize without a value."""

        self.value: object | None = None

    def setValue(self, value: object) -> None:
        """Store a written value."""

        self.value = value


def test_apply_node_input_preset_writes_buffer_and_live_widget() -> None:
    """Applying a preset should update authoritative state and visible widgets."""

    cube_state = _cube_state({"steps": 20})
    widget = _ValueWidget()

    report = apply_node_input_preset(
        cube_state=cube_state,
        cube_alias="A",
        node_name="sampler",
        node_type="KSampler",
        preset_id="node_inputs:test",
        preset_label="Fast Draft",
        preset_inputs={"steps": 12},
        node_inputs=_sampler_inputs(cube_state),
        field_specs={"steps": _field("steps", "INT")},
        is_connection=_is_connection,
        input_widgets_by_field_key={("A", "sampler", "steps"): widget},
    )

    assert report.applied_keys == ("steps",)
    assert report.skipped_fields == ()
    assert _sampler_inputs(cube_state)["steps"] == 12
    assert cube_state.dirty is True
    assert widget.value == 12


def test_apply_node_input_preset_skips_missing_connected_and_incompatible_fields() -> (
    None
):
    """Applying a preset should preserve fields that are not safe to write."""

    cube_state = _cube_state({"steps": 20, "cfg": ["other", 0], "name": "old"})

    report = apply_node_input_preset(
        cube_state=cube_state,
        cube_alias="A",
        node_name="sampler",
        node_type="KSampler",
        preset_id="node_inputs:test",
        preset_label="Fast Draft",
        preset_inputs={
            "steps": "bad",
            "cfg": 7.0,
            "missing": 1,
            "name": "new",
        },
        node_inputs=_sampler_inputs(cube_state),
        field_specs={
            "steps": _field("steps", "INT"),
            "cfg": _field("cfg", "FLOAT"),
            "name": _field("name", "STRING"),
        },
        is_connection=_is_connection,
    )

    assert report.applied_keys == ("name",)
    assert [(field.field_key, field.reason) for field in report.skipped_fields] == [
        ("steps", "incompatible_field_type"),
        ("cfg", "connected_field"),
        ("missing", "missing_field_spec"),
    ]
    assert _sampler_inputs(cube_state) == {
        "steps": 20,
        "cfg": ["other", 0],
        "name": "new",
    }


def _cube_state(inputs: dict[str, object]) -> CubeState:
    """Return a cube state containing one sampler node."""

    return CubeState(
        cube_id="cube",
        version="1",
        alias="A",
        original_cube={},
        buffer={
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": inputs,
                }
            }
        },
    )


def _sampler_inputs(cube_state: CubeState) -> dict[str, object]:
    """Return typed sampler inputs from a test cube state."""

    nodes = cast(dict[str, object], cube_state.buffer["nodes"])
    sampler = cast(dict[str, object], nodes["sampler"])
    return cast(dict[str, object], sampler["inputs"])


def _field(field_key: str, field_type: str | None) -> ResolvedFieldSpec:
    """Return a minimal resolved field spec for apply tests."""

    return ResolvedFieldSpec(
        cube_alias="A",
        node_name="sampler",
        class_type="KSampler",
        field_key=field_key,
        field_type=field_type,
        constraints={},
        meta_info={},
        field_info=None,
        value=None,
        field_behavior=FieldBehavior(field_key=field_key),
    )


def _is_connection(value: object) -> bool:
    """Return whether a value has the common Comfy connection shape."""

    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )
