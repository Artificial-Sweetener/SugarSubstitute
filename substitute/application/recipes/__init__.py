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

"""Expose recipe-oriented application services."""

from __future__ import annotations

from substitute.application.recipes.recipe_io_service import (
    ParsedRecipeDocument,
    RecipeIoService,
)
from substitute.application.recipes.model_resolution_index import (
    LocalRecipeModel,
    RecipeModelResolutionIndex,
)
from substitute.application.recipes.model_hash_lookup import (
    CachedModelCatalogLookup,
    CachedRecipeModelHashLookup,
    RecipeModelHashLookup,
)
from substitute.application.recipes.prompt_lora_hash_lookup import (
    CachedPromptLoraHashLookup,
    MemoizedPromptLoraHashLookup,
    PromptLoraHashLookup,
)
from substitute.application.recipes.recipe_serialization_context import (
    RecipePromptFieldOverrides,
    RecipeSerializationContext,
    RecipeSerializationPlan,
)
from substitute.application.recipes.model_download_resolution import (
    RecipeModelDownloadResolutionError,
    RecipeModelDownloadResolutionService,
)
from substitute.application.recipes.model_load_resolution import (
    RecipeModelCivitaiState,
    RecipeModelDownloadCandidate,
    RecipeModelLoadResolver,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
    RecipeModelUnresolvedReference,
    ResolvedRecipeModelScript,
)
from substitute.application.recipes.workflow_export_service import WorkflowExportService
from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)

__all__ = [
    "ParsedRecipeDocument",
    "RecipeIoService",
    "LocalRecipeModel",
    "CachedModelCatalogLookup",
    "CachedRecipeModelHashLookup",
    "CachedPromptLoraHashLookup",
    "MemoizedPromptLoraHashLookup",
    "RecipePromptFieldOverrides",
    "RecipeSerializationContext",
    "RecipeSerializationPlan",
    "RecipeModelResolutionIndex",
    "RecipeModelHashLookup",
    "PromptLoraHashLookup",
    "RecipeModelDownloadResolutionError",
    "RecipeModelDownloadResolutionService",
    "RecipeModelCivitaiState",
    "RecipeModelDownloadCandidate",
    "RecipeModelLoadResolver",
    "RecipeModelResolutionRequired",
    "RecipeModelResolutionSummary",
    "RecipeModelUnresolvedReference",
    "ResolvedRecipeModelScript",
    "WorkflowExportService",
    "executable_prompt_nodes",
]
