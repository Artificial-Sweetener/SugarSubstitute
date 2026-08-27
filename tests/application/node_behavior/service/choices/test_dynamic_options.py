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

"""Dynamic choice-option contracts."""

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


def test_build_snapshot_marks_link_backed_sampler_fields_as_linked_without_rewrite() -> (
    None
):
    """Active sampler links should bypass literal canonicalization and remain linked."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "legacy-sampler"},
                "sampler_link": {"from_cube": "A", "from_node": "upstream"},
            }
        }
    )
    snapshot = build_behavior_snapshot(
        cube_states={"B": cube},
        stack_order=["B"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [["euler", "heun"], {}],
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["B"]["ksampler"]["sampler_name"]

    assert spec.raw_value == "legacy-sampler"
    assert spec.value == "legacy-sampler"
    assert spec.value_source == FieldValueSource.LINKED
    assert cube.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == (
        "legacy-sampler"
    )
    assert cube.dirty is False


def test_build_snapshot_prefers_live_options_over_compact_dynamic_cube_definition() -> (
    None
):
    """Compact dynamic cube metadata should hydrate from current live Comfy options."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "heun"},
            }
        },
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [
                            "LIST",
                            {"dynamic": True, "input_order": 1},
                        ],
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [
                            ["euler", "heun"],
                            {"default": "euler"},
                        ]
                    }
                }
            }
        },
    )

    spec = snapshot.field_specs_by_alias["A"]["ksampler"]["sampler_name"]

    assert extract_live_list_options(spec.field_info) == ("euler", "heun")
    assert spec.meta_info["options_resolved"] is True
    assert spec.meta_info["options_unavailable_reason"] is None
    assert spec.value == "heun"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_build_snapshot_ignores_compact_dynamic_list_marker_when_live_missing() -> None:
    """Offline compact dynamic LIST metadata must not become runtime metadata."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "heun"},
            }
        },
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [
                            "LIST",
                            {"dynamic": True, "input_order": 1},
                        ],
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

    spec = snapshot.field_specs_by_alias["A"]["ksampler"]["sampler_name"]

    assert spec.field_type is None
    assert spec.field_info is None
    assert "options_resolved" not in spec.meta_info
    assert "options_unavailable_reason" not in spec.meta_info
    assert spec.value == "heun"
    assert spec.value_source == FieldValueSource.EXPLICIT


def test_build_snapshot_ignores_cube_authored_combo_options_when_live_missing() -> None:
    """Cube-authored COMBO options must not become authoritative choices."""

    cube = cube_state(
        nodes={
            "ksampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "cube_only"},
            }
        },
        definitions={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [
                            "COMBO",
                            {"options": ["cube_only"]},
                        ],
                    }
                },
            }
        },
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    spec = snapshot.field_specs_by_alias["A"]["ksampler"]["sampler_name"]
    assert spec.field_type is None
    assert spec.field_info is None
    assert "options" not in spec.meta_info
    assert spec.value == "cube_only"
