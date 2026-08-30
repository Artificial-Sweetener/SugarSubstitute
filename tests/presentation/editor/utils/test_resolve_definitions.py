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

"""Verify editor input-definition resolution."""

from __future__ import annotations

from substitute.presentation.editor.utils.resolve_definitions import (
    resolve_input_definition,
)


def test_resolve_input_definition_merges_inputs_and_extracts_constraints() -> None:
    """Resolve required and optional definitions into field metadata."""

    definitions = {
        "sampler": {
            "input": {
                "required": {
                    "sampler_name": ["STR", {"min": 0, "max": 10, "step": 1}],
                },
                "optional": {
                    "seed": ["INT"],
                    "schedule": [["a", "b"], {"step": 2}],
                },
            }
        }
    }

    type_name, metadata, _field, constraints = resolve_input_definition(
        definitions,
        "sampler",
        "sampler_name",
    )
    assert type_name == "STR"
    assert metadata.get("min") == 0
    assert constraints == {"min": 0, "max": 10, "step": 1}

    option_type, _option_metadata, _option_field, option_constraints = (
        resolve_input_definition(definitions, "sampler", "schedule")
    )
    assert option_type == "LIST"
    assert option_constraints["step"] == 2

    seed_type, _seed_metadata, _seed_field, seed_constraints = resolve_input_definition(
        definitions,
        "sampler",
        "seed",
    )
    assert seed_type == "INT"
    assert seed_constraints["min"] is None
