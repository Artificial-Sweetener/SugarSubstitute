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

"""Tests for the file-backed restore projection cache repository."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.workspace_state import (
    APP_PROJECTION_VERSION,
    RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
    RestoreProjectionArtifact,
)
from substitute.infrastructure.persistence.file_restore_projection_cache import (
    FileRestoreProjectionCacheRepository,
)


def test_missing_restore_projection_cache_returns_none(tmp_path: Path) -> None:
    """Missing cache files should be treated as a normal cold-start state."""

    repository = FileRestoreProjectionCacheRepository(tmp_path)

    assert repository.load() is None


def test_restore_projection_cache_saves_and_loads_artifact(tmp_path: Path) -> None:
    """Saved artifacts should round-trip through the repository."""

    repository = FileRestoreProjectionCacheRepository(tmp_path)
    artifact = _artifact(workspace_fingerprint="workspace-a")

    repository.save(artifact)

    assert repository.path.exists()
    assert repository.load() == artifact


def test_restore_projection_cache_save_creates_parent_directory(tmp_path: Path) -> None:
    """Saving should create the supplied state directory when needed."""

    state_dir = tmp_path / "missing" / "state"
    repository = FileRestoreProjectionCacheRepository(state_dir)

    repository.save(_artifact())

    assert repository.path.exists()


def test_invalid_restore_projection_cache_logs_warning_and_returns_none(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unreadable cache content should not break startup restore."""

    repository = FileRestoreProjectionCacheRepository(tmp_path)
    repository.path.write_text("{not-json", encoding="utf-8")

    assert repository.load() is None
    assert "Failed to load restore projection cache" in caplog.text


def test_restore_projection_cache_clear_removes_file(tmp_path: Path) -> None:
    """Clearing should remove the cache and tolerate repeated calls."""

    repository = FileRestoreProjectionCacheRepository(tmp_path)
    repository.save(_artifact())

    repository.clear()
    repository.clear()

    assert repository.load() is None


def test_failed_restore_projection_cache_serialization_does_not_replace_existing(
    tmp_path: Path,
) -> None:
    """Serialization failures should leave an existing valid artifact untouched."""

    repository = FileRestoreProjectionCacheRepository(tmp_path)
    valid_artifact = _artifact(workspace_fingerprint="valid")
    invalid_artifact = _artifact(
        workspace_fingerprint="invalid",
        projection={"bad": object()},
    )
    repository.save(valid_artifact)

    with pytest.raises(TypeError):
        repository.save(invalid_artifact)

    assert repository.load() == valid_artifact


def _artifact(
    *,
    workspace_fingerprint: str = "workspace",
    projection: dict[str, object] | None = None,
) -> RestoreProjectionArtifact:
    """Build a minimal cache artifact for repository behavior tests."""

    return RestoreProjectionArtifact(
        schema_version=RESTORE_PROJECTION_CACHE_SCHEMA_VERSION,
        created_at="2026-05-10T00:00:00Z",
        app_projection_version=APP_PROJECTION_VERSION,
        target_key="target",
        workspace_fingerprint=workspace_fingerprint,
        active_route="editor",
        active_workflow_id="workflow",
        workflows=(),
        prompt_editor_feature_profile_fingerprint="prompt-profile",
        node_definition_fingerprints={},
        cube_definition_fingerprints={},
        projection=projection or {},
    )
