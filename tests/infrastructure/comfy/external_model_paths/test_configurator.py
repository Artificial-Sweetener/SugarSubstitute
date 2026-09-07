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

"""Verify preservation-safe Comfy external model-path persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.infrastructure.comfy.external_model_paths_configurator import (
    ComfyExternalModelPathsConfigurator,
    ExternalModelPathsConfigurationError,
)


def _webui_models(tmp_path: Path) -> Path:
    """Create one representative WebUI models root."""

    models = tmp_path / "webui" / "models"
    for name in (
        "Stable-diffusion",
        "diffusion_models",
        "Ultralytics",
        "ESRGAN",
        "RealESRGAN",
    ):
        (models / name).mkdir(parents=True)
    return models


def test_configurator_preserves_user_yaml_and_writes_supported_mappings(
    tmp_path: Path,
) -> None:
    """Append one owned block without rewriting an existing user section."""

    workspace = tmp_path / "ComfyUI"
    workspace.mkdir()
    config = workspace / "extra_model_paths.yaml"
    user_yaml = "user_models:\n  checkpoints: D:/models/checkpoints\n"
    config.write_text(user_yaml, encoding="utf-8")
    models = _webui_models(tmp_path)

    configurator = ComfyExternalModelPathsConfigurator()
    configurator.configure(workspace, models)

    content = config.read_text(encoding="utf-8")
    assert content.startswith(user_yaml)
    assert "sugarsubstitute_connected_webui_models:" in content
    assert "  checkpoints: |" in content
    assert f"    {(models / 'Stable-diffusion').resolve().as_posix()}" in content
    assert "  diffusion_models: |" in content
    assert "  ultralytics: |" in content
    assert "  upscale_models: |" in content
    assert content.count("  upscale_models: |") == 1
    assert configurator.load_models_root(workspace) == models.resolve()


def test_configurator_replaces_only_its_owned_block(tmp_path: Path) -> None:
    """Update a selection without accumulating duplicate configuration."""

    workspace = tmp_path / "ComfyUI"
    workspace.mkdir()
    first = _webui_models(tmp_path / "first")
    second = _webui_models(tmp_path / "second")
    configurator = ComfyExternalModelPathsConfigurator()

    configurator.configure(workspace, first)
    configurator.configure(workspace, second)

    content = (workspace / "extra_model_paths.yaml").read_text(encoding="utf-8")
    assert first.resolve().as_posix() not in content
    assert second.resolve().as_posix() in content
    assert content.count("BEGIN SUGARSUBSTITUTE") == 1


def test_configurator_disconnects_without_deleting_user_yaml(tmp_path: Path) -> None:
    """Remove the owned block while retaining unrelated configuration exactly."""

    workspace = tmp_path / "ComfyUI"
    workspace.mkdir()
    config = workspace / "extra_model_paths.yaml"
    config.write_text("user_models:\n  checkpoints: D:/models\n", encoding="utf-8")
    configurator = ComfyExternalModelPathsConfigurator()
    configurator.configure(workspace, _webui_models(tmp_path))

    configurator.configure(workspace, None)

    assert config.read_text(encoding="utf-8") == (
        "user_models:\n  checkpoints: D:/models\n"
    )


def test_configurator_removes_app_only_file_when_disconnected(tmp_path: Path) -> None:
    """Leave no empty Comfy configuration behind after removing the connection."""

    workspace = tmp_path / "ComfyUI"
    workspace.mkdir()
    configurator = ComfyExternalModelPathsConfigurator()
    configurator.configure(workspace, _webui_models(tmp_path))

    configurator.configure(workspace, None)

    assert not (workspace / "extra_model_paths.yaml").exists()


def test_configurator_refuses_unmarked_reserved_section(tmp_path: Path) -> None:
    """Fail closed rather than overwrite a coincidentally matching user key."""

    workspace = tmp_path / "ComfyUI"
    workspace.mkdir()
    (workspace / "extra_model_paths.yaml").write_text(
        "sugarsubstitute_connected_webui_models:\n  checkpoints: D:/mine\n",
        encoding="utf-8",
    )

    with pytest.raises(ExternalModelPathsConfigurationError):
        ComfyExternalModelPathsConfigurator().configure(
            workspace,
            _webui_models(tmp_path),
        )


def test_configurator_clears_mapping_for_an_ordinary_empty_models_root(
    tmp_path: Path,
) -> None:
    """Allow one custom Comfy models folder without requiring WebUI structure."""

    workspace = tmp_path / "ComfyUI"
    workspace.mkdir()
    configurator = ComfyExternalModelPathsConfigurator()
    configurator.configure(workspace, _webui_models(tmp_path))
    ordinary_models = tmp_path / "ordinary-models"
    ordinary_models.mkdir()

    configurator.configure(workspace, ordinary_models)

    assert not (workspace / "extra_model_paths.yaml").exists()
