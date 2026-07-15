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

"""Define generation preview preferences and backend asset DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION = "1"


class GenerationPreviewMethod(StrEnum):
    """Identify ComfyUI preview methods exposed by SugarSubstitute settings."""

    AUTO = "auto"
    LATENT2RGB = "latent2rgb"
    TAESD = "taesd"


@dataclass(frozen=True, slots=True)
class GenerationPreviewPreferences:
    """Capture persisted user preferences for generation preview behavior."""

    schema_version: str
    enabled: bool
    method: GenerationPreviewMethod

    def resolved_comfy_preview_method(self) -> str:
        """Return the preview method value to send in Comfy prompt metadata."""

        if not self.enabled:
            return "none"
        return self.method.value

    def with_enabled(self, enabled: bool) -> GenerationPreviewPreferences:
        """Return preferences with preview enablement updated."""

        return GenerationPreviewPreferences(
            schema_version=self.schema_version,
            enabled=enabled,
            method=self.method,
        )

    def with_method(
        self,
        method: GenerationPreviewMethod,
    ) -> GenerationPreviewPreferences:
        """Return preferences with preview method updated."""

        return GenerationPreviewPreferences(
            schema_version=self.schema_version,
            enabled=self.enabled,
            method=method,
        )


class TaesdPreviewAssetState(StrEnum):
    """Identify backend-reported TAESD asset state."""

    INSTALLED = "installed"
    MISSING = "missing"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaesdPreviewAsset:
    """Describe one TAESD decoder asset reported by Substitute BackEnd."""

    asset_id: str
    filename: str
    url: str
    status: TaesdPreviewAssetState
    path: str | None = None
    size_bytes: int | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TaesdPreviewAssetStatus:
    """Describe TAESD decoder readiness reported by Substitute BackEnd."""

    schema_version: int
    ready: bool
    installed_count: int
    missing_count: int
    downloads_attempted: bool
    assets: tuple[TaesdPreviewAsset, ...]
    destination_root: str | None = None


def default_generation_preview_preferences() -> GenerationPreviewPreferences:
    """Return SugarSubstitute's default generation preview preferences."""

    return GenerationPreviewPreferences(
        schema_version=GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION,
        enabled=True,
        method=GenerationPreviewMethod.LATENT2RGB,
    )


__all__ = [
    "GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION",
    "GenerationPreviewMethod",
    "GenerationPreviewPreferences",
    "TaesdPreviewAsset",
    "TaesdPreviewAssetState",
    "TaesdPreviewAssetStatus",
    "default_generation_preview_preferences",
]
