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

"""Tests for persisted CivitAI preferences."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.civitai import CivitaiPreferenceService
from substitute.domain.civitai import DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN
from substitute.infrastructure.persistence import FileCivitaiPreferenceRepository


def test_default_civitai_preferences_include_download_path_pattern(
    tmp_path: Path,
) -> None:
    """CivitAI preferences should default to base-model download organization."""

    service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(tmp_path / "settings"),
        preview_comfy_root=tmp_path / "diffusion_models",
    )

    preferences = service.load_preferences()
    preview = service.render_download_path_preview()

    assert preferences.download_path_pattern == DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN
    assert preview.display_path == str(
        tmp_path / "diffusion_models" / "Anima" / "anima_baseV10.safetensors"
    )


def test_old_civitai_preferences_load_with_default_download_path_pattern(
    tmp_path: Path,
) -> None:
    """Older preference files should receive the new pattern default."""

    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    (settings_dir / "civitai.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "metadata_lookup_enabled": False,
                "missing_model_lookup_enabled": True,
                "thumbnail_downloads_enabled": True,
                "thumbnail_safety_policy": "sfw_only",
                "downloads_enabled": True,
            }
        ),
        encoding="utf-8",
    )

    preferences = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(settings_dir)
    ).load_preferences()

    assert preferences.download_path_pattern == DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN


def test_civitai_preferences_save_download_path_pattern(tmp_path: Path) -> None:
    """Saving CivitAI preferences should persist the download pattern field."""

    settings_dir = tmp_path / "settings"
    service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(settings_dir),
        preview_comfy_root=tmp_path / "diffusion_models",
    )

    result = service.set_download_path_pattern("{creator}\\{file_name}")

    assert result.succeeded is True
    payload = json.loads((settings_dir / "civitai.json").read_text(encoding="utf-8"))
    assert payload["download_path_pattern"] == "{creator}\\{file_name}"


def test_invalid_civitai_download_pattern_does_not_overwrite_saved_preferences(
    tmp_path: Path,
) -> None:
    """Invalid CivitAI patterns should leave the last saved value intact."""

    service = CivitaiPreferenceService(
        FileCivitaiPreferenceRepository(tmp_path / "settings"),
        preview_comfy_root=tmp_path / "diffusion_models",
    )

    result = service.set_download_path_pattern("{model_type}\\{file_name}")

    assert result.succeeded is False
    assert (
        service.load_preferences().download_path_pattern
        == DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN
    )
