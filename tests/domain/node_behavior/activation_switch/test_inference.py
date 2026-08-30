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

"""Verify activation-switch inference from live node definitions."""

from __future__ import annotations

from substitute.domain.node_behavior.inference import (
    infer_model_patch_switch,
    infer_sampler_worker_node,
)

NodeDefinition = dict[str, object]


def _model_patch_definition() -> NodeDefinition:
    """Return a MODEL-transform definition."""

    return {
        "input": {
            "required": {
                "model": ["MODEL", {"tooltip": "model input"}],
                "gain": ["FLOAT", {"default": 0.0}],
            },
            "optional": {},
        },
        "output": ["MODEL"],
    }


def _model_output_only_definition() -> NodeDefinition:
    """Return a definition without a MODEL input."""

    return {
        "input": {
            "required": {
                "ckpt_name": [
                    ["a.safetensors", "b.safetensors"],
                    {"default": "a.safetensors"},
                ],
            },
            "optional": {},
        },
        "output": ["MODEL", "CLIP", "VAE"],
    }


def _model_input_non_model_output_definition() -> NodeDefinition:
    """Return a definition without a MODEL output."""

    return {
        "input": {"required": {"model": ["MODEL", {}]}, "optional": {}},
        "output": ["LATENT"],
    }


def _sampler_worker_definition() -> NodeDefinition:
    """Return a sampler-worker-shaped definition."""

    return {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "steps": ["INT", {"default": 20}],
                "denoise": ["FLOAT", {"default": 1.0}],
            },
            "optional": {},
        },
        "output": ["LATENT"],
    }


def _sampler_worker_with_text_denoise_definition() -> NodeDefinition:
    """Return a malformed sampler-worker-shaped definition."""

    return {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "steps": ["INT", {"default": 20}],
                "denoise": ["STRING", {"default": "1.0"}],
            },
            "optional": {},
        },
        "output": ["LATENT"],
    }


def test_infer_enabled_switch_for_model_patch() -> None:
    """Recognize a MODEL in/out transform."""

    assert infer_model_patch_switch(_model_patch_definition()) is True


def test_infer_enabled_switch_rejects_missing_model_input() -> None:
    """Reject a definition without a MODEL input."""

    assert infer_model_patch_switch(_model_output_only_definition()) is False


def test_infer_enabled_switch_rejects_missing_model_output() -> None:
    """Reject a definition without a MODEL output."""

    assert infer_model_patch_switch(_model_input_non_model_output_definition()) is False


def test_infer_enabled_switch_rejects_invalid_definition() -> None:
    """Reject unavailable and empty definitions."""

    assert infer_model_patch_switch(None) is False
    assert infer_model_patch_switch({}) is False


def test_infer_sampler_worker_from_typed_definition() -> None:
    """Recognize numeric sampler-worker inputs."""

    assert (
        infer_sampler_worker_node(
            _sampler_worker_definition(),
            input_keys=("model", "steps", "denoise"),
        )
        is True
    )


def test_infer_sampler_worker_from_input_keys_fallback() -> None:
    """Recognize sampler-worker inputs without a live definition."""

    assert infer_sampler_worker_node(None, input_keys=("steps", "denoise")) is True


def test_infer_sampler_worker_rejects_missing_required_input() -> None:
    """Require both sampler-worker input names."""

    assert infer_sampler_worker_node(None, input_keys=("steps",)) is False


def test_infer_sampler_worker_rejects_invalid_scalar_type() -> None:
    """Reject a nonnumeric denoise definition."""

    assert (
        infer_sampler_worker_node(
            _sampler_worker_with_text_denoise_definition(),
            input_keys=("model", "steps", "denoise"),
        )
        is False
    )
