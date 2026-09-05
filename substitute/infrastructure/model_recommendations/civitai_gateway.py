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
import re
import ssl
from typing import Any
import urllib.request
from urllib.parse import urlencode, urlparse

from sugarsubstitute_shared.tls import SystemTrustTlsContext

from substitute.domain.model_metadata import CivitaiImage, CivitaiThumbnailPolicy
from substitute.domain.model_recommendations import (
    ModelFamilyDefinition,
    ModelRecommendation,
    ModelRecommendationQuery,
    SUPPORTED_MODEL_FAMILIES,
    SupportedModelFamilyCatalog,
)

_API_ROOT = "https://civitai.com/api/v1"
_THUMBNAIL_POLICY = CivitaiThumbnailPolicy()
_MIN_PORTRAIT_WIDTH = 640
_MIN_PORTRAIT_HEIGHT = 800
_PORTRAIT_PREVIEW_WIDTH = 1024
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
                card = _parse_model(
                    item,
                    family=family,
                    popularity_rank=rank,
                    fallback_thumbnail=self._fallback_thumbnail,
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

    def _validate_provider_mapping(self, family: ModelFamilyDefinition) -> None:
        """Fail closed when the live provider no longer recognizes a family mapping."""

        if self._validated_base_models is None:
            payload = self._request(f"{_API_ROOT}/enums", purpose="enum validation")
            self._validated_base_models = _base_model_values(payload)
        if family.civitai.recommendation_base_model not in self._validated_base_models:
            raise CivitaiRecommendationError(
                "CivitAI no longer recognizes the configured model family."
            )

    def _models_url(self, family: ModelFamilyDefinition) -> str:
        """Build the configured monthly-popularity query for one family."""

        return f"{_API_ROOT}/models?{urlencode({'limit': str(self._page_size), 'types': family.civitai.model_type, 'baseModels': family.civitai.recommendation_base_model, 'sort': 'Most Downloaded', 'period': 'Month', 'nsfw': 'false', 'earlyAccess': 'false', 'primaryFileOnly': 'true'})}"

    def _fallback_thumbnail(self, version_id: int) -> str | None:
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
        return _safe_thumbnail(payload.get("items"))

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


def _parse_model(
    value: object,
    *,
    family: ModelFamilyDefinition,
    popularity_rank: int,
    fallback_thumbnail: Callable[[int], str | None],
) -> ModelRecommendation | None:
    """Parse one public model and choose its first exact-family eligible version."""

    if not isinstance(value, dict):
        return None
    model_id = _positive_integer(value.get("id"))
    model_name = _text(value.get("name"))
    if (
        model_id is None
        or model_name is None
        or _text(value.get("type")) != family.civitai.model_type
        or value.get("nsfw") is not False
        or value.get("mode") is not None
    ):
        return None
    creator = value.get("creator")
    creator_name = _text(creator.get("username")) if isinstance(creator, dict) else None
    versions = value.get("modelVersions")
    if not isinstance(versions, list):
        return None
    for version in versions:
        parsed = _parse_version(
            version,
            expected_base_model=family.civitai.recommendation_base_model,
            fallback_thumbnail=fallback_thumbnail,
        )
        if parsed is None:
            continue
        (
            version_id,
            version_name,
            file_name,
            size_bytes,
            sha256,
            download_url,
            thumbnail,
        ) = parsed
        return ModelRecommendation(
            family_id=family.family_id,
            model_id=model_id,
            version_id=version_id,
            model_name=model_name,
            version_name=version_name,
            creator=creator_name,
            file_name=file_name,
            size_bytes=size_bytes,
            sha256=sha256,
            download_url=download_url,
            model_page_url=f"https://civitai.com/models/{model_id}?modelVersionId={version_id}",
            thumbnail_url=thumbnail,
            popularity_rank=popularity_rank,
        )
    return None


def _parse_version(
    value: object,
    *,
    expected_base_model: str,
    fallback_thumbnail: Callable[[int], str | None],
) -> tuple[int, str, str, int, str, str, str] | None:
    """Return one exact-family version with a safe image and verified primary file."""

    if not isinstance(value, dict):
        return None
    version_id = _positive_integer(value.get("id"))
    version_name = _text(value.get("name"))
    base_model = _text(value.get("baseModel"))
    availability = _text(value.get("availability"))
    if (
        version_id is None
        or version_name is None
        or base_model != expected_base_model
        or (availability is not None and availability.casefold() != "public")
    ):
        return None
    thumbnail = _safe_thumbnail(value.get("images"))
    if thumbnail is None:
        thumbnail = fallback_thumbnail(version_id)
        if thumbnail is None:
            return None
    files = value.get("files")
    if not isinstance(files, list):
        return None
    ordered = sorted(
        (item for item in files if isinstance(item, dict)),
        key=lambda item: item.get("primary") is not True,
    )
    for item in ordered:
        parsed = _safe_file(item)
        if parsed is not None:
            return (version_id, version_name, *parsed, thumbnail)
    return None


def _safe_file(value: dict[str, Any]) -> tuple[str, int, str, str] | None:
    """Return a published scan-clean SafeTensor file or reject it."""

    name = _text(value.get("name"))
    download_url = _text(value.get("downloadUrl"))
    size_kb = _number(value.get("sizeKB"))
    metadata = value.get("metadata")
    hashes = value.get("hashes")
    file_format = _text(metadata.get("format")) if isinstance(metadata, dict) else None
    sha256 = _text(hashes.get("SHA256")) if isinstance(hashes, dict) else None
    if (
        name is None
        or not name.casefold().endswith(".safetensors")
        or download_url is None
        or not _is_civitai_download_url(download_url)
        or size_kb is None
        or size_kb <= 0
        or sha256 is None
        or not _is_sha256(sha256)
        or file_format is None
        or file_format.casefold() != "safetensor"
        or _text(value.get("pickleScanResult")) != "Success"
        or _text(value.get("virusScanResult")) != "Success"
    ):
        return None
    return name, int(round(size_kb * 1024)), sha256.casefold(), download_url


def _safe_thumbnail(value: object) -> str | None:
    """Return the first safe high-resolution portrait hosted by CivitAI."""

    if not isinstance(value, list):
        return None
    for image in value:
        if not isinstance(image, dict):
            continue
        url = _text(image.get("url"))
        normalized = CivitaiImage(
            image_id=_positive_integer(image.get("id")),
            url=url or "",
            image_type=_text(image.get("type")),
            nsfw=image.get("nsfw") if isinstance(image.get("nsfw"), bool) else None,
            nsfw_level=(
                image.get("nsfwLevel")
                if isinstance(image.get("nsfwLevel"), (str, int))
                and not isinstance(image.get("nsfwLevel"), bool)
                else None
            ),
            width=_positive_integer(image.get("width")),
            height=_positive_integer(image.get("height")),
            meta=None,
        )
        if (
            url is not None
            and _is_civitai_asset_url(url)
            and _THUMBNAIL_POLICY.allows_image(normalized)
            and normalized.width is not None
            and normalized.height is not None
            and normalized.width >= _MIN_PORTRAIT_WIDTH
            and normalized.height >= _MIN_PORTRAIT_HEIGHT
            and normalized.height > normalized.width
        ):
            return _large_preview_url(url)
    return None


def _large_preview_url(url: str) -> str:
    """Request a bounded 1024-pixel CivitAI CDN derivative when supported."""

    return re.sub(
        r"/(?:width=\d+|original=true)/",
        f"/width={_PORTRAIT_PREVIEW_WIDTH}/",
        url,
        count=1,
    )


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


def _is_civitai_download_url(value: str) -> bool:
    """Return whether a URL is a fixed-origin CivitAI download route."""

    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"civitai.com", "www.civitai.com"}
        and parsed.path.startswith("/api/download/")
    )


def _is_civitai_asset_url(value: str) -> bool:
    """Return whether an HTTPS image uses CivitAI's domain."""

    parsed = urlparse(value)
    hostname = parsed.hostname or ""
    return parsed.scheme == "https" and (
        hostname == "civitai.com" or hostname.endswith(".civitai.com")
    )


def _is_sha256(value: str) -> bool:
    """Return whether a value is exactly one hexadecimal SHA-256 digest."""

    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value.casefold()
    )


def _text(value: object) -> str | None:
    """Return a stripped non-empty provider string."""

    return value.strip() if isinstance(value, str) and value.strip() else None


def _positive_integer(value: object) -> int | None:
    """Return a positive provider integer while rejecting booleans."""

    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _number(value: object) -> float | None:
    """Return one provider number while rejecting booleans."""

    return (
        float(value)
        if isinstance(value, (int, float)) and not isinstance(value, bool)
        else None
    )


__all__ = ["CivitaiFamilyRecommendationGateway", "CivitaiRecommendationError"]
