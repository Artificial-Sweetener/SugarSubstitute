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

"""Tests for authoritative model-field kind classification."""

from __future__ import annotations

import pytest

from substitute.application.model_metadata import model_kind_for_field
from substitute.application.model_metadata.model_field_kind_resolver import (
    declared_model_kind_for_field,
    declared_model_kind_for_projected_field,
)


@pytest.mark.parametrize(
    ("class_type", "input_key", "expected_kind"),
    (
        ("CheckpointLoaderSimple", "ckpt_name", "checkpoints"),
        ("UNETLoader", "unet_name", "diffusion_models"),
        (
            "SimpleSyrup.SimpleLoadAnima",
            "diffusion_model",
            "diffusion_models",
        ),
        ("LoraLoader", "lora_name", "loras"),
        ("VAELoader", "vae_name", "vae"),
        ("SimpleSyrup.SimpleLoadCheckpoint", "ckpt_name", "checkpoints"),
        ("ControlNetLoader", "control_net_name", "controlnet"),
        ("UpscaleModelLoader", "model_name", "upscale_models"),
        ("CLIPLoader", "clip_name", "text_encoders"),
        ("DualCLIPLoader", "clip_name1", "text_encoders"),
        ("DualCLIPLoader", "clip_name2", "text_encoders"),
        ("SimpleSyrup.LoadUltralyticsModel", "model_name", "ultralytics"),
        ("UltralyticsDetectorProvider", "model_name", "ultralytics"),
    ),
)
def test_model_kind_for_field_resolves_known_typed_model_inputs(
    class_type: str,
    input_key: str,
    expected_kind: str,
) -> None:
    """Known typed model fields should resolve through one shared authority."""

    assert (
        model_kind_for_field(class_type=class_type, input_key=input_key)
        == expected_kind
    )


def test_model_kind_for_field_rejects_ambiguous_generic_model_input() -> None:
    """Generic model fields should not acquire a guessed catalog kind."""

    assert model_kind_for_field(class_type="CustomLoader", input_key="model") is None


def test_projected_model_kind_uses_hidden_wrapper_field_provenance() -> None:
    """A public subgraph UUID should retain its linked model-loader identity."""

    assert (
        declared_model_kind_for_projected_field(
            class_type="c6bb854c-c2ee-47a7-818d-f51684b83e0a",
            input_key="model_name",
            field_metadata={
                "body_node_type": "SimpleSyrup.LoadUltralyticsModel",
                "body_input_name": "model_name",
            },
        )
        == "ultralytics"
    )


@pytest.mark.parametrize(
    ("class_type", "input_key", "expected_kind"),
    (
        ("SimpleSyrup.SimpleLoadCheckpoint", "ckpt_name", "checkpoints"),
        ("SimpleSyrup.SimpleLoadCheckpoint", "vae_name", "vae"),
        ("SimpleSyrup.SimpleLoadAnima", "diffusion_model", "diffusion_models"),
        ("SimpleSyrup.SimpleLoadAnima", "vae", "vae"),
        ("SimpleSyrup.SimpleLoadFlux", "diffusion_model", "diffusion_models"),
        ("SimpleSyrup.SimpleLoadFlux", "vae", "vae"),
        ("SimpleSyrup.SimpleLoadFlux2", "diffusion_model", "diffusion_models"),
        ("SimpleSyrup.SimpleLoadFlux2", "vae", "vae"),
        ("SimpleSyrup.FutureLoader", "vae", "vae"),
    ),
)
def test_declared_model_kind_covers_simplesyrup_loader_namespace(
    class_type: str,
    input_key: str,
    expected_kind: str,
) -> None:
    """SimpleSyrup loader conventions should not require per-node registrations."""

    assert (
        declared_model_kind_for_field(
            class_type=class_type,
            input_key=input_key,
        )
        == expected_kind
    )


def test_declared_model_kind_does_not_apply_simplesyrup_keys_globally() -> None:
    """Namespace conventions must not reclassify unrelated choice fields."""

    assert (
        declared_model_kind_for_field(
            class_type="Unrelated.CustomLoader",
            input_key="vae",
        )
        is None
    )


def test_model_kind_for_field_preserves_unique_custom_field_inference() -> None:
    """Unique model-kind tokens should support custom model-backed nodes."""

    assert (
        model_kind_for_field(
            class_type="CustomLoader",
            input_key="primary_diffusion_model_name",
        )
        == "diffusion_models"
    )
