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

"""Coordinate generation preview preference updates and TAESD preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.application.ports.generation_preview_preference_repository import (
    GenerationPreviewPreferenceRepository,
)
from substitute.domain.generation import (
    GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION,
    GenerationPreviewMethod,
    GenerationPreviewPreferences,
    TaesdPreviewAssetStatus,
    default_generation_preview_preferences,
)


class PreviewAssetBackend(Protocol):
    """Backend port for preview asset preparation routes."""

    def get_taesd_status(self) -> TaesdPreviewAssetStatus | None:
        """Return TAESD asset readiness or ``None`` when unavailable."""

    def ensure_taesd_assets(self) -> TaesdPreviewAssetStatus | None:
        """Prepare TAESD assets and return readiness or ``None`` when unavailable."""


class GenerationPreviewMethodResolver(Protocol):
    """Resolve the ComfyUI preview method used when queueing prompts."""

    def resolved_comfy_preview_method(self) -> str:
        """Return the preview method to send to ComfyUI."""


@dataclass(frozen=True)
class GenerationPreviewSaveResult:
    """Describe the result of saving preview preferences."""

    preferences: GenerationPreviewPreferences
    succeeded: bool
    message: str
    taesd_ready: bool | None = None
    taesd_status: TaesdPreviewAssetStatus | None = None


class GenerationPreviewPreferenceService(GenerationPreviewMethodResolver):
    """Own generation preview preference use cases."""

    def __init__(
        self,
        repository: GenerationPreviewPreferenceRepository,
        preview_asset_backend: PreviewAssetBackend | None = None,
    ) -> None:
        """Initialize preference persistence and optional backend preparation."""

        self._repository = repository
        self._preview_asset_backend = preview_asset_backend

    def load_preferences(self) -> GenerationPreviewPreferences:
        """Load normalized generation preview preferences."""

        return self._normalize(self._repository.load())

    def default_preferences(self) -> GenerationPreviewPreferences:
        """Return the default preview preferences."""

        return default_generation_preview_preferences()

    def save_preferences(
        self,
        preferences: GenerationPreviewPreferences,
    ) -> GenerationPreviewSaveResult:
        """Persist normalized preferences and prepare TAESD when selected."""

        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        if normalized.enabled and normalized.method is GenerationPreviewMethod.TAESD:
            return self._prepare_taesd(normalized)
        return GenerationPreviewSaveResult(
            preferences=normalized,
            succeeded=True,
            message="Generation preview settings saved.",
        )

    def set_enabled(self, enabled: bool) -> GenerationPreviewSaveResult:
        """Persist preview enablement and return the new preference state."""

        return self.save_preferences(self.load_preferences().with_enabled(enabled))

    def set_method(
        self,
        method: GenerationPreviewMethod,
    ) -> GenerationPreviewSaveResult:
        """Persist preview method and prepare TAESD assets when needed."""

        return self.save_preferences(self.load_preferences().with_method(method))

    def set_method_value(self, method_value: str) -> GenerationPreviewSaveResult:
        """Persist one settings-facing preview method value."""

        try:
            method = GenerationPreviewMethod(method_value)
        except ValueError:
            return GenerationPreviewSaveResult(
                preferences=self.load_preferences(),
                succeeded=False,
                message="Generation preview type is not recognized.",
            )
        return self.set_method(method)

    def resolved_comfy_preview_method(self) -> str:
        """Return the current ComfyUI preview method for prompt metadata."""

        return self.load_preferences().resolved_comfy_preview_method()

    def _prepare_taesd(
        self,
        preferences: GenerationPreviewPreferences,
    ) -> GenerationPreviewSaveResult:
        """Prepare TAESD assets through the backend and describe readiness."""

        if self._preview_asset_backend is None:
            return GenerationPreviewSaveResult(
                preferences=preferences,
                succeeded=True,
                message="TAESD selected, but Substitute BackEnd is not available.",
                taesd_ready=False,
            )
        status = self._preview_asset_backend.ensure_taesd_assets()
        if status is None:
            return GenerationPreviewSaveResult(
                preferences=preferences,
                succeeded=True,
                message="TAESD selected, but preview files could not be checked.",
                taesd_ready=False,
            )
        if status.ready:
            return GenerationPreviewSaveResult(
                preferences=preferences,
                succeeded=True,
                message="TAESD preview files are installed.",
                taesd_ready=True,
                taesd_status=status,
            )
        return GenerationPreviewSaveResult(
            preferences=preferences,
            succeeded=True,
            message=(
                "TAESD selected, but "
                f"{status.missing_count} preview file(s) are not installed."
            ),
            taesd_ready=False,
            taesd_status=status,
        )

    @staticmethod
    def _normalize(
        preferences: GenerationPreviewPreferences,
    ) -> GenerationPreviewPreferences:
        """Return preferences with the current schema version."""

        return GenerationPreviewPreferences(
            schema_version=GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION,
            enabled=preferences.enabled,
            method=preferences.method,
        )


__all__ = [
    "GenerationPreviewMethodResolver",
    "GenerationPreviewPreferenceService",
    "GenerationPreviewSaveResult",
    "PreviewAssetBackend",
]
