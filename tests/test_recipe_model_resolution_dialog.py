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

"""Tests for recipe missing-model resolver dialog copy helpers."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.application.recipes import RecipeModelCivitaiState
from substitute.presentation.dialogs.recipe_model_resolution_dialog import (
    _header_message,
    _reference_label,
    _thumbnail_url,
)


def test_recipe_model_reference_label_hides_internal_field_details() -> None:
    """Missing-model rows should show model names, not node/hash implementation data."""

    label = _reference_label(
        SimpleNamespace(
            alias="Anima/Text to Image",
            node_name="models",
            input_key="diffusion_model",
            kind="diffusion_models",
            sha256="A" * 64,
            value="Anima/model.safetensors",
            civitai_state=RecipeModelCivitaiState.FOUND,
            candidate=SimpleNamespace(
                model_name="Anima",
                name="anima_baseV10.safetensors",
            ),
        )
    )

    assert label == (
        "Anima/Text to Image uses Anima (anima_baseV10.safetensors), which is missing."
    )
    assert "Anima/Text to Image uses" in label
    assert "diffusion_model" not in label
    assert "diffusion_models" not in label
    assert "AAAA" not in label


def test_recipe_model_reference_label_describes_missing_value_plainly() -> None:
    """Rows without download candidates should still avoid internal identifiers."""

    label = _reference_label(
        SimpleNamespace(
            alias="Upscale",
            node_name="model_loader",
            input_key="model_name",
            kind="upscale_models",
            sha256="B" * 64,
            value=r"RealESRGAN\missing-upscaler.pth",
            civitai_state=RecipeModelCivitaiState.NO_SAFE_FILE,
            candidate=None,
        )
    )

    assert label == (
        "Upscale uses missing-upscaler.pth, but CivitAI did not offer a safe download."
    )
    assert "model_loader" not in label
    assert "model_name" not in label
    assert "upscale_models" not in label
    assert "BBBB" not in label


def test_recipe_model_header_copy_is_user_facing() -> None:
    """Resolver copy should explain the situation without backend terminology."""

    message = _header_message(downloads_enabled=True, can_download=True)

    assert "not in your current ComfyUI model folders" in message
    assert "download it for you" in message
    assert "install" not in message.casefold()
    assert "backend" not in message.casefold()
    assert "hash" not in message.casefold()


def test_recipe_model_thumbnail_url_uses_selected_candidate_url() -> None:
    """The dialog should only use thumbnail URLs already selected by resolution."""

    reference = SimpleNamespace(
        candidate=SimpleNamespace(thumbnail_url=" https://image.example/sfw.jpg ")
    )

    assert _thumbnail_url(reference) == "https://image.example/sfw.jpg"
    assert _thumbnail_url(SimpleNamespace(candidate=None)) is None
