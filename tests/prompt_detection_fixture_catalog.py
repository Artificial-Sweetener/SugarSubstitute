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

"""Define deterministic expectations for genuine managed Comfy templates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from substitute.domain.node_behavior import PromptRole
from tests.managed_comfy_harness_layout import ManagedComfyHarnessLayout


@dataclass(frozen=True, slots=True, order=True)
class ExpectedPromptField:
    """Describe one field expected to receive prompt behavior."""

    node_name: str
    field_key: str
    role: PromptRole


@dataclass(frozen=True, slots=True)
class PromptDetectionFixture:
    """Bind a workflow fixture to recorded metadata and exact expectations."""

    name: str
    path: Path
    node_definitions: Mapping[str, Mapping[str, object]]
    expected_prompts: tuple[ExpectedPromptField, ...]
    expected_standard_fields: tuple[tuple[str, str], ...] = ()
    expected_ambiguities: tuple[tuple[str, tuple[str, ...]], ...] = ()
    expected_context_anchors: tuple[str, ...] = ()
    expected_opening_cards: tuple[str, ...] = ()


def managed_prompt_detection_fixtures(
    repository_root: Path,
) -> tuple[PromptDetectionFixture, ...]:
    """Return the real-template prompt-detection corpus for this repository."""

    layout = ManagedComfyHarnessLayout.resolve(repository_root)
    return (
        PromptDetectionFixture(
            name="managed_sdxl_primitive_prompts",
            path=layout.image_template_root() / "sdxl_simple_example.json",
            node_definitions=_core_image_definitions(),
            expected_prompts=(
                ExpectedPromptField("50", "text", PromptRole.NEGATIVE),
                ExpectedPromptField("51", "text", PromptRole.POSITIVE),
            ),
            expected_context_anchors=("10", "11"),
            expected_opening_cards=("51", "50"),
        ),
        PromptDetectionFixture(
            name="qwen_inline_encoder_prompts",
            path=repository_root
            / "comfyui"
            / "blueprints"
            / "Text to Image (Qwen-Image).json",
            node_definitions=_core_image_definitions(),
            expected_prompts=(
                ExpectedPromptField("76:6", "text", PromptRole.POSITIVE),
                ExpectedPromptField("76:7", "text", PromptRole.NEGATIVE),
            ),
            expected_context_anchors=("76:3",),
            expected_opening_cards=("76:6", "76:7"),
        ),
        PromptDetectionFixture(
            name="firered_custom_encoder_prompts",
            path=repository_root
            / "comfyui"
            / "blueprints"
            / "Image Edit (FireRed Image Edit 1.1).json",
            node_definitions={
                **_core_image_definitions(),
                "TextEncodeQwenImageEditPlus": {
                    "input": {
                        "required": {
                            "clip": ["CLIP"],
                            "vae": ["VAE"],
                            "image1": ["IMAGE"],
                            "image2": ["IMAGE"],
                            "image3": ["IMAGE"],
                            "prompt": [
                                "STRING",
                                {"multiline": True, "dynamicPrompts": True},
                            ],
                        }
                    },
                    "output": ["CONDITIONING"],
                },
            },
            expected_prompts=(
                ExpectedPromptField("172:117", "prompt", PromptRole.NEGATIVE),
                ExpectedPromptField("172:118", "prompt", PromptRole.POSITIVE),
            ),
            expected_context_anchors=("172:130",),
            expected_opening_cards=("172:118", "172:117"),
        ),
        PromptDetectionFixture(
            name="wan_shared_pair_reaches_two_stage_anchors",
            path=repository_root
            / "comfyui"
            / "blueprints"
            / "Text to Video (Wan 2.2).json",
            node_definitions=_core_image_definitions(),
            expected_prompts=(
                ExpectedPromptField("114:72", "text", PromptRole.NEGATIVE),
                ExpectedPromptField("114:89", "text", PromptRole.POSITIVE),
            ),
            expected_context_anchors=("114:81", "114:78"),
            expected_opening_cards=("114:89", "114:72"),
        ),
        PromptDetectionFixture(
            name="flux_zeroed_conditioning_is_ambiguous",
            path=repository_root
            / "comfyui"
            / "blueprints"
            / "Text to Image (Flux.1 Dev).json",
            node_definitions={
                **_core_image_definitions(),
                "ConditioningZeroOut": {
                    "input": {
                        "required": {
                            "conditioning": ["CONDITIONING"],
                        }
                    },
                    "output": ["CONDITIONING"],
                },
            },
            expected_prompts=(),
            expected_standard_fields=(("193:45", "text"),),
            expected_ambiguities=(("conflicting_roles", ("193:45.text",)),),
        ),
        PromptDetectionFixture(
            name="ambiguous_conditioning_and_non_prompt_text",
            path=repository_root
            / "tests"
            / "fixtures"
            / "prompt_detection"
            / "ambiguous_conditioning.json",
            node_definitions={
                "UnknownTextEncoder": {
                    "input": {
                        "required": {
                            "text": ["STRING", {"multiline": True}],
                        }
                    },
                    "output": ["CONDITIONING"],
                },
                "UnknownSampler": {
                    "input": {
                        "required": {
                            "positive": ["CONDITIONING"],
                            "negative": ["CONDITIONING"],
                        }
                    },
                    "output": [],
                },
                "MetadataWriter": {
                    "input": {
                        "required": {
                            "description": ["STRING", {"multiline": True}],
                        }
                    },
                    "output": [],
                },
            },
            expected_prompts=(),
            expected_standard_fields=(("1", "text"), ("3", "description")),
            expected_ambiguities=(("conflicting_roles", ("1.text",)),),
        ),
    )


def deterministic_prompt_detection_fixtures(
    repository_root: Path,
) -> tuple[PromptDetectionFixture, ...]:
    """Return repository-owned fixtures suitable for the complete test suite."""

    fixture_root = repository_root / "tests" / "fixtures"
    return (
        PromptDetectionFixture(
            name="deterministic_sdxl_primitive_prompts",
            path=(
                fixture_root / "direct_workflows" / "deterministic_sdxl_projection.json"
            ),
            node_definitions=_core_image_definitions(),
            expected_prompts=(
                ExpectedPromptField("50", "text", PromptRole.NEGATIVE),
                ExpectedPromptField("51", "text", PromptRole.POSITIVE),
            ),
            expected_context_anchors=("10", "11"),
            expected_opening_cards=("51", "50"),
        ),
        PromptDetectionFixture(
            name="ambiguous_conditioning_and_non_prompt_text",
            path=(fixture_root / "prompt_detection" / "ambiguous_conditioning.json"),
            node_definitions={
                "UnknownTextEncoder": {
                    "input": {
                        "required": {
                            "text": ["STRING", {"multiline": True}],
                        }
                    },
                    "output": ["CONDITIONING"],
                },
                "UnknownSampler": {
                    "input": {
                        "required": {
                            "positive": ["CONDITIONING"],
                            "negative": ["CONDITIONING"],
                        }
                    },
                    "output": [],
                },
                "MetadataWriter": {
                    "input": {
                        "required": {
                            "description": ["STRING", {"multiline": True}],
                        }
                    },
                    "output": [],
                },
            },
            expected_prompts=(),
            expected_standard_fields=(("1", "text"), ("3", "description")),
            expected_ambiguities=(("conflicting_roles", ("1.text",)),),
        ),
    )


def _core_image_definitions() -> dict[str, Mapping[str, object]]:
    """Return stable core metadata needed to interpret the selected templates."""

    return {
        "CheckpointLoaderSimple": {
            "input": {
                "required": {
                    "ckpt_name": [
                        [
                            "sd_xl_base_1.0.safetensors",
                            "sd_xl_refiner_1.0.safetensors",
                        ]
                    ]
                }
            },
            "output": ["MODEL", "CLIP", "VAE"],
        },
        "EmptyLatentImage": {
            "input": {
                "required": {
                    "width": ["INT", {"default": 512, "min": 16, "max": 16384}],
                    "height": ["INT", {"default": 512, "min": 16, "max": 16384}],
                    "batch_size": ["INT", {"default": 1, "min": 1, "max": 4096}],
                }
            },
            "output": ["LATENT"],
        },
        "CLIPTextEncode": {
            "input": {
                "required": {
                    "text": [
                        "STRING",
                        {"multiline": True, "dynamicPrompts": True},
                    ],
                    "clip": ["CLIP"],
                }
            },
            "output": ["CONDITIONING"],
        },
        "KSampler": {
            "input": {
                "required": {
                    "model": ["MODEL"],
                    "positive": ["CONDITIONING"],
                    "negative": ["CONDITIONING"],
                    "latent_image": ["LATENT"],
                    "seed": ["INT", {"default": 0, "min": 0}],
                    "steps": ["INT", {"default": 20, "min": 1}],
                    "cfg": ["FLOAT", {"default": 8.0, "min": 0.0}],
                    "sampler_name": [["euler"]],
                    "scheduler": [["normal"]],
                    "denoise": ["FLOAT", {"default": 1.0, "min": 0.0}],
                }
            },
            "output": ["LATENT"],
        },
        "KSamplerAdvanced": {
            "input": {
                "required": {
                    "add_noise": [["enable", "disable"]],
                    "noise_seed": ["INT", {"default": 0, "min": 0}],
                    "steps": ["INT", {"default": 20, "min": 1}],
                    "cfg": ["FLOAT", {"default": 8.0, "min": 0.0}],
                    "sampler_name": [["euler"]],
                    "scheduler": [["normal"]],
                    "start_at_step": ["INT", {"default": 0, "min": 0}],
                    "end_at_step": ["INT", {"default": 10000, "min": 0}],
                    "return_with_leftover_noise": [["disable", "enable"]],
                    "model": ["MODEL"],
                    "positive": ["CONDITIONING"],
                    "negative": ["CONDITIONING"],
                    "latent_image": ["LATENT"],
                }
            },
            "output": ["LATENT"],
        },
        "VAEDecode": {
            "input": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}},
            "output": ["IMAGE"],
        },
        "SaveImage": {
            "output_node": True,
            "input": {
                "required": {
                    "images": ["IMAGE"],
                    "filename_prefix": ["STRING", {"default": "ComfyUI"}],
                }
            },
            "output": [],
        },
    }


__all__ = [
    "ExpectedPromptField",
    "PromptDetectionFixture",
    "deterministic_prompt_detection_fixtures",
    "managed_prompt_detection_fixtures",
]
