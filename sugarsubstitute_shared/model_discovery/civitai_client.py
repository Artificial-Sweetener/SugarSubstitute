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

"""Discover safe monthly-popular model files through CivitAI's public API."""

from __future__ import annotations

from collections.abc import Callable
import json
import ssl
from typing import Any
import urllib.request
from urllib.parse import urlencode, urlparse

from sugarsubstitute_shared.model_discovery.models import (
    DiscoveredModel,
    ModelCategory,
)
from sugarsubstitute_shared.tls import SystemTrustTlsContext

_MODELS_URL = "https://civitai.com/api/v1/models"
_CIVITAI_TYPES = {
    ModelCategory.CHECKPOINTS: "Checkpoint",
    ModelCategory.DIFFUSION_MODELS: "Checkpoint",
    ModelCategory.LORAS: "LORA",
    ModelCategory.VAE: "VAE",
    ModelCategory.CONTROLNET: "Controlnet",
    ModelCategory.UPSCALE_MODELS: "Upscaler",
}
JsonFetcher = Callable[..., object]


class CivitaiDiscoveryError(RuntimeError):
    """Report an unavailable or structurally invalid discovery response."""


class CivitaiDiscoveryClient:
    """Return only public, SFW, hash-identified SafeTensor model candidates."""

    def __init__(
        self,
        *,
        fetch_json: JsonFetcher | None = None,
        timeout_seconds: float = 20.0,
        api_key_provider: Callable[[], str | None] | None = None,
    ) -> None:
        """Store the bounded transport and optional secret provider."""

        self._fetch_json = fetch_json or _fetch_json
        self._timeout_seconds = timeout_seconds
        self._api_key_provider = api_key_provider

    def discover_monthly_popular(
        self,
        category: ModelCategory,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Fetch monthly popularity order and remove every unsafe candidate."""

        if limit < 1 or limit > 100:
            raise ValueError("CivitAI discovery limit must be between 1 and 100.")
        query = urlencode(
            {
                "limit": str(limit),
                "types": _CIVITAI_TYPES[category],
                "sort": "Most Downloaded",
                "period": "Month",
                "nsfw": "false",
                "earlyAccess": "false",
                "primaryFileOnly": "true",
            }
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": "SugarSubstitute/1.0",
        }
        api_key = self._api_key_provider() if self._api_key_provider else None
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            payload = self._fetch_json(
                f"{_MODELS_URL}?{query}",
                headers=headers,
                timeout=self._timeout_seconds,
            )
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            raise CivitaiDiscoveryError("CivitAI model discovery failed.") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise CivitaiDiscoveryError(
                "CivitAI model discovery returned an invalid response."
            )
        candidates: list[DiscoveredModel] = []
        for provider_rank, item in enumerate(payload["items"], start=1):
            candidate = _parse_candidate(
                item,
                category=category,
                expected_type=_CIVITAI_TYPES[category],
                provider_rank=provider_rank,
            )
            if candidate is not None:
                candidates.append(candidate)
        return tuple(candidates)

    def discover_model_versions(
        self,
        *,
        model_id: int,
        category: ModelCategory,
    ) -> tuple[DiscoveredModel, ...]:
        """Return safe versions in provider order for compatible update checks."""

        if model_id <= 0:
            raise ValueError("CivitAI model ID must be positive.")
        headers = {
            "Accept": "application/json",
            "User-Agent": "SugarSubstitute/1.0",
        }
        api_key = self._api_key_provider() if self._api_key_provider else None
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            payload = self._fetch_json(
                f"{_MODELS_URL}/{model_id}",
                headers=headers,
                timeout=self._timeout_seconds,
            )
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            raise CivitaiDiscoveryError(
                "CivitAI model version lookup failed."
            ) from error
        candidates = _parse_candidates(
            payload,
            category=category,
            expected_type=_CIVITAI_TYPES[category],
        )
        if payload is not None and not isinstance(payload, dict):
            raise CivitaiDiscoveryError(
                "CivitAI model version lookup returned an invalid response."
            )
        return candidates


def _fetch_json(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    tls_context: ssl.SSLContext | None = None,
) -> object:
    """Fetch one HTTPS JSON object through system trust."""

    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(  # noqa: S310 - fixed HTTPS CivitAI origin.
        request,
        timeout=timeout,
        context=tls_context or SystemTrustTlsContext.create(),
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_candidate(
    value: object,
    *,
    category: ModelCategory,
    expected_type: str,
    provider_rank: int,
) -> DiscoveredModel | None:
    """Parse the first safe downloadable version of one provider model."""

    candidates = _parse_candidates(
        value,
        category=category,
        expected_type=expected_type,
        provider_rank=provider_rank,
    )
    return candidates[0] if candidates else None


def _parse_candidates(
    value: object,
    *,
    category: ModelCategory,
    expected_type: str,
    provider_rank: int = 1,
) -> tuple[DiscoveredModel, ...]:
    """Parse every safe version of one public SFW provider model."""

    if not isinstance(value, dict):
        return ()
    model_id = _integer(value.get("id"))
    model_name = _string(value.get("name"))
    model_type = _string(value.get("type"))
    if (
        model_id is None
        or model_name is None
        or model_type != expected_type
        or value.get("nsfw") is not False
        or value.get("mode") is not None
    ):
        return ()
    versions = value.get("modelVersions")
    if not isinstance(versions, list):
        return ()
    creator = value.get("creator")
    creator_name = (
        _string(creator.get("username")) if isinstance(creator, dict) else None
    )
    candidates: list[DiscoveredModel] = []
    for version_rank, version in enumerate(versions, start=provider_rank):
        parsed = _parse_version_file(version)
        if parsed is None:
            continue
        (
            version_id,
            version_name,
            base_model,
            file_name,
            size_bytes,
            sha256,
            download_url,
            thumbnail_url,
        ) = parsed
        candidates.append(
            DiscoveredModel(
                category=category,
                model_id=model_id,
                version_id=version_id,
                model_name=model_name,
                version_name=version_name,
                creator=creator_name,
                base_model=base_model,
                file_name=file_name,
                size_bytes=size_bytes,
                sha256=sha256,
                download_url=download_url,
                model_page_url=(
                    f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
                ),
                thumbnail_url=thumbnail_url,
                provider_rank=version_rank,
            )
        )
    return tuple(candidates)


def _parse_version_file(
    value: object,
) -> tuple[int, str, str | None, str, int, str, str, str | None] | None:
    """Return one exact safe primary file from a published model version."""

    if not isinstance(value, dict):
        return None
    version_id = _integer(value.get("id"))
    version_name = _string(value.get("name"))
    availability = _string(value.get("availability"))
    if (
        version_id is None
        or version_name is None
        or (availability is not None and availability.casefold() != "public")
    ):
        return None
    files = value.get("files")
    if not isinstance(files, list):
        return None
    ordered_files = sorted(
        (file for file in files if isinstance(file, dict)),
        key=lambda file: file.get("primary") is not True,
    )
    for file in ordered_files:
        parsed_file = _parse_file(file)
        if parsed_file is None:
            continue
        file_name, size_bytes, sha256, download_url = parsed_file
        return (
            version_id,
            version_name,
            _string(value.get("baseModel")),
            file_name,
            size_bytes,
            sha256,
            download_url,
            _safe_thumbnail(value.get("images")),
        )
    return None


def _parse_file(value: dict[str, Any]) -> tuple[str, int, str, str] | None:
    """Return a verified-shape SafeTensor file or reject it."""

    name = _string(value.get("name"))
    download_url = _string(value.get("downloadUrl"))
    size_kb = _number(value.get("sizeKB"))
    metadata = value.get("metadata")
    hashes = value.get("hashes")
    sha256 = _string(hashes.get("SHA256")) if isinstance(hashes, dict) else None
    file_format = (
        _string(metadata.get("format")) if isinstance(metadata, dict) else None
    )
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
        or _string(value.get("pickleScanResult")) != "Success"
        or _string(value.get("virusScanResult")) != "Success"
    ):
        return None
    return name, int(round(size_kb * 1024)), sha256.lower(), download_url


def _safe_thumbnail(value: object) -> str | None:
    """Return the first explicitly SFW HTTPS CivitAI-hosted image."""

    if not isinstance(value, list):
        return None
    for image in value:
        if not isinstance(image, dict) or image.get("nsfw") is not False:
            continue
        url = _string(image.get("url"))
        if url is not None and _is_civitai_host(url):
            return url
    return None


def _is_civitai_download_url(value: str) -> bool:
    """Return whether the file route is a trusted CivitAI HTTPS endpoint."""

    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"civitai.com", "www.civitai.com"}
        and parsed.path.startswith("/api/download/")
    )


def _is_civitai_host(value: str) -> bool:
    """Return whether an HTTPS asset is hosted by CivitAI or its subdomain."""

    parsed = urlparse(value)
    hostname = parsed.hostname or ""
    return parsed.scheme == "https" and (
        hostname == "civitai.com" or hostname.endswith(".civitai.com")
    )


def _is_sha256(value: str) -> bool:
    """Return whether a string is exactly one hexadecimal SHA256 digest."""

    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value.casefold()
    )


def _string(value: object) -> str | None:
    """Return one non-empty provider string."""

    return value.strip() if isinstance(value, str) and value.strip() else None


def _integer(value: object) -> int | None:
    """Return one positive provider integer."""

    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
        else None
    )


def _number(value: object) -> float | None:
    """Return one provider number while excluding booleans."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


__all__ = ["CivitaiDiscoveryClient", "CivitaiDiscoveryError"]
