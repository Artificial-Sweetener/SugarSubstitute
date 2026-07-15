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

"""Tests for CivitAI download organization path rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.civitai import (
    CivitaiDownloadPathTemplateError,
    CivitaiDownloadPathTemplateRenderer,
)
from substitute.domain.civitai import CivitaiDownloadPathRenderContext


def test_civitai_download_renderer_accepts_default_pattern() -> None:
    """Default CivitAI download paths should render under the Comfy root."""

    result = CivitaiDownloadPathTemplateRenderer().preview_path(
        path_pattern="{base_model}\\{file_name}",
        context=_context(),
    )

    assert result.relative_path == Path("Anima") / "anima_baseV10.safetensors"
    assert result.display_path.endswith(
        "diffusion_models\\Anima\\anima_baseV10.safetensors"
    )


def test_civitai_download_renderer_rejects_unknown_and_malformed_tokens() -> None:
    """CivitAI download patterns should fail clearly for unsupported syntax."""

    renderer = CivitaiDownloadPathTemplateRenderer()

    with pytest.raises(CivitaiDownloadPathTemplateError, match="Unknown"):
        renderer.validate_pattern("{model_type}\\{file_name}")
    with pytest.raises(CivitaiDownloadPathTemplateError, match="malformed"):
        renderer.validate_pattern("{base_model\\{file_name}")


def test_civitai_download_renderer_rejects_absolute_and_traversal_paths() -> None:
    """CivitAI download patterns must stay relative to the model root."""

    renderer = CivitaiDownloadPathTemplateRenderer()

    with pytest.raises(CivitaiDownloadPathTemplateError, match="relative"):
        renderer.validate_pattern("E:\\Models\\{file_name}")
    with pytest.raises(CivitaiDownloadPathTemplateError, match="traversal"):
        renderer.preview_path(path_pattern="..\\{file_name}", context=_context())


def test_civitai_download_renderer_sanitizes_token_values() -> None:
    """Unsafe CivitAI metadata should become safe path components."""

    result = CivitaiDownloadPathTemplateRenderer().preview_path(
        path_pattern="{creator}\\{model_name}\\{file_name}",
        context=CivitaiDownloadPathRenderContext(
            kind="diffusion_models",
            comfy_root=Path("E:/ImageGen Models/diffusion_models"),
            base_model="Anima",
            model_name="Bad:Model/Name",
            version_name="base-v1.0",
            creator="Some<Creator>",
            file_name="../anime:base.safetensors",
        ),
    )

    assert result.relative_path == (
        Path("Some_Creator") / "Bad_Model_Name" / "anime_base.safetensors"
    )


def _context() -> CivitaiDownloadPathRenderContext:
    """Return a deterministic Anima preview context."""

    return CivitaiDownloadPathRenderContext(
        kind="diffusion_models",
        comfy_root=Path("E:/ImageGen Models/diffusion_models"),
        base_model="Anima",
        model_name="Anima",
        version_name="base-v1.0",
        creator="CivitAI Creator",
        file_name="anima_baseV10.safetensors",
    )
