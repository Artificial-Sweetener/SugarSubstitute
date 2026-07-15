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

"""Cache wildcard preprocessing decisions within one generation request."""

from __future__ import annotations

from dataclasses import dataclass, field

from substitute.application.prompt_wildcards.resolver import (
    PromptWildcardResolutionContext,
)
from substitute.application.prompt_wildcards.seed_policy import (
    PromptWildcardSeedSelection,
)
from substitute.domain.prompt import (
    PromptWildcardResolution,
    PromptWildcardSyntaxProfile,
)


@dataclass(frozen=True, slots=True)
class WildcardShouldResolveCacheKey:
    """Identify one wildcard parse decision for exact prompt text and syntax."""

    prompt_text: str
    syntax_profile: PromptWildcardSyntaxProfile


@dataclass(frozen=True, slots=True)
class WildcardPromptFieldSeedKey:
    """Identify seed selection for one prompt field in a workflow request."""

    workflow_id: str
    prompt_cube_alias: str
    prompt_node_name: str
    prompt_field_key: str


@dataclass(frozen=True, slots=True)
class WildcardExactResolutionCacheKey:
    """Identify one exact wildcard resolution result within a request."""

    prompt_text: str
    effective_seed: int | None
    syntax_profile: PromptWildcardSyntaxProfile


@dataclass(slots=True)
class PromptWildcardPreprocessingContext:
    """Cache wildcard preprocessing work within one generation request."""

    resolution_context: PromptWildcardResolutionContext = field(
        default_factory=PromptWildcardResolutionContext
    )
    should_resolve_by_text: dict[WildcardShouldResolveCacheKey, bool] = field(
        default_factory=dict
    )
    seed_selection_by_field: dict[
        WildcardPromptFieldSeedKey,
        PromptWildcardSeedSelection,
    ] = field(default_factory=dict)
    exact_resolution_by_text: dict[
        WildcardExactResolutionCacheKey,
        PromptWildcardResolution,
    ] = field(default_factory=dict)
    exact_resolution_cache_hits: int = 0
    exact_resolution_cache_misses: int = 0
    resolve_on_generation: bool | None = None
    syntax_profile: PromptWildcardSyntaxProfile | None = None


__all__ = [
    "PromptWildcardPreprocessingContext",
    "WildcardExactResolutionCacheKey",
    "WildcardPromptFieldSeedKey",
    "WildcardShouldResolveCacheKey",
]
