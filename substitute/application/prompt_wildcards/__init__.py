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

"""Expose native prompt wildcard preprocessing services."""

from __future__ import annotations

from .resolver import (
    PromptWildcardResolutionContext,
    PromptWildcardResolver,
    PromptWildcardSourceProvider,
)
from .file_management import (
    PromptWildcardFileEntry,
    PromptWildcardFileManagementService,
    PromptWildcardFileRepository,
)
from .preprocessing_service import PromptWildcardPreprocessingService
from .preprocessing_context import (
    PromptWildcardPreprocessingContext,
    WildcardExactResolutionCacheKey,
    WildcardPromptFieldSeedKey,
    WildcardShouldResolveCacheKey,
)
from .preferences import (
    PromptWildcardPreferenceService,
    PromptWildcardPreferences,
)
from .seed_policy import PromptWildcardSeedPolicy, PromptWildcardSeedSelection

__all__ = [
    "PromptWildcardPreprocessingService",
    "PromptWildcardPreprocessingContext",
    "PromptWildcardFileEntry",
    "PromptWildcardFileManagementService",
    "PromptWildcardFileRepository",
    "PromptWildcardPreferenceService",
    "PromptWildcardPreferences",
    "PromptWildcardResolutionContext",
    "PromptWildcardResolver",
    "PromptWildcardSeedPolicy",
    "PromptWildcardSeedSelection",
    "PromptWildcardSourceProvider",
    "WildcardExactResolutionCacheKey",
    "WildcardPromptFieldSeedKey",
    "WildcardShouldResolveCacheKey",
]
