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

"""Expose generation-domain value objects."""

from __future__ import annotations

from substitute.domain.generation.asset_staging_models import (
    AssetStagingFailure,
    ComfyStagedAsset,
)
from substitute.domain.generation.job_queue import (
    GenerationCubeExecutionDuration,
    GenerationJobOutputRecord,
    GenerationJobSnapshot,
    GenerationJobStatus,
    GenerationQueueJob,
    TERMINAL_GENERATION_JOB_STATUSES,
)
from substitute.domain.generation.preview_preferences import (
    GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION,
    GenerationPreviewMethod,
    GenerationPreviewPreferences,
    TaesdPreviewAsset,
    TaesdPreviewAssetState,
    TaesdPreviewAssetStatus,
    default_generation_preview_preferences,
)
from substitute.domain.generation.output_organization import (
    DEFAULT_OUTPUT_PATH_PATTERN,
    OUTPUT_ORGANIZATION_PREFERENCES_SCHEMA_VERSION,
    SUPPORTED_OUTPUT_PATH_TOKEN_NAMES,
    SUPPORTED_OUTPUT_PATH_TOKENS,
    OutputOrganizationPreferences,
    OutputPathPattern,
    OutputPathRenderContext,
    OutputPathRenderResult,
    OutputPathToken,
    OutputRunBucket,
    default_output_organization_preferences,
)
from substitute.domain.generation.output_position import OutputResultPosition
from substitute.domain.generation.result_snapshot import (
    GENERATION_RESULT_SNAPSHOT_SCHEMA_VERSION,
    GenerationResultSnapshot,
)
from substitute.domain.generation.seed_control import (
    SeedControlState,
    SeedMode,
    seed_control_state_from_json,
    seed_control_state_to_json,
    seed_mode_from_value,
)

__all__ = [
    "AssetStagingFailure",
    "ComfyStagedAsset",
    "DEFAULT_OUTPUT_PATH_PATTERN",
    "GENERATION_PREVIEW_PREFERENCES_SCHEMA_VERSION",
    "GENERATION_RESULT_SNAPSHOT_SCHEMA_VERSION",
    "GenerationCubeExecutionDuration",
    "GenerationJobOutputRecord",
    "GenerationJobSnapshot",
    "GenerationResultSnapshot",
    "GenerationJobStatus",
    "GenerationPreviewMethod",
    "GenerationPreviewPreferences",
    "GenerationQueueJob",
    "OUTPUT_ORGANIZATION_PREFERENCES_SCHEMA_VERSION",
    "OutputOrganizationPreferences",
    "OutputPathPattern",
    "OutputPathRenderContext",
    "OutputPathRenderResult",
    "OutputPathToken",
    "OutputRunBucket",
    "OutputResultPosition",
    "SUPPORTED_OUTPUT_PATH_TOKEN_NAMES",
    "SUPPORTED_OUTPUT_PATH_TOKENS",
    "SeedControlState",
    "SeedMode",
    "TERMINAL_GENERATION_JOB_STATUSES",
    "TaesdPreviewAsset",
    "TaesdPreviewAssetState",
    "TaesdPreviewAssetStatus",
    "default_generation_preview_preferences",
    "default_output_organization_preferences",
    "seed_control_state_from_json",
    "seed_control_state_to_json",
    "seed_mode_from_value",
]
