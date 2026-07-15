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

"""Tests for install-root configuration persistence."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.onboarding.installation_service import InstallationService
from substitute.infrastructure.onboarding.file_installation_repository import (
    FileInstallationConfigurationRepository,
)


def test_installation_repository_returns_default_install_layout_when_missing(
    tmp_path: Path,
) -> None:
    """Missing installation config should synthesize the visible default layout."""

    repository = FileInstallationConfigurationRepository(tmp_path)

    configuration = repository.load()

    assert configuration.installation_root == tmp_path.resolve()
    assert configuration.user_dir == tmp_path / "user"
    assert configuration.user_settings_dir == tmp_path / "user" / "settings"
    assert configuration.projects_dir == tmp_path / "user" / "projects"
    assert configuration.outputs_dir == tmp_path / "user" / "outputs"
    assert configuration.sugar_scripts_dir == configuration.projects_dir
    assert configuration.wildcards_dir == tmp_path / "user" / "wildcards"
    assert configuration.appdata_dir == tmp_path / "appdata"
    assert configuration.session_dir == tmp_path / "appdata" / "session"
    assert configuration.cache_dir == tmp_path / "appdata" / "cache"
    assert configuration.diagnostics_dir == tmp_path / "appdata" / "diagnostics"
    assert configuration.logs_dir == tmp_path / "appdata" / "diagnostics" / "logs"
    assert configuration.runtime_state_dir == tmp_path / "appdata" / "runtime_state"
    assert (
        configuration.model_metadata_dir
        == tmp_path / "appdata" / "cache" / "model_metadata"
    )
    assert configuration.runtime_dir == tmp_path / "runtime"
    assert configuration.default_managed_comfy_dir == tmp_path / "comfyui"


def test_installation_repository_round_trips_custom_paths(tmp_path: Path) -> None:
    """Saved installation config should load back with the same visible paths."""

    repository = FileInstallationConfigurationRepository(tmp_path)
    configuration = repository.load()
    updated_configuration = type(configuration)(
        installation_root=configuration.installation_root,
        user_dir=tmp_path / "profiles" / "main",
        user_settings_dir=tmp_path / "profiles" / "main" / "settings",
        projects_dir=tmp_path / "workflows",
        outputs_dir=tmp_path / "profiles" / "main" / "outputs",
        sugar_scripts_dir=tmp_path / "profiles" / "main" / "sugarscripts",
        wildcards_dir=tmp_path / "profiles" / "main" / "wildcards",
        appdata_dir=tmp_path / "app-storage",
        session_dir=tmp_path / "app-storage" / "session",
        cache_dir=tmp_path / "app-storage" / "cache",
        diagnostics_dir=tmp_path / "app-storage" / "diagnostics",
        logs_dir=tmp_path / "app-storage" / "diagnostics" / "logs",
        runtime_state_dir=tmp_path / "app-storage" / "runtime-state",
        model_metadata_dir=tmp_path / "app-storage" / "cache" / "model_metadata",
        runtime_dir=tmp_path / "python-runtime",
        default_managed_comfy_dir=tmp_path / "managed-comfy",
    )

    repository.save(updated_configuration)

    reloaded_configuration = repository.load()

    assert reloaded_configuration == type(updated_configuration)(
        installation_root=updated_configuration.installation_root,
        user_dir=updated_configuration.user_dir,
        user_settings_dir=updated_configuration.user_settings_dir,
        projects_dir=updated_configuration.projects_dir,
        outputs_dir=updated_configuration.outputs_dir,
        sugar_scripts_dir=updated_configuration.projects_dir,
        wildcards_dir=updated_configuration.wildcards_dir,
        appdata_dir=updated_configuration.appdata_dir,
        session_dir=updated_configuration.session_dir,
        cache_dir=updated_configuration.cache_dir,
        diagnostics_dir=updated_configuration.diagnostics_dir,
        logs_dir=updated_configuration.logs_dir,
        runtime_state_dir=updated_configuration.runtime_state_dir,
        model_metadata_dir=updated_configuration.model_metadata_dir,
        runtime_dir=updated_configuration.runtime_dir,
        default_managed_comfy_dir=updated_configuration.default_managed_comfy_dir,
    )


def test_installation_repository_loads_legacy_config_without_user_roots(
    tmp_path: Path,
) -> None:
    """Old persisted config should load with derived user-data roots."""

    repository = FileInstallationConfigurationRepository(tmp_path)
    _write_legacy_installation_config(tmp_path)

    configuration = repository.load()

    assert configuration.user_dir == tmp_path / "user"
    assert configuration.user_settings_dir == tmp_path / "user" / "settings"
    assert (
        configuration.model_metadata_dir
        == tmp_path / "appdata" / "cache" / "model_metadata"
    )
    assert configuration.wildcards_dir == tmp_path / "user" / "wildcards"
    assert configuration.outputs_dir == tmp_path / "user" / "outputs"
    assert configuration.projects_dir == tmp_path / "projects"
    assert configuration.sugar_scripts_dir == configuration.projects_dir
    assert configuration.appdata_dir == tmp_path / "appdata"


def test_installation_service_migrates_legacy_default_projects_root(
    tmp_path: Path,
) -> None:
    """Default legacy project data should move into Substitute user data."""

    repository = FileInstallationConfigurationRepository(tmp_path)
    service = InstallationService(repository)
    legacy_projects_dir = tmp_path / "projects"
    (legacy_projects_dir / "Recipe").mkdir(parents=True)
    (legacy_projects_dir / "Recipe" / "Recipe.sugar").write_text(
        'use "cube" as A',
        encoding="utf-8",
    )
    _write_legacy_installation_config(tmp_path)

    configuration = service.load_persisted()

    assert configuration is not None
    assert configuration.projects_dir == tmp_path / "user" / "projects"
    assert configuration.sugar_scripts_dir == configuration.projects_dir
    assert not legacy_projects_dir.exists()
    assert (configuration.projects_dir / "Recipe" / "Recipe.sugar").exists()


def test_installation_service_preserves_custom_projects_root(
    tmp_path: Path,
) -> None:
    """Custom project directories are a persisted user choice and should remain active."""

    repository = FileInstallationConfigurationRepository(tmp_path)
    configuration = repository.load()
    custom_configuration = type(configuration)(
        installation_root=configuration.installation_root,
        user_dir=configuration.user_dir,
        user_settings_dir=configuration.user_settings_dir,
        projects_dir=tmp_path / "external-projects",
        outputs_dir=configuration.outputs_dir,
        sugar_scripts_dir=configuration.sugar_scripts_dir,
        wildcards_dir=configuration.wildcards_dir,
        appdata_dir=configuration.appdata_dir,
        session_dir=configuration.session_dir,
        cache_dir=configuration.cache_dir,
        diagnostics_dir=configuration.diagnostics_dir,
        logs_dir=configuration.logs_dir,
        runtime_state_dir=configuration.runtime_state_dir,
        model_metadata_dir=configuration.model_metadata_dir,
        runtime_dir=configuration.runtime_dir,
        default_managed_comfy_dir=configuration.default_managed_comfy_dir,
    )

    saved_configuration = InstallationService(repository).save(custom_configuration)

    assert saved_configuration.projects_dir == tmp_path / "external-projects"
    assert saved_configuration.sugar_scripts_dir == saved_configuration.projects_dir


def test_installation_service_moves_orphan_saved_masks_to_legacy_user_area(
    tmp_path: Path,
) -> None:
    """Unmapped root mask artifacts should move to the legacy user-data area."""

    repository = FileInstallationConfigurationRepository(tmp_path)
    saved_masks_dir = tmp_path / "saved_masks"
    saved_masks_dir.mkdir()
    (saved_masks_dir / "mask.png").write_bytes(b"mask")

    InstallationService(repository).save(repository.load())

    assert not saved_masks_dir.exists()
    assert (tmp_path / "user" / "legacy" / "saved_masks" / "mask.png").exists()


def test_installation_service_materializes_user_cache_directories(
    tmp_path: Path,
) -> None:
    """Saving the default configuration should create user-data landing spots."""

    repository = FileInstallationConfigurationRepository(tmp_path)
    configuration = InstallationService(repository).save(repository.load())

    assert configuration.user_dir.is_dir()
    assert configuration.user_settings_dir.is_dir()
    assert configuration.projects_dir.is_dir()
    assert configuration.sugar_scripts_dir.is_dir()
    assert configuration.sugar_scripts_dir == configuration.projects_dir
    assert configuration.outputs_dir.is_dir()
    assert configuration.appdata_dir.is_dir()
    assert configuration.session_dir.is_dir()
    assert (configuration.cache_dir / "cube").is_dir()
    assert (configuration.cache_dir / "danbooru" / "images").is_dir()
    assert configuration.runtime_state_dir.is_dir()
    assert configuration.diagnostics_dir.is_dir()
    assert configuration.logs_dir.is_dir()
    assert (configuration.model_metadata_dir / "catalog").is_dir()
    assert (configuration.model_metadata_dir / "thumbnails").is_dir()
    assert (configuration.model_metadata_dir / "fingerprints").is_dir()
    assert configuration.wildcards_dir.is_dir()
    assert not (tmp_path / "user" / "sugarscripts").exists()
    assert not (tmp_path / "config").exists()
    assert not (tmp_path / "state").exists()
    assert not (tmp_path / "cubes").exists()
    assert not (tmp_path / "custom_nodes").exists()


def test_installation_service_migrates_legacy_layout_files(
    tmp_path: Path,
) -> None:
    """Legacy config and state files should move into user/appdata ownership roots."""

    repository = FileInstallationConfigurationRepository(tmp_path)
    _write_legacy_installation_config(tmp_path)
    legacy_files = {
        tmp_path / "config" / "runtime.json": "{}",
        tmp_path / "config" / "comfy_target.json": "{}",
        tmp_path / "config" / "appearance.json": "{}",
        tmp_path / "state" / "session" / "session.json": "{}",
        tmp_path / "state" / "restore-projection-cache.json": "{}",
        tmp_path / "state" / "cube_icon_cache.sqlite3": "icon",
        tmp_path / "state" / "cube_classification_cache.sqlite3": "classification",
        tmp_path / "state" / "danbooru_cache.sqlite3": "danbooru",
        tmp_path / "state" / "managed_runtime.json": "{}",
        tmp_path / "state" / "managed_comfy_process.json": "{}",
        tmp_path / "state" / "setup_transaction.json": "{}",
        tmp_path / "state" / "startup_diagnostics_ignores.json": "{}",
    }
    for path, content in legacy_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "state" / "danbooru_images").mkdir(parents=True)
    (tmp_path / "state" / "danbooru_images" / "image.webp").write_bytes(b"image")
    (tmp_path / "state" / "logs").mkdir()
    (tmp_path / "state" / "logs" / "sugarsubstitute.log").write_text(
        "log",
        encoding="utf-8",
    )
    (tmp_path / "user" / "model_metadata").mkdir(parents=True)
    (tmp_path / "user" / "model_metadata" / "model_metadata.sqlite3").write_text(
        "metadata",
        encoding="utf-8",
    )

    configuration = InstallationService(repository).load_persisted()

    assert configuration is not None
    assert (configuration.user_settings_dir / "installation.json").exists()
    assert (configuration.user_settings_dir / "runtime.json").exists()
    assert (configuration.user_settings_dir / "appearance.json").exists()
    assert (configuration.session_dir / "session.json").exists()
    assert (configuration.cache_dir / "restore-projection-cache.json").exists()
    assert (configuration.cache_dir / "cube" / "cube_icon_cache.sqlite3").exists()
    assert (
        configuration.cache_dir / "cube" / "cube_classification_cache.sqlite3"
    ).exists()
    assert (configuration.cache_dir / "danbooru" / "danbooru_cache.sqlite3").exists()
    assert (configuration.cache_dir / "danbooru" / "images" / "image.webp").exists()
    assert (configuration.runtime_state_dir / "managed_runtime.json").exists()
    assert (configuration.runtime_state_dir / "managed_comfy_process.json").exists()
    assert (configuration.runtime_state_dir / "setup_transaction.json").exists()
    assert (configuration.diagnostics_dir / "startup_diagnostics_ignores.json").exists()
    assert (configuration.logs_dir / "sugarsubstitute.log").exists()
    assert (configuration.model_metadata_dir / "model_metadata.sqlite3").exists()


def test_installation_service_preserves_project_sugar_scripts(
    tmp_path: Path,
) -> None:
    """Recipe files under `user/projects` should remain project-owned."""

    repository = FileInstallationConfigurationRepository(tmp_path)
    configuration = repository.load()
    projects_recipe_dir = configuration.projects_dir / "Portrait"
    versions_dir = projects_recipe_dir / "versions"
    versions_dir.mkdir(parents=True)
    (projects_recipe_dir / "Portrait.sugar").write_text(
        'use "cube" as A',
        encoding="utf-8",
    )
    (versions_dir / "Portrait_20260511_120000.sugar").write_text(
        'use "old-cube" as A',
        encoding="utf-8",
    )
    masks_dir = projects_recipe_dir / "masks"
    masks_dir.mkdir()
    (masks_dir / "mask.png").write_bytes(b"mask")

    InstallationService(repository).save(configuration)

    assert (projects_recipe_dir / "Portrait.sugar").read_text(
        encoding="utf-8"
    ) == 'use "cube" as A'
    assert (versions_dir / "Portrait_20260511_120000.sugar").read_text(
        encoding="utf-8"
    ) == 'use "old-cube" as A'
    assert (masks_dir / "mask.png").exists()


def _write_legacy_installation_config(installation_root: Path) -> None:
    """Write the pre-user-dir installation config format for migration tests."""

    legacy_config_path = installation_root / "config" / "installation.json"
    legacy_config_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_config_path.write_text(
        json.dumps(
            {
                "installation_root": str(installation_root),
                "config_dir": str(installation_root / "config"),
                "state_dir": str(installation_root / "state"),
                "logs_dir": str(installation_root / "state" / "logs"),
                "cubes_dir": str(installation_root / "cubes"),
                "projects_dir": str(installation_root / "projects"),
                "runtime_dir": str(installation_root / "runtime"),
                "workspace_custom_nodes_dir": str(installation_root / "custom_nodes"),
                "default_managed_comfy_dir": str(installation_root / "comfyui"),
            }
        ),
        encoding="utf-8",
    )
