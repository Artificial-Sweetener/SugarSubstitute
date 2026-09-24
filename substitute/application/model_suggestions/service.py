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
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_suggestions import (
    ModelAcquisitionOffer,
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
        offer: ModelAcquisitionOffer,
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
        excluded_hashes = {value.casefold() for value in excluded_sha256}
        suggestions: list[ModelSuggestion] = []
        suggestion_indexes: dict[str, int] = {}
        for provider in self._providers:
            if not provider.supports(context):
                continue
            for suggestion in provider.suggest(
                context,
                access_policy=access_policy,
                limit=limit,
                excluded_sha256=frozenset(excluded_hashes),
            ):
                if len(suggestion.offers) != 1:
                    raise ValueError(
                        "Model suggestion providers must return one owned offer."
                    )
                offer = suggestion.primary_offer
                if offer.reference.provider_id != provider.provider_id:
                    raise ValueError(
                        "Model suggestion provider returned another provider's identity."
                    )
                normalized_hash = suggestion.sha256.casefold()
                if suggestion.context != context or normalized_hash in excluded_hashes:
                    continue
                existing_index = suggestion_indexes.get(normalized_hash)
                if existing_index is not None:
                    existing = suggestions[existing_index]
                    if existing.offer_for_provider(provider.provider_id) is None:
                        suggestions[existing_index] = replace(
                            existing,
                            offers=(*existing.offers, offer),
                        )
                    continue
                if len(suggestions) == limit:
                    continue
                suggestion_indexes[normalized_hash] = len(suggestions)
                suggestions.append(suggestion)
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

        return self._provider(suggestion.primary_offer).fetch_thumbnail(suggestion)

    def acquire(
        self,
        suggestion: ModelSuggestion,
        *,
        provider_id: str | None = None,
        destination: Path,
        cancellation: CancellationProbe | None = None,
    ) -> AcquisitionResult:
        """Acquire a suggestion through its owning provider."""

        offer = (
            suggestion.primary_offer
            if provider_id is None
            else suggestion.offer_for_provider(provider_id)
        )
        if offer is None:
            raise ValueError(f"Provider has no offer for suggestion: {provider_id}")
        return self._provider(offer).acquire(
            suggestion,
            offer,
            destination=destination,
            cancellation=cancellation,
        )

    def _provider(self, offer: ModelAcquisitionOffer) -> ModelSuggestionProvider:
        """Return the exact registered provider for one acquisition offer."""

        provider_id = offer.reference.provider_id
        for provider in self._providers:
            if provider.provider_id == provider_id:
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

        return self._plan(context, ModelSuggestionAccessPolicy.CURRENT_USER)

    def plan_public_picker(
        self, context: ModelSuggestionContext
    ) -> ModelSuggestionPlan:
        """Return compatible choices downloadable without provider credentials."""

        return self._plan(context, ModelSuggestionAccessPolicy.PUBLIC_ONLY)

    def _plan(
        self,
        context: ModelSuggestionContext,
        access_policy: ModelSuggestionAccessPolicy,
    ) -> ModelSuggestionPlan:
        """Build one destination-safe plan under the requested access policy."""

        suggestions = self._engine.suggest(
            context,
            access_policy=access_policy,
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
        provider_id: str | None = None,
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
            provider_id=provider_id,
            destination=plan.destination,
            cancellation=cancellation,
        )
        return suggestion, result


__all__ = [
    "ModelSuggestionEngine",
    "ModelSuggestionProvider",
    "ModelSuggestionService",
]
