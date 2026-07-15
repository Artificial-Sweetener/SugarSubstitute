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

"""Tests for generation preview preferences and TAESD preparation orchestration."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.generation import GenerationPreviewPreferenceService
from substitute.domain.generation import (
    GenerationPreviewMethod,
    TaesdPreviewAssetStatus,
    default_generation_preview_preferences,
)
from substitute.infrastructure.persistence import (
    FileGenerationPreviewPreferenceRepository,
)


class _MemoryRepository:
    """Store preferences in memory for service tests."""

    def __init__(self) -> None:
        """Initialize with default preferences."""

        self.preferences = default_generation_preview_preferences()
        self.saved = 0

    def load(self):
        """Return the current in-memory preferences."""

        return self.preferences

    def save(self, preferences) -> None:
        """Store preferences and count writes."""

        self.saved += 1
        self.preferences = preferences


class _Backend:
    """Record TAESD ensure calls and return a configured status."""

    def __init__(self, status: TaesdPreviewAssetStatus | None) -> None:
        """Store the configured status."""

        self.status = status
        self.ensure_calls = 0

    def get_taesd_status(self) -> TaesdPreviewAssetStatus | None:
        """Return configured status without recording ensure."""

        return self.status

    def ensure_taesd_assets(self) -> TaesdPreviewAssetStatus | None:
        """Record ensure calls and return configured status."""

        self.ensure_calls += 1
        return self.status


def test_generation_preview_defaults_resolve_to_latent2rgb() -> None:
    """Default preview preferences should enable latent RGB previews."""

    preferences = default_generation_preview_preferences()

    assert preferences.enabled is True
    assert preferences.method is GenerationPreviewMethod.LATENT2RGB
    assert preferences.resolved_comfy_preview_method() == "latent2rgb"


def test_generation_preview_disabled_resolves_to_none() -> None:
    """Disabled preview preferences should send Comfy's no-preview value."""

    preferences = default_generation_preview_preferences().with_enabled(False)

    assert preferences.resolved_comfy_preview_method() == "none"


def test_file_generation_preview_repository_round_trips(tmp_path: Path) -> None:
    """File repository should persist generation preview preferences."""

    repository = FileGenerationPreviewPreferenceRepository(tmp_path)
    repository.save(
        default_generation_preview_preferences().with_method(
            GenerationPreviewMethod.TAESD
        )
    )

    loaded = repository.load()

    assert loaded.enabled is True
    assert loaded.method is GenerationPreviewMethod.TAESD


def test_file_generation_preview_repository_uses_defaults_for_missing_file(
    tmp_path: Path,
) -> None:
    """Missing preference files should load default preferences."""

    loaded = FileGenerationPreviewPreferenceRepository(tmp_path).load()

    assert loaded == default_generation_preview_preferences()


def test_file_generation_preview_repository_defaults_unknown_method(
    tmp_path: Path,
) -> None:
    """Unknown persisted preview methods should fall back to latent RGB."""

    path = tmp_path / "generation_preview.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "enabled": False,
                "method": "unknown",
            }
        ),
        encoding="utf-8",
    )

    loaded = FileGenerationPreviewPreferenceRepository(tmp_path).load()

    assert loaded.enabled is False
    assert loaded.method is GenerationPreviewMethod.LATENT2RGB


def test_generation_preview_service_taesd_calls_backend_ensure() -> None:
    """Selecting TAESD should persist the method and prepare backend assets."""

    repository = _MemoryRepository()
    backend = _Backend(_status(ready=True, missing_count=0))
    service = GenerationPreviewPreferenceService(repository, backend)

    result = service.set_method(GenerationPreviewMethod.TAESD)

    assert repository.preferences.method is GenerationPreviewMethod.TAESD
    assert repository.saved == 1
    assert backend.ensure_calls == 1
    assert result.taesd_ready is True
    assert result.message == "TAESD preview files are installed."


def test_generation_preview_service_reports_backend_unavailable() -> None:
    """TAESD selection should remain saved when backend preparation is unavailable."""

    repository = _MemoryRepository()
    service = GenerationPreviewPreferenceService(repository, _Backend(None))

    result = service.set_method(GenerationPreviewMethod.TAESD)

    assert repository.preferences.method is GenerationPreviewMethod.TAESD
    assert result.succeeded is True
    assert result.taesd_ready is False
    assert "could not be checked" in result.message


def _status(*, ready: bool, missing_count: int) -> TaesdPreviewAssetStatus:
    """Build a minimal TAESD status for service tests."""

    return TaesdPreviewAssetStatus(
        schema_version=1,
        ready=ready,
        installed_count=4 - missing_count,
        missing_count=missing_count,
        downloads_attempted=True,
        assets=(),
        destination_root="E:\\ComfyUI\\models\\vae_approx",
    )
