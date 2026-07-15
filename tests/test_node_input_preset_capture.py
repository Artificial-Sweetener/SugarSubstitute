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

"""Contract tests for node input preset value capture."""

from __future__ import annotations

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.domain.node_behavior import FieldBehavior
from substitute.presentation.editor.panel.menus.node_input_preset_capture import (
    capture_savable_node_inputs,
)


def test_capture_uses_field_spec_keys_and_skips_missing_or_connected_inputs() -> None:
    """Capture should only store editable field-spec inputs."""

    captured = capture_savable_node_inputs(
        node_inputs={
            "steps": 20,
            "cfg": 7.0,
            "model": ["checkpoint", 0],
            "ignored": "not in field specs",
        },
        field_specs={
            "steps": _field("steps", "INT"),
            "cfg": _field("cfg", "FLOAT"),
            "model": _field("model", None),
            "missing": _field("missing", "STRING"),
        },
        is_connection=_is_connection,
    )

    assert captured == {"steps": 20, "cfg": 7.0}


def test_capture_skips_non_json_safe_values() -> None:
    """Capture should skip values that cannot be stored in JSON presets."""

    captured = capture_savable_node_inputs(
        node_inputs={
            "valid": {"nested": [True, None, "text"]},
            "invalid_key": {1: "bad"},
            "invalid_value": object(),
        },
        field_specs={
            "valid": _field("valid", None),
            "invalid_key": _field("invalid_key", None),
            "invalid_value": _field("invalid_value", None),
        },
        is_connection=_is_connection,
    )

    assert captured == {"valid": {"nested": [True, None, "text"]}}


def test_capture_deep_copies_mutable_values() -> None:
    """Captured mutable values should be detached from live node input state."""

    live_value = {"nested": [1, 2]}
    captured = capture_savable_node_inputs(
        node_inputs={"value": live_value},
        field_specs={"value": _field("value", None)},
        is_connection=_is_connection,
    )

    live_value["nested"].append(3)

    assert captured == {"value": {"nested": [1, 2]}}


def test_capture_preserves_bool_as_bool() -> None:
    """Boolean values should stay booleans rather than being treated as ints."""

    captured = capture_savable_node_inputs(
        node_inputs={"enabled": True},
        field_specs={"enabled": _field("enabled", "BOOLEAN")},
        is_connection=_is_connection,
    )

    assert captured == {"enabled": True}


def _field(field_key: str, field_type: str | None) -> ResolvedFieldSpec:
    """Return a minimal resolved field spec for capture tests."""

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
