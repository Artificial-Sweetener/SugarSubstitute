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

"""Define persisted CivitAI integration preferences."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from substitute.domain.civitai.download_organization import (
    DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN,
)

CIVITAI_PREFERENCES_SCHEMA_VERSION = "2"


class CivitaiThumbnailSafetyPolicy(str, Enum):
    """Identify which CivitAI image candidates may become model thumbnails."""

    DISABLED = "disabled"
    SFW_ONLY = "sfw_only"
    ALLOW_SOFT = "allow_soft"
    ALLOW_ALL = "allow_all"


@dataclass(frozen=True, slots=True)
class CivitaiPreferences:
    """Capture non-secret CivitAI integration policy."""

    schema_version: str
    metadata_lookup_enabled: bool
    missing_model_lookup_enabled: bool
    thumbnail_downloads_enabled: bool
    thumbnail_safety_policy: CivitaiThumbnailSafetyPolicy
    downloads_enabled: bool
    download_path_pattern: str

    def with_metadata_lookup_enabled(self, enabled: bool) -> CivitaiPreferences:
        """Return a copy with metadata lookup policy updated."""

        return CivitaiPreferences(
            schema_version=self.schema_version,
            metadata_lookup_enabled=enabled,
            missing_model_lookup_enabled=self.missing_model_lookup_enabled,
            thumbnail_downloads_enabled=self.thumbnail_downloads_enabled,
            thumbnail_safety_policy=self.thumbnail_safety_policy,
            downloads_enabled=self.downloads_enabled,
            download_path_pattern=self.download_path_pattern,
        )

    def with_missing_model_lookup_enabled(self, enabled: bool) -> CivitaiPreferences:
        """Return a copy with missing recipe model lookup policy updated."""

        return CivitaiPreferences(
            schema_version=self.schema_version,
            metadata_lookup_enabled=self.metadata_lookup_enabled,
            missing_model_lookup_enabled=enabled,
            thumbnail_downloads_enabled=self.thumbnail_downloads_enabled,
            thumbnail_safety_policy=self.thumbnail_safety_policy,
            downloads_enabled=self.downloads_enabled,
            download_path_pattern=self.download_path_pattern,
        )

    def with_thumbnail_downloads_enabled(self, enabled: bool) -> CivitaiPreferences:
        """Return a copy with thumbnail download policy updated."""

        return CivitaiPreferences(
            schema_version=self.schema_version,
            metadata_lookup_enabled=self.metadata_lookup_enabled,
            missing_model_lookup_enabled=self.missing_model_lookup_enabled,
            thumbnail_downloads_enabled=enabled,
            thumbnail_safety_policy=self.thumbnail_safety_policy,
            downloads_enabled=self.downloads_enabled,
            download_path_pattern=self.download_path_pattern,
        )

    def with_thumbnail_safety_policy(
        self,
        policy: CivitaiThumbnailSafetyPolicy,
    ) -> CivitaiPreferences:
        """Return a copy with thumbnail safety policy updated."""

        return CivitaiPreferences(
            schema_version=self.schema_version,
            metadata_lookup_enabled=self.metadata_lookup_enabled,
            missing_model_lookup_enabled=self.missing_model_lookup_enabled,
            thumbnail_downloads_enabled=self.thumbnail_downloads_enabled,
            thumbnail_safety_policy=policy,
            downloads_enabled=self.downloads_enabled,
            download_path_pattern=self.download_path_pattern,
        )

    def with_downloads_enabled(self, enabled: bool) -> CivitaiPreferences:
        """Return a copy with model download policy updated."""

        return CivitaiPreferences(
            schema_version=self.schema_version,
            metadata_lookup_enabled=self.metadata_lookup_enabled,
            missing_model_lookup_enabled=self.missing_model_lookup_enabled,
            thumbnail_downloads_enabled=self.thumbnail_downloads_enabled,
            thumbnail_safety_policy=self.thumbnail_safety_policy,
            downloads_enabled=enabled,
            download_path_pattern=self.download_path_pattern,
        )

    def with_download_path_pattern(self, pattern: str) -> CivitaiPreferences:
        """Return a copy with the model download path pattern updated."""

        return CivitaiPreferences(
            schema_version=self.schema_version,
            metadata_lookup_enabled=self.metadata_lookup_enabled,
            missing_model_lookup_enabled=self.missing_model_lookup_enabled,
            thumbnail_downloads_enabled=self.thumbnail_downloads_enabled,
            thumbnail_safety_policy=self.thumbnail_safety_policy,
            downloads_enabled=self.downloads_enabled,
            download_path_pattern=pattern,
        )


def default_civitai_preferences() -> CivitaiPreferences:
    """Return default CivitAI policy preserving current integration behavior."""

    return CivitaiPreferences(
        schema_version=CIVITAI_PREFERENCES_SCHEMA_VERSION,
        metadata_lookup_enabled=True,
        missing_model_lookup_enabled=True,
        thumbnail_downloads_enabled=True,
        thumbnail_safety_policy=CivitaiThumbnailSafetyPolicy.SFW_ONLY,
        downloads_enabled=True,
        download_path_pattern=DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN,
    )


__all__ = [
    "CIVITAI_PREFERENCES_SCHEMA_VERSION",
    "DEFAULT_CIVITAI_DOWNLOAD_PATH_PATTERN",
    "CivitaiPreferences",
    "CivitaiThumbnailSafetyPolicy",
    "default_civitai_preferences",
]
