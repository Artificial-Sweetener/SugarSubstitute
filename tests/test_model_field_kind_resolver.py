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


def test_model_kind_for_field_preserves_unique_custom_field_inference() -> None:
    """Unique model-kind tokens should support custom model-backed nodes."""

    assert (
        model_kind_for_field(
            class_type="CustomLoader",
            input_key="primary_diffusion_model_name",
        )
        == "diffusion_models"
    )
