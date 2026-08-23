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

"""Verify generation preview preference application workflows."""

from __future__ import annotations

from substitute.application.generation import GenerationPreviewPreferenceService
from substitute.domain.generation import (
    GenerationPreviewMethod,
    GenerationPreviewPreferences,
    TaesdPreviewAssetStatus,
    default_generation_preview_preferences,
)


class MemoryRepository:
    """Store generation preview preferences in memory."""

    def __init__(self) -> None:
        """Initialize default preferences and write count."""

        self.preferences = default_generation_preview_preferences()
        self.saved = 0

    def load(self) -> GenerationPreviewPreferences:
        """Return the current in-memory preferences."""

        return self.preferences

    def save(self, preferences: GenerationPreviewPreferences) -> None:
        """Store preferences and count one write."""

        self.saved += 1
        self.preferences = preferences


class PreviewAssetBackend:
    """Record TAESD preparation and return one configured status."""

    def __init__(self, status: TaesdPreviewAssetStatus | None) -> None:
        """Store the configured backend response."""

        self.status = status
        self.ensure_calls = 0

    def get_taesd_status(self) -> TaesdPreviewAssetStatus | None:
        """Return the configured status without preparing assets."""

        return self.status

    def ensure_taesd_assets(self) -> TaesdPreviewAssetStatus | None:
        """Record one preparation request and return the configured status."""

        self.ensure_calls += 1
        return self.status


def test_generation_preview_service_prepares_taesd_assets() -> None:
    """Persist TAESD selection and request asset preparation."""

    repository = MemoryRepository()
    backend = PreviewAssetBackend(_status(ready=True, missing_count=0))
    service = GenerationPreviewPreferenceService(repository, backend)

    result = service.set_method(GenerationPreviewMethod.TAESD)

    assert repository.preferences.method is GenerationPreviewMethod.TAESD
    assert repository.saved == 1
    assert backend.ensure_calls == 1
    assert result.taesd_ready is True
    assert result.message == "TAESD preview files are installed."


def test_generation_preview_service_reports_unavailable_backend() -> None:
    """Keep a TAESD selection when preparation cannot contact the backend."""

    repository = MemoryRepository()
    service = GenerationPreviewPreferenceService(repository, PreviewAssetBackend(None))

    result = service.set_method(GenerationPreviewMethod.TAESD)

    assert repository.preferences.method is GenerationPreviewMethod.TAESD
    assert result.succeeded is True
    assert result.taesd_ready is False
    assert "could not be checked" in result.message


def _status(*, ready: bool, missing_count: int) -> TaesdPreviewAssetStatus:
    """Build a minimal TAESD readiness response."""

    return TaesdPreviewAssetStatus(
        schema_version=1,
        ready=ready,
        installed_count=4 - missing_count,
        missing_count=missing_count,
        downloads_attempted=True,
        assets=(),
        destination_root="E:\\ComfyUI\\models\\vae_approx",
    )
