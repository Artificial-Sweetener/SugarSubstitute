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

"""Verify bounded WebUI model-folder detection."""

from __future__ import annotations

from pathlib import Path

import pytest
from sugarsubstitute_shared.model_discovery import ModelArtifactKind

from substitute.infrastructure.comfy.webui_model_library_detector import (
    WebUiModelLibraryDetectionError,
    WebUiModelLibraryDetector,
)


def test_detector_maps_only_supported_direct_model_directories(tmp_path: Path) -> None:
    """Map heavyweight shared assets without treating extensions as model roots."""

    models = tmp_path / "models"
    expected = {
        name: (models / name).resolve()
        for name in (
            "Stable-diffusion",
            "UNET",
            "Ultralytics",
            "ESRGAN",
            "RealESRGAN",
        )
    }
    for path in expected.values():
        path.mkdir(parents=True)
    (models / "Lora").mkdir()
    (models / "VAE").mkdir()
    (models / "extensions" / "nested" / "Stable-diffusion").mkdir(parents=True)

    library = WebUiModelLibraryDetector().detect(models)

    assert library.models_root == models.resolve()
    assert library.checkpoints == (expected["Stable-diffusion"],)
    assert library.diffusion_models == (expected["UNET"],)
    assert library.ultralytics == (expected["Ultralytics"],)
    assert library.upscale_models == (
        expected["ESRGAN"],
        expected["RealESRGAN"],
    )


def test_detector_accepts_webui_root_containing_models_directory(
    tmp_path: Path,
) -> None:
    """Let the folder picker tolerate selecting one level above models."""

    checkpoint_root = tmp_path / "models" / "Stable-diffusion"
    checkpoint_root.mkdir(parents=True)

    library = WebUiModelLibraryDetector().detect(tmp_path)

    assert library.models_root == (tmp_path / "models").resolve()
    assert library.checkpoints == (checkpoint_root.resolve(),)


def test_detector_matches_directory_names_case_insensitively(tmp_path: Path) -> None:
    """Recognize Windows model folders without relying on their display casing."""

    yolo = tmp_path / "YoLo"
    upscalers = tmp_path / "UPSCale_MODELS"
    yolo.mkdir()
    upscalers.mkdir()

    library = WebUiModelLibraryDetector().detect(tmp_path)

    assert library.ultralytics == (yolo.resolve(),)
    assert library.upscale_models == (upscalers.resolve(),)


def test_detector_does_not_descend_into_extensions(tmp_path: Path) -> None:
    """Reject folders whose only apparent models belong to extension internals."""

    (tmp_path / "extensions" / "plugin" / "models" / "Stable-diffusion").mkdir(
        parents=True
    )

    with pytest.raises(WebUiModelLibraryDetectionError):
        WebUiModelLibraryDetector().detect(tmp_path)


def test_install_destination_reuses_the_webui_category_in_place(tmp_path: Path) -> None:
    """Put new models where the selected WebUI will continue to discover them."""

    checkpoints = tmp_path / "models" / "Stable-diffusion"
    diffusion_models = tmp_path / "models" / "UNET"
    checkpoints.mkdir(parents=True)
    diffusion_models.mkdir()
    detector = WebUiModelLibraryDetector()

    assert (
        detector.install_destination(tmp_path / "models", ModelArtifactKind.CHECKPOINTS)
        == checkpoints.resolve()
    )
    assert (
        detector.install_destination(
            tmp_path / "models", ModelArtifactKind.DIFFUSION_MODELS
        )
        == diffusion_models.resolve()
    )
