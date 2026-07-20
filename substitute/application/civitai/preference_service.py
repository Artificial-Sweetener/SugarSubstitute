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

"""Coordinate CivitAI preference loading, normalization, and persistence."""

from __future__ import annotations

from sugarsubstitute_shared.localization import app_text

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from substitute.application.civitai.download_path_template_renderer import (
    CivitaiDownloadPathTemplateError,
    CivitaiDownloadPathTemplateRenderer,
)
from substitute.application.ports.civitai_preference_repository import (
    CivitaiPreferenceRepository,
)
from substitute.domain.civitai import (
    CIVITAI_PREFERENCES_SCHEMA_VERSION,
    DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN,
    CivitaiDownloadPathRenderContext,
    CivitaiDownloadPathRenderResult,
    CivitaiDownloadPathToken,
    CivitaiPreferences,
    CivitaiThumbnailSafetyPolicy,
    SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKENS,
    default_civitai_preferences,
)


@dataclass(frozen=True, slots=True)
class CivitaiPreferenceSaveResult:
    """Describe a settings-facing CivitAI preference save result."""

    preferences: CivitaiPreferences
    succeeded: bool
    message: str
    preview: CivitaiDownloadPathRenderResult | None = None


class CivitaiPreferenceService:
    """Own CivitAI integration policy use cases."""

    def __init__(
        self,
        repository: CivitaiPreferenceRepository,
        *,
        preview_comfy_root: Path | Callable[[], Path] | None = None,
        renderer: CivitaiDownloadPathTemplateRenderer | None = None,
    ) -> None:
        """Store the CivitAI preference repository."""

        self._repository = repository
        self._preview_comfy_root = preview_comfy_root or Path("models/diffusion_models")
        self._renderer = renderer or CivitaiDownloadPathTemplateRenderer()

    def load_preferences(self) -> CivitaiPreferences:
        """Load normalized CivitAI preferences."""

        return self._normalize(self._repository.load())

    def default_preferences(self) -> CivitaiPreferences:
        """Return default CivitAI preferences."""

        return default_civitai_preferences()

    def save_preferences(self, preferences: CivitaiPreferences) -> CivitaiPreferences:
        """Persist one normalized CivitAI preference snapshot."""

        normalized = self._normalize(preferences)
        self._repository.save(normalized)
        return normalized

    def set_metadata_lookup_enabled(self, enabled: bool) -> CivitaiPreferences:
        """Persist whether local model hashes may query CivitAI metadata."""

        return self.save_preferences(
            self.load_preferences().with_metadata_lookup_enabled(enabled)
        )

    def set_missing_model_lookup_enabled(self, enabled: bool) -> CivitaiPreferences:
        """Persist whether recipe missing-model hashes may query CivitAI."""

        return self.save_preferences(
            self.load_preferences().with_missing_model_lookup_enabled(enabled)
        )

    def set_thumbnail_downloads_enabled(self, enabled: bool) -> CivitaiPreferences:
        """Persist whether CivitAI thumbnails may be downloaded."""

        return self.save_preferences(
            self.load_preferences().with_thumbnail_downloads_enabled(enabled)
        )

    def set_thumbnail_safety_policy(
        self,
        policy: CivitaiThumbnailSafetyPolicy,
    ) -> CivitaiPreferences:
        """Persist which CivitAI thumbnails are acceptable for display."""

        return self.save_preferences(
            self.load_preferences().with_thumbnail_safety_policy(policy)
        )

    def set_thumbnail_safety_policy_value(self, value: str) -> CivitaiPreferences:
        """Persist a thumbnail safety policy from a settings string value."""

        return self.set_thumbnail_safety_policy(CivitaiThumbnailSafetyPolicy(value))

    def set_downloads_enabled(self, enabled: bool) -> CivitaiPreferences:
        """Persist whether resolver flows may offer CivitAI model downloads."""

        return self.save_preferences(
            self.load_preferences().with_downloads_enabled(enabled)
        )

    def supported_download_path_token_descriptions(
        self,
    ) -> tuple[CivitaiDownloadPathToken, ...]:
        """Return CivitAI download path tokens with user-facing descriptions."""

        return SUPPORTED_CIVITAI_DOWNLOAD_PATH_TOKENS

    def render_download_path_preview(
        self,
        preferences: CivitaiPreferences | None = None,
    ) -> CivitaiDownloadPathRenderResult:
        """Render the settings preview path for CivitAI download organization."""

        resolved = self._normalize(
            preferences if preferences is not None else self.load_preferences()
        )
        return self._renderer.preview_path(
            path_pattern=resolved.download_path_pattern,
            context=self.example_download_path_context(),
        )

    def set_download_path_pattern(
        self,
        pattern: str,
    ) -> CivitaiPreferenceSaveResult:
        """Validate and persist the CivitAI download organization pattern."""

        preferences = self.load_preferences().with_download_path_pattern(pattern)
        normalized = self._normalize(preferences)
        try:
            self._renderer.validate_pattern(normalized.download_path_pattern)
            preview = self.render_download_path_preview(normalized)
        except CivitaiDownloadPathTemplateError as error:
            return CivitaiPreferenceSaveResult(
                preferences=self.load_preferences(),
                succeeded=False,
                message=str(error),
            )
        self._repository.save(normalized)
        return CivitaiPreferenceSaveResult(
            preferences=normalized,
            succeeded=True,
            message=app_text("CivitAI download organization settings saved."),
            preview=preview,
        )

    def example_download_path_context(self) -> CivitaiDownloadPathRenderContext:
        """Return deterministic example values for Settings previews."""

        return CivitaiDownloadPathRenderContext(
            kind="diffusion_models",
            comfy_root=(
                self._preview_comfy_root()
                if callable(self._preview_comfy_root)
                else self._preview_comfy_root
            ),
            base_model="Anima",
            model_name="Anima",
            version_name="base-v1.0",
            creator="CivitAI Creator",
            file_name="anima_baseV10.safetensors",
        )

    @staticmethod
    def _normalize(preferences: CivitaiPreferences) -> CivitaiPreferences:
        """Return preferences with the current schema version."""

        return CivitaiPreferences(
            schema_version=CIVITAI_PREFERENCES_SCHEMA_VERSION,
            metadata_lookup_enabled=preferences.metadata_lookup_enabled,
            missing_model_lookup_enabled=preferences.missing_model_lookup_enabled,
            thumbnail_downloads_enabled=preferences.thumbnail_downloads_enabled,
            thumbnail_safety_policy=preferences.thumbnail_safety_policy,
            downloads_enabled=preferences.downloads_enabled,
            download_path_pattern=(
                preferences.download_path_pattern
                or DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN
            ),
        )


__all__ = ["CivitaiPreferenceSaveResult", "CivitaiPreferenceService"]
