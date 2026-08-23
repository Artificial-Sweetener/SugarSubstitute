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

"""Tests for SugarScript label metadata resolution."""

from __future__ import annotations

from collections import OrderedDict

from substitute.application.recipes.sugar_label_resolution import (
    SugarScriptLabelIndex,
    resolve_parsed_script_labels,
)
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.recipes import ParsedSugarScript


def test_resolve_parsed_script_labels_remaps_prompt_lora_hash_fields() -> None:
    """Inline LoRA hash metadata should follow node/input label resolution."""

    parsed = ParsedSugarScript(
        buffers=OrderedDict(
            {
                "A": OrderedDict(
                    {
                        "cube_id": "cube",
                        "nodes": {
                            "Prompt Node": {
                                "inputs": {
                                    "Prompt Text": "<lora:characters/midna:1.00>"
                                },
                            }
                        },
                    }
                )
            }
        ),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field={},
        prompt_lora_hashes_by_field={
            ("A", "Prompt Node", "Prompt Text"): {
                "characters/midna": "A" * 64,
            }
        },
        project_name=None,
    )
    label_index = SugarScriptLabelIndex.from_cube_graphs(
        {
            "A": {
                "nodes": {
                    "prompt": {
                        "class_type": "CLIPTextEncode",
                        "label": "Prompt Node",
                        "inputs": {"text": ""},
                    }
                },
                "definitions": {
                    "CLIPTextEncode": {
                        "input": {
                            "required": {"text": ["STRING", {"label": "Prompt Text"}]}
                        }
                    }
                },
            }
        }
    )

    resolved = resolve_parsed_script_labels(parsed, label_index)

    assert resolved.prompt_lora_hashes_by_field == {
        ("A", "prompt", "text"): {"characters/midna": "A" * 64}
    }


def test_resolve_parsed_script_labels_remaps_seed_control_metadata() -> None:
    """Seed-control comments should resolve visible node/input labels to machine keys."""

    seed_state = SeedControlState(SeedMode.FIXED)
    parsed = ParsedSugarScript(
        buffers=OrderedDict(
            {
                "A": OrderedDict(
                    {
                        "cube_id": "cube",
                        "nodes": {
                            "Sampler Node": {
                                "inputs": {"Seed Value": 1234},
                            }
                        },
                    }
                )
            }
        ),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={
            "A": {"Sampler Node": {"Seed Value": seed_state}}
        },
        override_control_states={"Seed Value": seed_state},
        model_hashes_by_field={},
        prompt_lora_hashes_by_field={},
        project_name=None,
    )
    label_index = SugarScriptLabelIndex.from_cube_graphs(
        {
            "A": {
                "nodes": {
                    "ksampler": {
                        "class_type": "KSampler",
                        "label": "Sampler Node",
                        "inputs": {"seed": 1234},
                    }
                },
                "definitions": {
                    "KSampler": {
                        "input": {
                            "required": {"seed": ["INT", {"label": "Seed Value"}]}
                        }
                    }
                },
            }
        }
    )

    resolved = resolve_parsed_script_labels(parsed, label_index)

    assert resolved.field_control_states_by_alias == {
        "A": {"ksampler": {"seed": seed_state}}
    }
    assert resolved.override_control_states == {"seed": seed_state}
