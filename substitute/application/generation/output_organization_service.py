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

"""Coordinate output organization preference and save-plan use cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Hashable

from substitute.application.generation.output_path_template_renderer import (
    OutputPathTemplateError,
    OutputPathTemplateRenderer,
)
from substitute.application.ports.comfy_gateway import OutputSavePlan
from substitute.application.ports.output_organization_preference_repository import (
    OutputOrganizationPreferenceRepository,
)
from substitute.domain.generation import (
    DEFAULT_OUTPUT_PATH_PATTERN,
    OUTPUT_ORGANIZATION_PREFERENCES_SCHEMA_VERSION,
    OutputOrganizationPreferences,
    OutputPathRenderContext,
    OutputPathRenderResult,
    OutputPathToken,
    OutputRunBucket,
    SUPPORTED_OUTPUT_PATH_TOKENS,
    default_output_organization_preferences,
)


@dataclass(frozen=True)
class OutputOrganizationSaveResult:
    """Describe a settings-facing output organization save result."""

    preferences: OutputOrganizationPreferences
    succeeded: bool
    message: str
    preview: OutputPathRenderResult | None = None


class OutputOrganizationPreferenceService:
    """Own output organization preference validation, persistence, and previews."""

    def __init__(
        self,
        repository: OutputOrganizationPreferenceRepository,
        *,
        default_output_root: Path,
        renderer: OutputPathTemplateRenderer | None = None,
    ) -> None:
        """Initialize repository and default output root dependencies."""

        self._repository = repository
        self._default_output_root = default_output_root
        self._renderer = renderer or OutputPathTemplateRenderer()

    def load_preferences(self) -> OutputOrganizationPreferences:
        """Load normalized output organization preferences."""

        return self._normalize(self._repository.load())

    def default_preferences(self) -> OutputOrganizationPreferences:
        """Return preferences that preserve the current output layout."""

        return default_output_organization_preferences()

    def supported_tokens(self) -> tuple[str, ...]:
        """Return supported token placeholders in display order."""

        return tuple(token.placeholder for token in SUPPORTED_OUTPUT_PATH_TOKENS)

    def supported_token_descriptions(self) -> tuple[OutputPathToken, ...]:
        """Return supported output tokens with user-facing descriptions."""

        return SUPPORTED_OUTPUT_PATH_TOKENS

    def effective_output_root(
        self,
        preferences: OutputOrganizationPreferences | None = None,
    ) -> Path:
        """Return the concrete output root for preferences or current state."""

        resolved_preferences = preferences or self.load_preferences()
        return resolved_preferences.output_root or self._default_output_root

    def save_preferences(
        self,
        preferences: OutputOrganizationPreferences,
    ) -> OutputOrganizationSaveResult:
        """Persist validated output organization preferences."""

        normalized = self._normalize(preferences)
        try:
            self._validate_preferences(normalized)
        except OutputPathTemplateError as error:
            return OutputOrganizationSaveResult(
                preferences=self.load_preferences(),
                succeeded=False,
                message=str(error),
            )
        self._repository.save(normalized)
        return OutputOrganizationSaveResult(
            preferences=normalized,
            succeeded=True,
            message="Output organization settings saved.",
            preview=self.render_preview(normalized),
        )

    def reset_preferences(self) -> OutputOrganizationSaveResult:
        """Persist default output organization preferences."""

        return self.save_preferences(self.default_preferences())

    def render_preview(
        self,
        preferences: OutputOrganizationPreferences | None = None,
    ) -> OutputPathRenderResult:
        """Render the settings preview path for preferences."""

        resolved_preferences = self._normalize(
            preferences if preferences is not None else self.load_preferences()
        )
        return self._renderer.preview_path(
            output_root=self.effective_output_root(resolved_preferences),
            path_pattern=resolved_preferences.path_pattern,
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
    ) -> OutputSavePlan:
        """Create an immutable output save plan for one generation job."""

        preferences = self.load_preferences()
        self._validate_preferences(preferences)
        return OutputSavePlan(
            output_root=self.effective_output_root(preferences),
            path_pattern=preferences.path_pattern,
            workflow_name=workflow_name,
            output_run_number=output_run_number,
            job_started_at=job_started_at,
            seed=seed,
            cube_numbers_by_alias=cube_numbers_by_alias or {},
        )

    def resolve_run_bucket(
        self,
        *,
        workflow_name: str,
        job_started_at: datetime,
        seed: str = "",
    ) -> OutputRunBucket:
        """Resolve the output bucket used to allocate `{run}` for a job."""

        preferences = self.load_preferences()
        self._validate_preferences(preferences)
        return self._renderer.resolve_run_bucket(
            output_root=self.effective_output_root(preferences),
            path_pattern=preferences.path_pattern,
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
        """Return dependencies that can change visible pending run projection."""

        preferences = self.load_preferences()
        effective_root = self.effective_output_root(preferences)
        time_tokens = self._renderer.bucket_affecting_time_tokens(
            preferences.path_pattern
        )
        time_key = tuple(
            (token, _projection_time_token_value(token, now)) for token in time_tokens
        )
        return (
            str(Path(effective_root).resolve()).replace("\\", "/").casefold(),
            preferences.path_pattern,
            time_key,
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

    def _normalize(
        self,
        preferences: OutputOrganizationPreferences,
    ) -> OutputOrganizationPreferences:
        """Return preferences with current schema and fallback patterns."""

        path_pattern = preferences.path_pattern or DEFAULT_OUTPUT_PATH_PATTERN
        return OutputOrganizationPreferences(
            schema_version=OUTPUT_ORGANIZATION_PREFERENCES_SCHEMA_VERSION,
            output_root=preferences.output_root,
            path_pattern=path_pattern,
        )

    def _validate_preferences(
        self,
        preferences: OutputOrganizationPreferences,
    ) -> None:
        """Validate output root and patterns before persistence."""

        output_root = self.effective_output_root(preferences)
        if not output_root.is_absolute():
            raise OutputPathTemplateError("Output root must be an absolute path.")
        if output_root.exists() and not output_root.is_dir():
            raise OutputPathTemplateError("Output root must be a folder.")
        self._renderer.validate_pattern(preferences.path_pattern)
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


__all__ = [
    "OutputOrganizationPreferenceService",
    "OutputOrganizationSaveResult",
]
