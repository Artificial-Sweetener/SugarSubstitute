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

"""Fetch safe exact-family monthly-popular recommendations from CivitAI."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
import ssl
import urllib.request
from urllib.parse import urlencode, urlparse

from sugarsubstitute_shared.tls import SystemTrustTlsContext

from substitute.domain.model_metadata import CivitaiThumbnailPolicy
from substitute.domain.model_recommendations import (
    ModelFamilyDefinition,
    ModelFamilyId,
    ModelRecommendation,
    ModelRecommendationQuery,
    SUPPORTED_MODEL_FAMILIES,
    SupportedModelFamilyCatalog,
)
from substitute.infrastructure.model_recommendations.civitai_payload_parser import (
    model_page_identity,
    parse_model,
    safe_thumbnail,
)

_API_ROOT = "https://civitai.com/api/v1"
JsonFetcher = Callable[..., object]
_LOGGER = logging.getLogger(__name__)


class CivitaiRecommendationError(RuntimeError):
    """Report a retryable transport or fail-closed provider-contract problem."""


class CivitaiFamilyRecommendationGateway:
    """Return unique exact-family cards while preserving provider popularity order."""

    def __init__(
        self,
        *,
        fetch_json: JsonFetcher | None = None,
        timeout_seconds: float = 20.0,
        catalog: SupportedModelFamilyCatalog = SUPPORTED_MODEL_FAMILIES,
        api_key_provider: Callable[[], str | None] | None = None,
        thumbnail_policy_provider: Callable[[], CivitaiThumbnailPolicy] | None = None,
        page_size: int = 20,
        maximum_pages: int = 3,
    ) -> None:
        """Store bounded provider transport, catalog, and process-lifetime enums."""

        if timeout_seconds <= 0:
            raise ValueError("CivitAI timeout must be positive.")
        if page_size < 5 or page_size > 100:
            raise ValueError("CivitAI page size must be between 5 and 100.")
        if maximum_pages < 1 or maximum_pages > 10:
            raise ValueError("CivitAI page limit must be between 1 and 10.")
        self._fetch_json = fetch_json or _fetch_json
        self._timeout_seconds = timeout_seconds
        self._catalog = catalog
        self._api_key_provider = api_key_provider
        self._thumbnail_policy_provider = thumbnail_policy_provider
        self._page_size = page_size
        self._maximum_pages = maximum_pages
        self._validated_base_models: frozenset[str] | None = None

    def discover(
        self,
        query: ModelRecommendationQuery,
        *,
        limit: int = 5,
        excluded_sha256: frozenset[str] = frozenset(),
    ) -> tuple[ModelRecommendation, ...]:
        """Return a bounded provider-ordered candidate set for one exact family."""

        if limit < 1 or limit > 20:
            raise ValueError("Onboarding recommendation limit must be 1 through 20.")
        family = self._catalog.get(query.family_id)
        self._validate_provider_mapping(family)
        seen_hashes = {value.casefold() for value in excluded_sha256}
        cards: list[ModelRecommendation] = []
        next_url: str | None = self._models_url(family)
        pages = 0
        provider_position = 0
        while (
            next_url is not None and pages < self._maximum_pages and len(cards) < limit
        ):
            payload = self._request(next_url, purpose="model recommendations")
            pages += 1
            if not isinstance(payload, dict) or not isinstance(
                payload.get("items"), list
            ):
                raise CivitaiRecommendationError(
                    "CivitAI model recommendations returned an invalid response."
                )
            for item in payload["items"]:
                provider_position += 1
                rank = provider_position
                card = parse_model(
                    item,
                    family=family,
                    popularity_rank=rank,
                    fallback_thumbnail=self._fallback_thumbnail,
                    thumbnail_policy=self._thumbnail_policy(),
                    accepted_base_models=frozenset(
                        {family.civitai.recommendation_base_model}
                    ),
                )
                if (
                    card is None
                    or card.model_id in {existing.model_id for existing in cards}
                    or card.sha256.casefold() in seen_hashes
                ):
                    continue
                cards.append(card)
                seen_hashes.add(card.sha256.casefold())
                if len(cards) == limit:
                    break
            next_url = _next_page(payload)
        return tuple(cards)

    def resolve_model_page(
        self,
        family_id: ModelFamilyId,
        url: str,
    ) -> ModelRecommendation | None:
        """Resolve one public CivitAI model URL to a safe compatible version."""

        model_id, version_id = model_page_identity(url)
        family = self._catalog.get(family_id)
        payload = self._request(
            f"{_API_ROOT}/models/{model_id}",
            purpose="linked model lookup",
        )
        return parse_model(
            payload,
            family=family,
            popularity_rank=0,
            fallback_thumbnail=self._fallback_thumbnail,
            thumbnail_policy=self._thumbnail_policy(),
            accepted_base_models=self._recognized_linked_base_models(family),
            target_version_id=version_id,
        )

    def _validate_provider_mapping(self, family: ModelFamilyDefinition) -> None:
        """Fail closed when the live provider no longer recognizes a family mapping."""

        if family.civitai.recommendation_base_model not in self._provider_base_models():
            raise CivitaiRecommendationError(
                "CivitAI no longer recognizes the configured model family."
            )

    def _recognized_linked_base_models(
        self,
        family: ModelFamilyDefinition,
    ) -> frozenset[str]:
        """Return configured linked-model labels still advertised by CivitAI."""

        recognized = family.civitai.linked_base_models & self._provider_base_models()
        if not recognized:
            raise CivitaiRecommendationError(
                "CivitAI no longer recognizes the configured model family."
            )
        return recognized

    def _provider_base_models(self) -> frozenset[str]:
        """Return CivitAI's process-cached current base-model enumeration."""

        if self._validated_base_models is None:
            payload = self._request(f"{_API_ROOT}/enums", purpose="enum validation")
            self._validated_base_models = _base_model_values(payload)
        return self._validated_base_models

    def _models_url(self, family: ModelFamilyDefinition) -> str:
        """Build the configured monthly-popularity query for one family."""

        return f"{_API_ROOT}/models?{urlencode({'limit': str(self._page_size), 'types': family.civitai.model_type, 'baseModels': family.civitai.recommendation_base_model, 'sort': 'Most Downloaded', 'period': 'Month', 'nsfw': 'false', 'earlyAccess': 'false', 'primaryFileOnly': 'true'})}"

    def _fallback_thumbnail(self, version_id: int) -> tuple[int, str] | None:
        """Return a safe large portrait from the version's public image gallery."""

        url = f"{_API_ROOT}/images?{urlencode({'limit': '20', 'modelVersionId': str(version_id), 'sort': 'Most Reactions', 'period': 'AllTime', 'nsfw': 'None', 'type': 'image'})}"
        try:
            payload = self._request(url, purpose="model preview images")
        except CivitaiRecommendationError:
            _LOGGER.warning(
                "CivitAI preview lookup failed",
                extra={"model_version_id": version_id},
                exc_info=True,
            )
            return None
        if not isinstance(payload, dict):
            return None
        return safe_thumbnail(
            payload.get("items"),
            thumbnail_policy=self._thumbnail_policy(),
        )

    def _thumbnail_policy(self) -> CivitaiThumbnailPolicy:
        """Return the current user-owned CivitAI preview-content policy."""

        provider = self._thumbnail_policy_provider
        return CivitaiThumbnailPolicy() if provider is None else provider()

    def _request(self, url: str, *, purpose: str) -> object:
        """Fetch provider JSON with bounded time and sanitized failures."""

        if not _is_civitai_api_url(url):
            raise CivitaiRecommendationError(
                "CivitAI pagination returned an unsafe URL."
            )
        headers = {"Accept": "application/json", "User-Agent": "SugarSubstitute/1.0"}
        api_key = self._api_key_provider() if self._api_key_provider else None
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            return self._fetch_json(url, headers=headers, timeout=self._timeout_seconds)
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            raise CivitaiRecommendationError(
                f"CivitAI {purpose} is temporarily unavailable."
            ) from error


def _base_model_values(payload: object) -> frozenset[str]:
    """Read current base-model values from supported enum response shapes."""

    if not isinstance(payload, dict):
        raise CivitaiRecommendationError(
            "CivitAI enum validation returned invalid data."
        )
    values: set[str] = set()
    for key in ("BaseModel", "ActiveBaseModel"):
        candidates = payload.get(key)
        if isinstance(candidates, list):
            values.update(item for item in candidates if isinstance(item, str))
    if not values:
        raise CivitaiRecommendationError(
            "CivitAI enum validation returned no model families."
        )
    return frozenset(values)


def _next_page(payload: dict[str, object]) -> str | None:
    """Return a trusted provider next-page URL when present."""

    metadata = payload.get("metadata")
    value = metadata.get("nextPage") if isinstance(metadata, dict) else None
    return _text(value)


def _fetch_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    tls_context: ssl.SSLContext | None = None,
) -> object:
    """Fetch one CivitAI JSON payload through system trust."""

    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(  # noqa: S310 - origin is validated before fetch.
        request,
        timeout=timeout,
        context=tls_context or SystemTrustTlsContext.create(),
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _is_civitai_api_url(value: str) -> bool:
    """Return whether a URL is a fixed-origin CivitAI API route."""

    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "civitai.com"
        and parsed.path.startswith("/api/v1/")
    )


def _text(value: object) -> str | None:
    """Return a stripped non-empty provider string."""

    return value.strip() if isinstance(value, str) and value.strip() else None


__all__ = ["CivitaiFamilyRecommendationGateway", "CivitaiRecommendationError"]
