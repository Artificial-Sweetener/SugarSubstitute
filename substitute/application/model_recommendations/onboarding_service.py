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

"""Coordinate cancellable existing-model scans and family recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
from typing import Protocol

from substitute.application.execution import CancellationToken
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import (
    ModelFamilyId,
    ModelFamilyScanResult,
    ModelRecommendation,
    ModelRecommendationQuery,
)

_RECOMMENDATION_PAGE_SIZE = 8
_LOGGER = logging.getLogger(__name__)


class ModelFamilyScanner(Protocol):
    """Read supported-family evidence from one explicit local root."""

    def scan(
        self,
        root: Path,
        *,
        cancellation: CancellationToken,
    ) -> ModelFamilyScanResult:
        """Return one bounded read-only scan result."""


class FamilyRecommendationGateway(Protocol):
    """Return safe exact-family CivitAI recommendations."""

    def discover(
        self,
        query: ModelRecommendationQuery,
        *,
        limit: int = 5,
        excluded_sha256: frozenset[str] = frozenset(),
    ) -> tuple[ModelRecommendation, ...]:
        """Return provider-ordered recommendation cards."""

    def resolve_model_page(
        self,
        family_id: ModelFamilyId,
        url: str,
    ) -> ModelRecommendation | None:
        """Resolve one trusted CivitAI model page to an exact compatible file."""


class RecommendationThumbnailFetcher(Protocol):
    """Return one validated provider thumbnail payload."""

    def fetch(self, recommendation: ModelRecommendation) -> ThumbnailAsset:
        """Fetch one governed, Qt-ready safe thumbnail."""


@dataclass(frozen=True, slots=True)
class RecommendationCardAsset:
    """Carry one recommendation and its independently loaded image state."""

    recommendation: ModelRecommendation
    thumbnail: ThumbnailAsset | None = None
    thumbnail_failed: bool = False


@dataclass(frozen=True, slots=True)
class FamilyRecommendationPage:
    """Carry one catalog-ordered family page while its thumbnails load."""

    family_id: ModelFamilyId
    cards: tuple[RecommendationCardAsset, ...]
    imported_cards: tuple[RecommendationCardAsset, ...] = ()

    @property
    def all_cards(self) -> tuple[RecommendationCardAsset, ...]:
        """Return curated and user-imported cards in stable review order."""

        return self.cards + self.imported_cards


class RecommendationLinkStatus(str, Enum):
    """Describe one CivitAI link without leaking provider diagnostics into UI."""

    READY = "ready"
    INVALID = "invalid"
    INCOMPATIBLE = "incompatible"
    DUPLICATE = "duplicate"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RecommendationLinkResult:
    """Carry the resolved cards and stable status for every submitted link."""

    source_url: str
    status: RecommendationLinkStatus
    card: RecommendationCardAsset | None = None


class ModelOnboardingApplicationService:
    """Own local scanning and CivitAI page construction outside presentation."""

    def __init__(
        self,
        *,
        scanner: ModelFamilyScanner,
        gateway: FamilyRecommendationGateway,
        thumbnail_fetcher: RecommendationThumbnailFetcher,
    ) -> None:
        """Store safe model-onboarding boundaries."""

        self._scanner = scanner
        self._gateway = gateway
        self._thumbnail_fetcher = thumbnail_fetcher

    def scan(
        self,
        root: Path,
        *,
        cancellation: CancellationToken,
    ) -> ModelFamilyScanResult:
        """Scan one explicitly selected root through the bounded scanner."""

        return self._scanner.scan(root, cancellation=cancellation)

    def recommend(
        self,
        families: tuple[ModelFamilyId, ...],
        *,
        cancellation: CancellationToken,
        excluded_sha256: frozenset[str] = frozenset(),
    ) -> tuple[FamilyRecommendationPage, ...]:
        """Build ordered pages without waiting for their image downloads."""

        pages: list[FamilyRecommendationPage] = []
        for family_id in families:
            if cancellation.is_cancelled:
                break
            recommendations = self._gateway.discover(
                ModelRecommendationQuery(family_id),
                limit=_RECOMMENDATION_PAGE_SIZE,
                excluded_sha256=excluded_sha256,
            )
            cards = tuple(
                RecommendationCardAsset(recommendation)
                for recommendation in recommendations[:_RECOMMENDATION_PAGE_SIZE]
            )
            pages.append(FamilyRecommendationPage(family_id, cards))
        return tuple(pages)

    def resolve_model_links(
        self,
        family_id: ModelFamilyId,
        urls: tuple[str, ...],
        *,
        cancellation: CancellationToken,
        excluded_version_ids: frozenset[int] = frozenset(),
    ) -> tuple[RecommendationLinkResult, ...]:
        """Resolve, validate, and preview explicit CivitAI links in input order."""

        results: list[RecommendationLinkResult] = []
        seen_urls: set[str] = set()
        seen_versions = set(excluded_version_ids)
        for source_url in urls:
            if cancellation.is_cancelled:
                break
            normalized_url = source_url.strip()
            if not normalized_url:
                results.append(
                    RecommendationLinkResult(
                        source_url,
                        RecommendationLinkStatus.INVALID,
                    )
                )
                continue
            if normalized_url.casefold() in seen_urls:
                results.append(
                    RecommendationLinkResult(
                        source_url,
                        RecommendationLinkStatus.DUPLICATE,
                    )
                )
                continue
            seen_urls.add(normalized_url.casefold())
            try:
                recommendation = self._gateway.resolve_model_page(
                    family_id,
                    normalized_url,
                )
            except ValueError:
                results.append(
                    RecommendationLinkResult(
                        source_url,
                        RecommendationLinkStatus.INVALID,
                    )
                )
                continue
            except (OSError, RuntimeError) as error:
                _LOGGER.warning(
                    "CivitAI model-link resolution failed",
                    extra={"model_family_id": family_id.value},
                    exc_info=error,
                )
                results.append(
                    RecommendationLinkResult(
                        source_url,
                        RecommendationLinkStatus.UNAVAILABLE,
                    )
                )
                continue
            if recommendation is None:
                results.append(
                    RecommendationLinkResult(
                        source_url,
                        RecommendationLinkStatus.INCOMPATIBLE,
                    )
                )
                continue
            if recommendation.version_id in seen_versions:
                results.append(
                    RecommendationLinkResult(
                        source_url,
                        RecommendationLinkStatus.DUPLICATE,
                    )
                )
                continue
            seen_versions.add(recommendation.version_id)
            try:
                thumbnail = self.fetch_thumbnail(
                    recommendation,
                    cancellation=cancellation,
                )
                card = RecommendationCardAsset(recommendation, thumbnail=thumbnail)
            except (OSError, RuntimeError, ValueError) as error:
                if cancellation.is_cancelled:
                    break
                _LOGGER.warning(
                    "CivitAI model-link preview failed",
                    extra={
                        "model_family_id": family_id.value,
                        "model_version_id": recommendation.version_id,
                    },
                    exc_info=error,
                )
                card = RecommendationCardAsset(
                    recommendation,
                    thumbnail_failed=True,
                )
            results.append(
                RecommendationLinkResult(
                    source_url,
                    RecommendationLinkStatus.READY,
                    card,
                )
            )
        return tuple(results)

    def fetch_thumbnail(
        self,
        recommendation: ModelRecommendation,
        *,
        cancellation: CancellationToken,
    ) -> ThumbnailAsset:
        """Load one governed thumbnail after recommendation metadata is visible."""

        if cancellation.is_cancelled:
            raise RuntimeError("Recommendation thumbnail request was cancelled.")
        thumbnail = self._thumbnail_fetcher.fetch(recommendation)
        if cancellation.is_cancelled:
            raise RuntimeError("Recommendation thumbnail request was cancelled.")
        return thumbnail


__all__ = [
    "FamilyRecommendationGateway",
    "FamilyRecommendationPage",
    "ModelOnboardingApplicationService",
    "ModelFamilyScanner",
    "RecommendationCardAsset",
    "RecommendationLinkResult",
    "RecommendationLinkStatus",
    "RecommendationThumbnailFetcher",
]
