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

"""Tests for managed ComfyUI model-root ownership."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import runpy
import sys
from types import ModuleType

import pytest

from substitute.infrastructure.comfy.managed_model_root import (
    MANAGED_MODEL_ROOT_ENV,
    ManagedModelRootSource,
    ManagedModelRootStore,
    ensure_managed_model_root_startup_hook,
)


def test_missing_config_uses_comfy_default_models_folder(tmp_path: Path) -> None:
    """Managed model roots should default to ComfyUI's workspace models folder."""

    config = ManagedModelRootStore().load(tmp_path)

    assert config.effective_model_root == tmp_path.resolve() / "models"
    assert config.override_model_root is None
    assert config.source is ManagedModelRootSource.DEFAULT


def test_owned_model_root_config_is_read(tmp_path: Path) -> None:
    """Substitute's owned model-root file should define the model root."""

    model_root = tmp_path / "ImageGen Models"
    config_dir = tmp_path / ".substitute"
    config_dir.mkdir()
    (config_dir / "managed_model_root.json").write_text(
        json.dumps({"schema_version": 1, "model_root": str(model_root)}) + "\n",
        encoding="utf-8",
    )

    config = ManagedModelRootStore().load(tmp_path)

    assert config.effective_model_root == model_root.resolve()
    assert config.override_model_root == model_root.resolve()
    assert config.source is ManagedModelRootSource.SUBSTITUTE_MODEL_ROOT


def test_legacy_owned_extra_model_paths_base_path_is_read(tmp_path: Path) -> None:
    """Legacy owned YAML should be read until setup migrates it."""

    model_root = tmp_path / "ImageGen Models"
    (tmp_path / "extra_model_paths.yaml").write_text(
        "\n".join(
            (
                "substitute_shared_models:",
                f"  base_path: {model_root}",
                "  checkpoints: checkpoints",
                "",
            )
        ),
        encoding="utf-8",
    )

    config = ManagedModelRootStore().load(tmp_path)

    assert config.effective_model_root == model_root.resolve()
    assert config.override_model_root == model_root.resolve()
    assert config.source is ManagedModelRootSource.LEGACY_EXTRA_PATHS


def test_models_symlink_is_used_when_no_owned_override(tmp_path: Path) -> None:
    """Existing managed `models` symlinks should remain readable as legacy state."""

    model_root = tmp_path / "shared-models"
    model_root.mkdir()
    try:
        (tmp_path / "models").symlink_to(model_root, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Directory symlinks are unavailable on this system: {error}")

    config = ManagedModelRootStore().load(tmp_path)

    assert config.effective_model_root == model_root.resolve()
    assert config.source is ManagedModelRootSource.MODELS_SYMLINK


def test_save_custom_model_root_writes_owned_config_and_removes_legacy_yaml(
    tmp_path: Path,
) -> None:
    """Saving a custom model root should migrate away from owned extra paths."""

    config_path = tmp_path / "extra_model_paths.yaml"
    config_path.write_text(
        "\n".join(
            (
                "user_custom:",
                "  base_path: F:\\UserModels",
                "  loras: loras",
                "",
                "substitute_shared_models:",
                "  base_path: E:\\OldModels",
                "  checkpoints: checkpoints",
                "",
            )
        ),
        encoding="utf-8",
    )
    model_root = tmp_path / "custom-models"

    config = ManagedModelRootStore().save(tmp_path, model_root)

    payload = json.loads(
        (tmp_path / ".substitute" / "managed_model_root.json").read_text(
            encoding="utf-8"
        )
    )
    assert config.effective_model_root == model_root.resolve()
    assert payload["model_root"] == str(model_root.resolve())
    assert model_root.is_dir()
    remaining_yaml = config_path.read_text(encoding="utf-8")
    assert "user_custom:" in remaining_yaml
    assert "substitute_shared_models:" not in remaining_yaml


def test_save_default_model_root_removes_owned_config_and_empty_legacy_yaml(
    tmp_path: Path,
) -> None:
    """Saving the default should clear Substitute-owned model-root state."""

    model_root = tmp_path / "custom-models"
    ManagedModelRootStore().save(tmp_path, model_root)
    (tmp_path / "extra_model_paths.yaml").write_text(
        "\n".join(
            (
                "substitute_shared_models:",
                "  base_path: E:\\OldModels",
                "  checkpoints: checkpoints",
                "",
            )
        ),
        encoding="utf-8",
    )

    ManagedModelRootStore().save(tmp_path, tmp_path / "models")

    assert not (tmp_path / ".substitute" / "managed_model_root.json").exists()
    assert not (tmp_path / "extra_model_paths.yaml").exists()


def test_prestartup_hook_redirects_models_dir_and_registered_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Generated prestartup should make model-root paths behave like Comfy models."""

    workspace = tmp_path / "ComfyUI"
    old_root = workspace / "models"
    new_root = tmp_path / "ImageGen Models"
    hook_path = ensure_managed_model_root_startup_hook(workspace)
    folder_paths = _FolderPathsModule(old_root)
    monkeypatch.setitem(sys.modules, "folder_paths", folder_paths)
    monkeypatch.setenv(MANAGED_MODEL_ROOT_ENV, str(new_root))

    runpy.run_path(str(hook_path))

    assert folder_paths.models_dir == str(new_root.resolve())
    assert folder_paths.folder_names_and_paths["checkpoints"][0][0] == str(
        new_root.resolve() / "checkpoints"
    )
    assert folder_paths.folder_names_and_paths["custom_nodes"][0][0] == str(
        workspace / "custom_nodes"
    )
    assert folder_paths.filename_list_cache == {}
    assert folder_paths.cache_helper.cleared is True


def test_prestartup_hook_directory_imports_as_empty_custom_node(tmp_path: Path) -> None:
    """Generated hook directory should not fail Comfy's custom-node import pass."""

    workspace = tmp_path / "ComfyUI"
    hook_path = ensure_managed_model_root_startup_hook(workspace)
    init_path = hook_path.parent / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "SubstituteManagedModelRoot",
        init_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    assert module.NODE_CLASS_MAPPINGS == {}
    assert module.NODE_DISPLAY_NAME_MAPPINGS == {}


class _CacheHelper:
    """Record cache clearing requested by the generated hook."""

    def __init__(self) -> None:
        """Initialize the clear marker."""

        self.cleared = False

    def clear(self) -> None:
        """Record that the hook cleared Comfy's helper cache."""

        self.cleared = True


class _FolderPathsModule(ModuleType):
    """Provide the subset of Comfy's folder_paths module needed by the hook."""

    def __init__(self, models_dir: Path) -> None:
        """Initialize fake Comfy paths rooted at models_dir."""

        super().__init__("folder_paths")
        workspace = models_dir.parent
        self.models_dir = str(models_dir)
        self.folder_names_and_paths = {
            "checkpoints": ([str(models_dir / "checkpoints")], {".safetensors"}),
            "custom_nodes": ([str(workspace / "custom_nodes")], set()),
        }
        self.filename_list_cache: dict[
            str, tuple[list[str], dict[str, float], float]
        ] = {"checkpoints": ([], {}, 0.0)}
        self.cache_helper = _CacheHelper()
