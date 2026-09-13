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

"""Route model suggestions and acquisition through registered providers."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Protocol

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionAccessPolicy,
    ModelSuggestionContext,
    ModelSuggestionPlan,
)
from sugarsubstitute_shared.model_acquisition import (
    AcquisitionResult,
    CancellationProbe,
)
from sugarsubstitute_shared.model_discovery import ModelArtifactKind


class ModelSuggestionProvider(Protocol):
    """Discover and acquire suggestions from one external model provider."""

    @property
    def provider_id(self) -> str:
        """Return the stable provider identifier."""

    def supports(self, context: ModelSuggestionContext) -> bool:
        """Return whether this provider understands the requested compatibility."""

    def suggest(
        self,
        context: ModelSuggestionContext,
        *,
        access_policy: ModelSuggestionAccessPolicy,
        limit: int,
        excluded_sha256: frozenset[str],
    ) -> tuple[ModelSuggestion, ...]:
        """Return provider-ranked compatible suggestions."""

    def browse_url(self, context: ModelSuggestionContext) -> str:
        """Return a public provider browse URL for the compatibility context."""

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> ThumbnailAsset:
        """Return a governed thumbnail for one suggestion."""

    def acquire(
        self,
        suggestion: ModelSuggestion,
        *,
        destination: Path,
        cancellation: CancellationProbe | None,
    ) -> AcquisitionResult:
        """Download and atomically verify one exact suggestion."""


class ModelDestinationPolicy(Protocol):
    """Resolve the target-owned model folder for one artifact role."""

    def destination_for(self, artifact_kind: ModelArtifactKind) -> Path:
        """Return the governed destination directory."""


class ModelSuggestionEngine:
    """Combine capable providers while preserving identity and hash uniqueness."""

    def __init__(self, providers: Collection[ModelSuggestionProvider]) -> None:
        """Register uniquely identified providers in deterministic priority order."""

        self._providers = tuple(providers)
        identities = tuple(provider.provider_id for provider in self._providers)
        if (
            not identities
            or any(not identity.strip() for identity in identities)
            or len(identities) != len(set(identities))
        ):
            raise ValueError("Model suggestion providers must be non-empty and unique.")

    def suggest(
        self,
        context: ModelSuggestionContext,
        *,
        access_policy: ModelSuggestionAccessPolicy,
        limit: int,
        excluded_sha256: frozenset[str] = frozenset(),
    ) -> tuple[ModelSuggestion, ...]:
        """Return deterministic provider-priority suggestions deduplicated by hash."""

        if limit < 1:
            raise ValueError("Model suggestion limit must be positive.")
        seen_hashes = {value.casefold() for value in excluded_sha256}
        suggestions: list[ModelSuggestion] = []
        for provider in self._providers:
            if not provider.supports(context):
                continue
            for suggestion in provider.suggest(
                context,
                access_policy=access_policy,
                limit=limit - len(suggestions),
                excluded_sha256=frozenset(seen_hashes),
            ):
                if suggestion.reference.provider_id != provider.provider_id:
                    raise ValueError(
                        "Model suggestion provider returned another provider's identity."
                    )
                normalized_hash = suggestion.sha256.casefold()
                if suggestion.context != context or normalized_hash in seen_hashes:
                    continue
                suggestions.append(suggestion)
                seen_hashes.add(normalized_hash)
                if len(suggestions) == limit:
                    return tuple(suggestions)
        return tuple(suggestions)

    def browse_urls(
        self, context: ModelSuggestionContext
    ) -> tuple[tuple[str, str], ...]:
        """Return provider-labelled browse URLs for capable providers."""

        return tuple(
            (provider.provider_id, provider.browse_url(context))
            for provider in self._providers
            if provider.supports(context)
        )

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> ThumbnailAsset:
        """Fetch a thumbnail through the suggestion's owning provider."""

        return self._provider(suggestion).fetch_thumbnail(suggestion)

    def acquire(
        self,
        suggestion: ModelSuggestion,
        *,
        destination: Path,
        cancellation: CancellationProbe | None = None,
    ) -> AcquisitionResult:
        """Acquire a suggestion through its owning provider."""

        return self._provider(suggestion).acquire(
            suggestion,
            destination=destination,
            cancellation=cancellation,
        )

    def _provider(self, suggestion: ModelSuggestion) -> ModelSuggestionProvider:
        """Return the exact registered provider for one suggestion."""

        provider_id = suggestion.reference.provider_id
        for provider in self._providers:
            if provider.provider_id == provider_id and provider.supports(
                suggestion.context
            ):
                return provider
        raise ValueError(f"No provider owns model suggestion: {provider_id}")


class ModelSuggestionService:
    """Plan empty-picker discovery and verified single-model acquisition."""

    def __init__(
        self,
        *,
        destinations: ModelDestinationPolicy,
        engine: ModelSuggestionEngine,
        suggestion_limit: int = 8,
    ) -> None:
        """Store target destination and provider owners."""

        if suggestion_limit < 1:
            raise ValueError("Suggestion card limit must be positive.")
        self._destinations = destinations
        self._engine = engine
        self._suggestion_limit = suggestion_limit

    def plan_empty_picker(self, context: ModelSuggestionContext) -> ModelSuggestionPlan:
        """Return compatible suggestions only while the picker remains empty."""

        suggestions = self._engine.suggest(
            context,
            access_policy=ModelSuggestionAccessPolicy.CURRENT_USER,
            limit=self._suggestion_limit,
        )
        return ModelSuggestionPlan(
            context=context,
            suggestions=suggestions,
            destination=self._destinations.destination_for(context.artifact_kind),
            browse_urls=self._engine.browse_urls(context),
        )

    def fetch_thumbnail(self, suggestion: ModelSuggestion) -> ThumbnailAsset:
        """Return one provider-routed suggestion thumbnail."""

        return self._engine.fetch_thumbnail(suggestion)

    def acquire(
        self,
        plan: ModelSuggestionPlan,
        suggestion_identity: str,
        *,
        cancellation: CancellationProbe | None = None,
    ) -> tuple[ModelSuggestion, AcquisitionResult]:
        """Acquire exactly one explicitly selected suggestion from the plan."""

        suggestion = next(
            (
                candidate
                for candidate in plan.suggestions
                if candidate.identity == suggestion_identity
            ),
            None,
        )
        if suggestion is None:
            raise ValueError("Selected model suggestion is not in the reviewed plan.")
        result = self._engine.acquire(
            suggestion,
            destination=plan.destination,
            cancellation=cancellation,
        )
        return suggestion, result


__all__ = [
    "ModelSuggestionEngine",
    "ModelSuggestionProvider",
    "ModelSuggestionService",
]
