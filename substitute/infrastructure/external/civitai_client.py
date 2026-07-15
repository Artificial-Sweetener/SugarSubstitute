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

"""HTTP client and parser for CivitAI model metadata."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from substitute.domain.common import JsonObject
from substitute.domain.model_metadata import (
    CivitaiFile,
    CivitaiImage,
    CivitaiLookupResult,
    CivitaiModelVersion,
    CivitaiLookupStatus,
)
from substitute.infrastructure.external.http_transport import (
    default_http_get,
    is_request_exception,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.external.civitai_client")
_BASE_URL = "https://civitai.com/api/v1"
HttpGet = Callable[..., Any]


class CivitaiClient:
    """Look up CivitAI model-version metadata by model file hash."""

    def __init__(
        self,
        *,
        http_get: HttpGet | None = None,
        timeout_seconds: float = 15.0,
        api_key: str | None = None,
        api_key_provider: Callable[[], str | None] | None = None,
        user_agent: str = "SugarSubstitute/1.0",
        clock: Callable[[], str] | None = None,
    ) -> None:
        """Initialize the client with injectable HTTP transport and clock."""

        self._http_get = http_get or default_http_get
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._api_key_provider = api_key_provider
        self._user_agent = user_agent
        self._clock = clock or _utc_now

    def lookup_model_version_by_hash(self, sha256: str) -> CivitaiLookupResult:
        """Return CivitAI metadata for a SHA256 value."""

        normalized_sha256 = sha256.upper()
        url = f"{_BASE_URL}/model-versions/by-hash/{normalized_sha256}"
        try:
            response = self._http_get(
                url,
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
            if getattr(response, "status_code", None) == 404:
                return CivitaiLookupResult(status=CivitaiLookupStatus.NOT_FOUND)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not is_request_exception(error):
                raise
            log_warning(
                _LOGGER,
                "CivitAI lookup failed",
                sha256=normalized_sha256,
                error=repr(error),
            )
            return CivitaiLookupResult(
                status=CivitaiLookupStatus.UNAVAILABLE,
                error=str(error),
            )
        except (TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "CivitAI lookup returned invalid JSON",
                sha256=normalized_sha256,
                error=repr(error),
            )
            return CivitaiLookupResult(
                status=CivitaiLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        if not isinstance(payload, dict):
            return CivitaiLookupResult(
                status=CivitaiLookupStatus.INVALID_RESPONSE,
                error="CivitAI payload must be a JSON object.",
            )
        try:
            version = _parse_model_version(
                payload, source_url=url, fetched_at=self._clock()
            )
        except ValueError as error:
            log_warning(
                _LOGGER,
                "CivitAI lookup returned unexpected model-version shape",
                sha256=normalized_sha256,
                error=repr(error),
            )
            return CivitaiLookupResult(
                status=CivitaiLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        return CivitaiLookupResult(
            status=CivitaiLookupStatus.FOUND,
            version=version,
        )

    def _headers(self) -> dict[str, str]:
        """Return CivitAI request headers without logging secrets."""

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self._user_agent,
        }
        api_key = self._api_key_provider() if self._api_key_provider else self._api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers


def _parse_model_version(
    data: JsonObject,
    *,
    source_url: str,
    fetched_at: str,
) -> CivitaiModelVersion:
    """Parse a CivitAI by-hash model-version response."""

    model = data.get("model")
    model_object = model if isinstance(model, dict) else {}
    model_id = _read_int(data, "modelId")
    if model_id is None:
        model_id = _read_int(model_object, "id")
    version_id = _read_int(data, "id")
    if model_id is None or version_id is None:
        raise ValueError("CivitAI response missing modelId or id")
    return CivitaiModelVersion(
        model_id=model_id,
        model_version_id=version_id,
        model_name=_read_str(model_object, "name")
        or _read_str(data, "modelName")
        or "",
        model_type=_read_str(model_object, "type") or _read_str(data, "modelType"),
        version_name=_read_str(data, "name") or "",
        base_model=_read_str(data, "baseModel"),
        trained_words=_read_str_tuple(data, "trainedWords"),
        description=_read_str(model_object, "description"),
        version_description=_read_str(data, "description"),
        tags=_read_str_tuple(model_object, "tags"),
        creator_username=_read_creator_username(model_object),
        creator_image=_read_creator_image(model_object),
        nsfw=_read_bool_or_none(model_object, "nsfw"),
        nsfw_level=_read_str_or_int(model_object, "nsfwLevel"),
        availability=_read_str(data, "availability") or _read_str(model_object, "mode"),
        files=_parse_files(data.get("files")),
        images=_parse_images(data.get("images")),
        stats=_read_object_or_empty(data, "stats"),
        model_page_url=_model_page_url(model_id, version_id),
        source_url=source_url,
        fetched_at=fetched_at,
        raw_provider_payload=data,
    )


def _model_page_url(model_id: int, model_version_id: int) -> str:
    """Return the public CivitAI page URL for one model version."""

    return f"https://civitai.com/models/{model_id}?modelVersionId={model_version_id}"


def _parse_files(raw_files: object) -> tuple[CivitaiFile, ...]:
    """Parse CivitAI file metadata entries."""

    if not isinstance(raw_files, list):
        return ()
    files: list[CivitaiFile] = []
    for raw_file in raw_files:
        if not isinstance(raw_file, dict):
            continue
        name = _read_str(raw_file, "name")
        if name is None:
            continue
        files.append(
            CivitaiFile(
                file_id=_read_int(raw_file, "id"),
                name=name,
                size_kb=_read_float(raw_file, "sizeKB"),
                file_type=_read_str(raw_file, "type"),
                download_url=_read_str(raw_file, "downloadUrl"),
                pickle_scan_result=_read_str(raw_file, "pickleScanResult"),
                virus_scan_result=_read_str(raw_file, "virusScanResult"),
                primary=_read_bool(raw_file, "primary"),
                hashes=_read_object_or_empty(raw_file, "hashes"),
                metadata=_read_object_or_empty(raw_file, "metadata"),
            )
        )
    return tuple(files)


def _parse_images(raw_images: object) -> tuple[CivitaiImage, ...]:
    """Parse CivitAI image metadata entries."""

    if not isinstance(raw_images, list):
        return ()
    images: list[CivitaiImage] = []
    for raw_image in raw_images:
        if not isinstance(raw_image, dict):
            continue
        url = _read_str(raw_image, "url")
        if url is None:
            continue
        images.append(
            CivitaiImage(
                image_id=_read_int(raw_image, "id"),
                url=url,
                image_type=_read_str(raw_image, "type"),
                nsfw=_read_bool_or_none(raw_image, "nsfw"),
                nsfw_level=_read_str_or_int(raw_image, "nsfwLevel"),
                width=_read_int(raw_image, "width"),
                height=_read_int(raw_image, "height"),
                meta=_read_optional_object(raw_image, "meta"),
            )
        )
    return tuple(images)


def _read_creator_username(model: JsonObject) -> str | None:
    """Read CivitAI creator username from a model object."""

    creator = model.get("creator")
    if not isinstance(creator, dict):
        return None
    return _read_str(creator, "username")


def _read_creator_image(model: JsonObject) -> str | None:
    """Read CivitAI creator avatar URL from a model object."""

    creator = model.get("creator")
    if not isinstance(creator, dict):
        return None
    return _read_str(creator, "image")


def _read_str(data: JsonObject, key: str) -> str | None:
    """Read an optional string field."""

    value = data.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _read_int(data: JsonObject, key: str) -> int | None:
    """Read an optional integer field."""

    value = data.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _read_float(data: JsonObject, key: str) -> float | None:
    """Read an optional numeric field as float."""

    value = data.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _read_bool(data: JsonObject, key: str) -> bool:
    """Read an optional boolean field with a false default."""

    value = data.get(key)
    return value if isinstance(value, bool) else False


def _read_bool_or_none(data: JsonObject, key: str) -> bool | None:
    """Read an optional boolean field."""

    value = data.get(key)
    return value if isinstance(value, bool) else None


def _read_str_or_int(data: JsonObject, key: str) -> str | int | None:
    """Read an optional string or integer field."""

    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _read_str_tuple(data: JsonObject, key: str) -> tuple[str, ...]:
    """Read an optional string list field."""

    value = data.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item.strip())


def _read_optional_object(data: JsonObject, key: str) -> JsonObject | None:
    """Read an optional object field."""

    value = data.get(key)
    return value if isinstance(value, dict) else None


def _read_object_or_empty(data: JsonObject, key: str) -> JsonObject:
    """Read an optional object field with an empty object fallback."""

    value = data.get(key)
    return value if isinstance(value, dict) else {}


def _utc_now() -> str:
    """Return the current UTC timestamp for cache records."""

    from datetime import UTC, datetime

    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


__all__ = ["CivitaiClient"]
