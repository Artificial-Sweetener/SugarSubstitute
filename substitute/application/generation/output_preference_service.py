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

"""Coordinate generated-output preferences, validation, and save planning."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText, app_text

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Hashable

from substitute.application.generation.output_path_template_renderer import (
    OutputPathTemplateError,
    OutputPathTemplateRenderer,
)
from substitute.application.cubes import cube_alias_body
from substitute.application.ports.comfy_gateway import OutputSavePlan
from substitute.application.ports.output_preference_repository import (
    OutputPreferenceRepository,
)
from substitute.domain.generation.output_organization import (
    DEFAULT_OUTPUT_PATH_PATTERN,
    OutputPathRenderContext,
    OutputPathRenderResult,
    OutputPathToken,
    OutputRunBucket,
    SUPPORTED_OUTPUT_PATH_TOKENS,
)
from substitute.domain.generation.output_preferences import (
    default_output_preferences,
    JpegOutputSettings,
    JpegSizingMode,
    OUTPUT_PREFERENCES_SCHEMA_VERSION,
    OutputOrganizationSettings,
    OutputPersistenceMode,
    OutputPreferences,
)


@dataclass(frozen=True, slots=True)
class OutputPreferenceSaveResult:
    """Describe one settings-facing output preference save result."""

    preferences: OutputPreferences
    succeeded: bool
    message: ApplicationText
    preview: OutputPathRenderResult | None = None


class OutputPreferenceService:
    """Own validation, persistence, preview rendering, and immutable run plans."""

    def __init__(
        self,
        repository: OutputPreferenceRepository,
        *,
        default_output_root: Path,
        renderer: OutputPathTemplateRenderer | None = None,
    ) -> None:
        """Initialize preference persistence and output-path dependencies."""

        self._repository = repository
        self._default_output_root = default_output_root
        self._renderer = renderer or OutputPathTemplateRenderer()

    def load_preferences(self) -> OutputPreferences:
        """Load normalized output preferences."""

        return self._normalize(self._repository.load())

    def default_preferences(self) -> OutputPreferences:
        """Return defaults that durably save canonical PNGs for every source."""

        return default_output_preferences()

    def supported_tokens(self) -> tuple[str, ...]:
        """Return supported token placeholders in display order."""

        return tuple(token.placeholder for token in SUPPORTED_OUTPUT_PATH_TOKENS)

    def supported_token_descriptions(self) -> tuple[OutputPathToken, ...]:
        """Return supported output tokens with descriptions."""

        return SUPPORTED_OUTPUT_PATH_TOKENS

    def effective_output_root(
        self, preferences: OutputPreferences | None = None
    ) -> Path:
        """Return the concrete output root for preferences or current state."""

        resolved = preferences or self.load_preferences()
        return resolved.organization.output_root or self._default_output_root

    def save_preferences(
        self, preferences: OutputPreferences
    ) -> OutputPreferenceSaveResult:
        """Persist validated output preferences."""

        normalized = self._normalize(preferences)
        try:
            self._validate_preferences(normalized)
        except (OutputPathTemplateError, ValueError) as error:
            return OutputPreferenceSaveResult(
                preferences=self.load_preferences(),
                succeeded=False,
                message=str(error),
            )
        self._repository.save(normalized)
        return OutputPreferenceSaveResult(
            preferences=normalized,
            succeeded=True,
            message=app_text("Output settings saved."),
            preview=self.render_preview(normalized),
        )

    def reset_preferences(self) -> OutputPreferenceSaveResult:
        """Persist default output preferences."""

        return self.save_preferences(self.default_preferences())

    def render_preview(
        self, preferences: OutputPreferences | None = None
    ) -> OutputPathRenderResult:
        """Render the settings preview path for preferences."""

        resolved = self._normalize(preferences or self.load_preferences())
        return self._renderer.preview_path(
            output_root=self.effective_output_root(resolved),
            path_pattern=resolved.organization.path_pattern,
            context=self.example_render_context(),
        )

    def create_save_plan(
        self,
        *,
        workflow_name: str,
        output_run_number: int | None,
        job_started_at: datetime,
        seed: str = "",
        cube_numbers_by_alias: Mapping[str, int] | None = None,
        active_cube_aliases: tuple[str, ...] = (),
        muted_cube_aliases: frozenset[str] = frozenset(),
    ) -> OutputSavePlan:
        """Create one immutable run policy from current preferences and topology."""

        preferences = self.load_preferences()
        self._validate_preferences(preferences)
        normalized_muted_aliases = _alias_keys(muted_cube_aliases)
        persisted_aliases: frozenset[str] | None = None
        if preferences.persistence_mode is OutputPersistenceMode.FINAL_CUBE:
            final_alias = active_cube_aliases[-1] if active_cube_aliases else None
            persisted_aliases = (
                _alias_keys((final_alias,))
                if final_alias is not None
                and not _alias_keys((final_alias,)).intersection(
                    normalized_muted_aliases
                )
                else frozenset()
            )
        return OutputSavePlan(
            output_root=self.effective_output_root(preferences),
            path_pattern=preferences.organization.path_pattern,
            workflow_name=workflow_name,
            output_run_number=output_run_number,
            job_started_at=job_started_at,
            seed=seed,
            cube_numbers_by_alias=cube_numbers_by_alias or {},
            jpeg=preferences.jpeg,
            persisted_cube_aliases=persisted_aliases,
            muted_cube_aliases=normalized_muted_aliases,
        )

    def resolve_run_bucket(
        self, *, workflow_name: str, job_started_at: datetime, seed: str = ""
    ) -> OutputRunBucket:
        """Resolve the namespace used to allocate a run number."""

        preferences = self.load_preferences()
        self._validate_preferences(preferences)
        return self._renderer.resolve_run_bucket(
            output_root=self.effective_output_root(preferences),
            path_pattern=preferences.organization.path_pattern,
            context=OutputPathRenderContext(
                workflow_name=workflow_name,
                source="",
                cube="",
                output_run_number=None,
                cube_number=None,
                folder_image_number=None,
                job_started_at=job_started_at,
                width=0,
                height=0,
                index=1,
                set_index=1,
                seed=seed,
            ),
        )

    def output_run_projection_cache_key(self, *, now: datetime) -> Hashable:
        """Return dependencies that can change pending run projection."""

        preferences = self.load_preferences()
        effective_root = self.effective_output_root(preferences)
        pattern = preferences.organization.path_pattern
        time_tokens = self._renderer.bucket_affecting_time_tokens(pattern)
        return (
            str(Path(effective_root).resolve()).replace("\\", "/").casefold(),
            pattern,
            tuple(
                (token, _projection_time_token_value(token, now))
                for token in time_tokens
            ),
        )

    def example_render_context(self) -> OutputPathRenderContext:
        """Return deterministic example values for settings previews."""

        return OutputPathRenderContext(
            workflow_name="My Workflow",
            source="Main Output",
            cube="Main Output",
            output_run_number=7,
            cube_number=1,
            folder_image_number=1,
            job_started_at=datetime(2026, 5, 1, 14, 32, 9),
            width=1024,
            height=1024,
            index=1,
            set_index=1,
            seed="123456789",
        )

    def _normalize(self, preferences: OutputPreferences) -> OutputPreferences:
        """Return current-schema preferences with bounded numeric values."""

        organization = preferences.organization
        return OutputPreferences(
            schema_version=OUTPUT_PREFERENCES_SCHEMA_VERSION,
            organization=OutputOrganizationSettings(
                output_root=organization.output_root,
                path_pattern=organization.path_pattern or DEFAULT_OUTPUT_PATH_PATTERN,
            ),
            jpeg=JpegOutputSettings(
                enabled=preferences.jpeg.enabled,
                sizing_mode=preferences.jpeg.sizing_mode,
                quality=max(1, min(preferences.jpeg.quality, 100)),
                target_size_kib=max(1, preferences.jpeg.target_size_kib),
            ),
            persistence_mode=preferences.persistence_mode,
        )

    def _validate_preferences(self, preferences: OutputPreferences) -> None:
        """Validate filesystem, template, and JPEG constraints."""

        output_root = self.effective_output_root(preferences)
        if not output_root.is_absolute():
            raise OutputPathTemplateError("Output root must be an absolute path.")
        if output_root.exists() and not output_root.is_dir():
            raise OutputPathTemplateError("Output root must be a folder.")
        self._renderer.validate_pattern(preferences.organization.path_pattern)
        if preferences.jpeg.sizing_mode is JpegSizingMode.QUALITY:
            if not 1 <= preferences.jpeg.quality <= 100:
                raise ValueError("JPEG quality must be between 1 and 100.")
        elif preferences.jpeg.target_size_kib < 1:
            raise ValueError("JPEG target size must be positive.")
        self.render_preview(preferences)


def _projection_time_token_value(token: str, now: datetime) -> str:
    """Return the cache-key value for one bucket-affecting time token."""

    if token == "date":
        return now.strftime("%Y-%m-%d")
    if token == "day":
        return now.strftime("%A")
    if token == "time":
        return now.strftime("%H-%M-%S")
    return ""


def _alias_keys(aliases: tuple[str, ...] | frozenset[str]) -> frozenset[str]:
    """Return raw and display-form aliases used by backend source identities."""

    keys: set[str] = set()
    for alias in aliases:
        keys.add(alias)
        body = cube_alias_body(alias)
        if body:
            keys.add(body)
    return frozenset(keys)


__all__ = ["OutputPreferenceSaveResult", "OutputPreferenceService"]
