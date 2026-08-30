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

"""Prompt-role inference contracts."""

from __future__ import annotations


from substitute.application.node_behavior import (
    CardMode,
    FieldPresentation,
    PromptRole,
)
from tests.support.node_behavior import (
    build_behavior_snapshot,
    cube_state,
)


def test_prompt_card_icons_distinguish_positive_and_negative_prompts() -> None:
    """Positive prompt keeps edit while negative prompt uses the eraser icon."""

    cube = cube_state(
        nodes={
            "positive_prompt": {
                "class_type": "CLIPTextEncode",
                "inputs": {"prompt_template": "quality"},
            },
            "negative_prompt": {
                "class_type": "CLIPTextEncode",
                "inputs": {"prompt_template": "blurry"},
            },
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

    assert (
        snapshot.resolved_nodes_by_alias["A"]["positive_prompt"].card.icon_name
        == "edit"
    )
    assert (
        snapshot.resolved_nodes_by_alias["A"]["negative_prompt"].card.icon_name
        == "eraser"
    )


def test_inferred_negative_prompt_card_uses_eraser_icon() -> None:
    """Titled custom negative prompt cards should use the eraser icon."""

    cube = cube_state(
        nodes={
            "node_18": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "blurry"},
                "_meta": {"title": "Negative Prompt"},
            },
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "CLIPTextEncode": {
                "input": {
                    "required": {
                        "text": ["STRING", {"multiline": True}],
                    }
                }
            }
        },
    )

    assert snapshot.resolved_nodes_by_alias["A"]["node_18"].card.icon_name == "eraser"


def test_prompt_title_inference_is_isolated_per_editor_section() -> None:
    """Prompt behavior in one cube section must not affect another section."""

    definitions = {
        "CustomPrompt": {
            "input": {
                "required": {
                    "text": ["STRING", {"multiline": True}],
                }
            }
        }
    }
    positive = cube_state(
        nodes={
            "shared_id": {
                "class_type": "CustomPrompt",
                "inputs": {"text": "quality"},
                "_meta": {"title": "Positive Prompt"},
            }
        }
    )
    negative = cube_state(
        nodes={
            "shared_id": {
                "class_type": "CustomPrompt",
                "inputs": {"text": "blurry"},
                "_meta": {"title": "Negative Prompt"},
            }
        }
    )

    snapshot = build_behavior_snapshot(
        cube_states={"positive": positive, "negative": negative},
        stack_order=["positive", "negative"],
        definitions_by_class=definitions,
    )

    positive_field = snapshot.resolved_nodes_by_alias["positive"]["shared_id"].fields[
        "text"
    ]
    negative_field = snapshot.resolved_nodes_by_alias["negative"]["shared_id"].fields[
        "text"
    ]
    assert positive_field.prompt is not None
    assert positive_field.prompt.role == PromptRole.POSITIVE
    assert negative_field.prompt is not None
    assert negative_field.prompt.role == PromptRole.NEGATIVE


def test_behavior_snapshot_infers_prompt_from_conditioning_topology() -> None:
    """Unknown encoders should resolve through typed conditioning sink semantics."""

    cube = cube_state(
        nodes={
            "encoder": {
                "class_type": "UnknownTextEncoder",
                "inputs": {"text": "quality"},
            },
            "sampler": {
                "class_type": "UnknownSampler",
                "inputs": {"positive": ["encoder", 0]},
            },
        }
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UnknownTextEncoder": {
                "input": {"required": {"text": ["STRING", {"multiline": True}]}},
                "output": ["CONDITIONING"],
            },
            "UnknownSampler": {
                "input": {"required": {"positive": ["CONDITIONING", {}]}}
            },
        },
    )

    behavior = snapshot.resolved_nodes_by_alias["A"]["encoder"]
    assert behavior.card.card_mode == CardMode.PROMPT
    assert behavior.fields["text"].presentation == FieldPresentation.PROMPT_BOX
    assert behavior.fields["text"].prompt is not None
    assert behavior.fields["text"].prompt.role == PromptRole.POSITIVE


def test_behavior_snapshot_withholds_dual_role_conditioning_source() -> None:
    """A shared prompt source should remain standard when polarity is ambiguous."""

    cube = cube_state(
        nodes={
            "encoder": {
                "class_type": "UnknownTextEncoder",
                "inputs": {"text": "shared"},
            },
            "sampler": {
                "class_type": "UnknownSampler",
                "inputs": {
                    "positive": ["encoder", 0],
                    "negative": ["encoder", 0],
                },
            },
        }
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UnknownTextEncoder": {
                "input": {"required": {"text": ["STRING", {"multiline": True}]}},
                "output": ["CONDITIONING"],
            },
            "UnknownSampler": {
                "input": {
                    "required": {
                        "positive": ["CONDITIONING", {}],
                        "negative": ["CONDITIONING", {}],
                    }
                }
            },
        },
    )

    behavior = snapshot.resolved_nodes_by_alias["A"]["encoder"]
    assert behavior.card.card_mode == CardMode.STANDARD
    assert behavior.fields["text"].presentation == FieldPresentation.STANDARD
    assert behavior.fields["text"].prompt is None


def test_behavior_snapshot_never_traces_prompt_roles_across_cube_sections() -> None:
    """A sink in another cube must not classify an encoder-only cube field."""

    encoder_cube = cube_state(
        nodes={
            "encoder": {
                "class_type": "UnknownTextEncoder",
                "inputs": {"text": "quality"},
            }
        }
    )
    sink_cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "UnknownSampler",
                "inputs": {"positive": ["encoder", 0]},
            }
        }
    )
    snapshot = build_behavior_snapshot(
        cube_states={"encoder_cube": encoder_cube, "sink_cube": sink_cube},
        stack_order=["encoder_cube", "sink_cube"],
        definitions_by_class={
            "UnknownTextEncoder": {
                "input": {"required": {"text": ["STRING", {"multiline": True}]}},
                "output": ["CONDITIONING"],
            },
            "UnknownSampler": {
                "input": {"required": {"positive": ["CONDITIONING", {}]}}
            },
        },
    )

    field = snapshot.resolved_nodes_by_alias["encoder_cube"]["encoder"].fields["text"]
    assert field.prompt is None
    assert field.presentation == FieldPresentation.STANDARD


def test_literal_prompt_name_remains_authoritative_over_graph_evidence() -> None:
    """The established literal prompt alias should not be reclassified by topology."""

    cube = cube_state(
        nodes={
            "positive_prompt": {
                "class_type": "UnknownTextEncoder",
                "inputs": {"prompt_template": "quality"},
                "_meta": {"title": "Negative Prompt"},
            },
            "sampler": {
                "class_type": "UnknownSampler",
                "inputs": {"negative": ["positive_prompt", 0]},
            },
        }
    )
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "UnknownTextEncoder": {
                "input": {
                    "required": {"prompt_template": ["STRING", {"multiline": True}]}
                },
                "output": ["CONDITIONING"],
            },
            "UnknownSampler": {
                "input": {"required": {"negative": ["CONDITIONING", {}]}}
            },
        },
    )

    field = snapshot.resolved_nodes_by_alias["A"]["positive_prompt"].fields[
        "prompt_template"
    ]
    assert field.prompt is not None
    assert field.prompt.role == PromptRole.POSITIVE
