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

"""General choice-field resolution contracts."""

from __future__ import annotations


from substitute.application.node_behavior import (
    FieldValueSource,
)
from substitute.application.node_behavior.list_value_resolver import (
    extract_live_list_options,
)
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)


def test_build_snapshot_resolves_combo_choice_fields() -> None:
    """COMBO fields should resolve through the same choice-value path as LIST fields."""

    cube = cube_state(
        nodes={
            "load_upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {"model_name": "R-ESRGAN 4x+ Anime6B.pth"},
            }
        },
        definitions={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["load_upscale_model"]["model_name"]

    assert spec.field_type == "COMBO"
    assert extract_live_list_options(spec.field_info) == (
        "ESRGAN_4x.pth",
        "R-ESRGAN 4x+ Anime6B.pth",
    )
    assert spec.value == "R-ESRGAN 4x+ Anime6B.pth"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_build_snapshot_resolves_missing_combo_to_first_option() -> None:
    """COMBO fields without authored values should fall back to their first option."""

    cube = cube_state(
        nodes={
            "load_upscale_model": {
                "class_type": "UpscaleModelLoader",
                "inputs": {},
            }
        },
        definitions={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UpscaleModelLoader": {
                "input": {
                    "required": {
                        "model_name": [
                            "COMBO",
                            {
                                "options": [
                                    "ESRGAN_4x.pth",
                                    "R-ESRGAN 4x+ Anime6B.pth",
                                ]
                            },
                        ]
                    }
                },
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["load_upscale_model"]["model_name"]

    assert spec.field_type == "COMBO"
    assert spec.value == "ESRGAN_4x.pth"
    assert spec.value_source == FieldValueSource.FIRST_OPTION
