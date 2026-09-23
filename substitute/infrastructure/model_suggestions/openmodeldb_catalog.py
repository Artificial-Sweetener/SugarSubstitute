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

"""Load and validate the governed OpenModelDB model catalog."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import time
from typing import Any
from urllib.parse import unquote, urlparse

from substitute.infrastructure.external.http_transport import (
    default_http_get,
    is_request_exception,
)

_LOGGER = logging.getLogger(__name__)
_CATALOG_URL = "https://openmodeldb.info/api/v1/models.json"
_MODEL_PAGE_ROOT = "https://openmodeldb.info/models"
_THUMBNAIL_ROOT = "https://openmodeldb.info"
_CACHE_FILE_NAME = "catalog-v1.json"
_MAXIMUM_CATALOG_BYTES = 10 * 1024 * 1024
_DEFAULT_FRESHNESS_SECONDS = 60 * 60
_SUPPORTED_RESOURCE_TYPES = frozenset({"pth", "safetensors"})

HttpGet = Callable[..., Any]


class OpenModelDbCatalogError(RuntimeError):
    """Report an unavailable or invalid OpenModelDB catalog."""


@dataclass(frozen=True, slots=True)
class OpenModelDbResource:
    """Describe one exact downloadable OpenModelDB artifact."""

    resource_type: str
    size_bytes: int
    sha256: str
    urls: tuple[str, ...]

    @property
    def file_name(self) -> str:
        """Return a portable file name derived from the preferred URL."""

        path_name = Path(unquote(urlparse(self.urls[0]).path)).name
        if path_name.casefold().endswith(f".{self.resource_type}"):
            return path_name
        return f"model.{self.resource_type}"


@dataclass(frozen=True, slots=True)
class OpenModelDbModel:
    """Describe one validated OpenModelDB entry and its exact resources."""

    model_id: str
    name: str
    author: str | None
    license_name: str | None
    architecture: str | None
    scale: int | None
    tags: tuple[str, ...]
    description: str | None
    resources: tuple[OpenModelDbResource, ...]
    thumbnail_url: str | None

    @property
    def model_page_url(self) -> str:
        """Return the public OpenModelDB model page."""

        return f"{_MODEL_PAGE_ROOT}/{self.model_id}"

    def preferred_resource(self) -> OpenModelDbResource | None:
        """Prefer SafeTensor artifacts before compatible PyTorch weights."""

        return next(
            (
                resource
                for resource_type in ("safetensors", "pth")
                for resource in self.resources
                if resource.resource_type == resource_type
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class OpenModelDbCatalog:
    """Expose validated OpenModelDB entries through stable lookup operations."""

    models: tuple[OpenModelDbModel, ...]

    def model(self, model_id: str) -> OpenModelDbModel | None:
        """Return one model by its stable OpenModelDB identifier."""

        return next(
            (model for model in self.models if model.model_id == model_id), None
        )

    def resource_for_sha256(
        self, sha256: str
    ) -> tuple[OpenModelDbModel, OpenModelDbResource] | None:
        """Return the exact model resource matching a SHA-256 identity."""

        normalized = sha256.casefold()
        return next(
            (
                (model, resource)
                for model in self.models
                for resource in model.resources
                if resource.sha256 == normalized
            ),
            None,
        )


class OpenModelDbCatalogClient:
    """Fetch, validate, and reuse OpenModelDB's remote catalog snapshot."""

    def __init__(
        self,
        cache_root: Path,
        *,
        http_get: HttpGet | None = None,
        timeout_seconds: float = 20.0,
        freshness_seconds: float = _DEFAULT_FRESHNESS_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Store bounded transport and the prepared persistent namespace."""

        if timeout_seconds <= 0 or freshness_seconds < 0:
            raise ValueError("OpenModelDB catalog timing limits are invalid.")
        self._cache_path = cache_root / _CACHE_FILE_NAME
        self._http_get = http_get or default_http_get
        self._timeout_seconds = timeout_seconds
        self._freshness_seconds = freshness_seconds
        self._clock = clock or time.time

    def load(self) -> OpenModelDbCatalog:
        """Return a fresh catalog, revalidating and falling back to stale data."""

        cached = self._read_cache()
        now = self._clock()
        if cached is not None and now - cached.fetched_at <= self._freshness_seconds:
            return cached.catalog
        headers = {
            "Accept": "application/json",
            "User-Agent": "SugarSubstitute/1.0",
        }
        if cached is not None:
            if cached.etag:
                headers["If-None-Match"] = cached.etag
            if cached.last_modified:
                headers["If-Modified-Since"] = cached.last_modified
        try:
            response = self._http_get(
                _CATALOG_URL,
                headers=headers,
                timeout=self._timeout_seconds,
            )
            status_code = getattr(response, "status_code", None)
            if status_code == 304 and cached is not None:
                self._write_cache(
                    _CachedCatalog(
                        catalog=cached.catalog,
                        raw_catalog=cached.raw_catalog,
                        fetched_at=now,
                        etag=cached.etag,
                        last_modified=cached.last_modified,
                    )
                )
                return cached.catalog
            response.raise_for_status()
            self._require_bounded_response(response)
            payload = response.json()
            catalog = parse_openmodeldb_catalog(payload)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            _LOGGER.warning("OpenModelDB catalog response was invalid", exc_info=error)
            if cached is not None:
                return cached.catalog
            raise OpenModelDbCatalogError(
                "OpenModelDB returned an invalid catalog."
            ) from error
        except Exception as error:
            if not is_request_exception(error):
                raise
            _LOGGER.warning("OpenModelDB catalog refresh failed", exc_info=error)
            if cached is not None:
                return cached.catalog
            raise OpenModelDbCatalogError("OpenModelDB is unavailable.") from error
        if not isinstance(payload, dict):
            raise OpenModelDbCatalogError("OpenModelDB catalog must be an object.")
        cached_catalog = _CachedCatalog(
            catalog=catalog,
            raw_catalog=payload,
            fetched_at=now,
            etag=_response_header(response, "ETag"),
            last_modified=_response_header(response, "Last-Modified"),
        )
        self._write_cache(cached_catalog)
        return catalog

    @staticmethod
    def _require_bounded_response(response: object) -> None:
        """Reject remote catalog bodies larger than the governed limit."""

        headers = getattr(response, "headers", {})
        raw_length = headers.get("Content-Length") if hasattr(headers, "get") else None
        if isinstance(raw_length, str) and raw_length.isdigit():
            if int(raw_length) > _MAXIMUM_CATALOG_BYTES:
                raise ValueError("OpenModelDB catalog exceeds the size limit.")
        content = getattr(response, "content", None)
        if isinstance(content, bytes) and len(content) > _MAXIMUM_CATALOG_BYTES:
            raise ValueError("OpenModelDB catalog exceeds the size limit.")

    def _read_cache(self) -> _CachedCatalog | None:
        """Return a validated cached catalog or report a recoverable cache miss."""

        try:
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("cache root is not an object")
            raw_catalog = payload["catalog"]
            fetched_at = payload["fetchedAt"]
            if not isinstance(raw_catalog, dict) or not isinstance(
                fetched_at, (int, float)
            ):
                raise ValueError("cache envelope is incomplete")
            return _CachedCatalog(
                catalog=parse_openmodeldb_catalog(raw_catalog),
                raw_catalog=raw_catalog,
                fetched_at=float(fetched_at),
                etag=_optional_string(payload.get("etag")),
                last_modified=_optional_string(payload.get("lastModified")),
            )
        except FileNotFoundError:
            return None
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            _LOGGER.warning(
                "OpenModelDB catalog cache is unreadable and will be replaced",
                extra={"cache_file": self._cache_path.name},
                exc_info=error,
            )
            return None

    def _write_cache(self, cached: _CachedCatalog) -> None:
        """Atomically replace the disposable remote catalog cache."""

        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._cache_path.with_suffix(".tmp")
        envelope = {
            "catalog": cached.raw_catalog,
            "etag": cached.etag,
            "fetchedAt": cached.fetched_at,
            "lastModified": cached.last_modified,
        }
        temporary.write_text(
            json.dumps(envelope, ensure_ascii=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(self._cache_path)


@dataclass(frozen=True, slots=True)
class _CachedCatalog:
    """Carry validated cache content and remote revalidation evidence."""

    catalog: OpenModelDbCatalog
    raw_catalog: Mapping[str, object]
    fetched_at: float
    etag: str | None
    last_modified: str | None


def parse_openmodeldb_catalog(payload: object) -> OpenModelDbCatalog:
    """Parse the public catalog while dropping malformed individual entries."""

    if not isinstance(payload, dict):
        raise ValueError("OpenModelDB catalog must be an object.")
    models = tuple(
        model
        for model_id, value in payload.items()
        if isinstance(model_id, str)
        for model in (_parse_model(model_id, value),)
        if model is not None
    )
    if not models:
        raise ValueError("OpenModelDB catalog contains no usable models.")
    return OpenModelDbCatalog(models)


def _parse_model(model_id: str, payload: object) -> OpenModelDbModel | None:
    """Return one valid catalog model or omit an unusable entry."""

    if not isinstance(payload, dict):
        return None
    name = _optional_string(payload.get("name"))
    resources = _parse_resources(payload.get("resources"))
    if name is None or not resources:
        return None
    return OpenModelDbModel(
        model_id=model_id,
        name=name,
        author=_optional_string(payload.get("author")),
        license_name=_optional_string(payload.get("license")),
        architecture=_optional_string(payload.get("architecture")),
        scale=_optional_positive_int(payload.get("scale")),
        tags=_string_tuple(payload.get("tags")),
        description=_optional_string(payload.get("description")),
        resources=resources,
        thumbnail_url=_thumbnail_url(payload.get("thumbnail")),
    )


def _parse_resources(payload: object) -> tuple[OpenModelDbResource, ...]:
    """Return exact supported resources from one model entry."""

    if not isinstance(payload, list):
        return ()
    resources: list[OpenModelDbResource] = []
    for value in payload:
        if not isinstance(value, dict):
            continue
        resource_type = _optional_string(value.get("type"))
        size_bytes = _optional_positive_int(value.get("size"))
        sha256 = _optional_string(value.get("sha256"))
        urls = tuple(
            url for url in _string_tuple(value.get("urls")) if _is_safe_https_url(url)
        )
        if (
            resource_type is None
            or resource_type.casefold() not in _SUPPORTED_RESOURCE_TYPES
            or size_bytes is None
            or sha256 is None
            or not _is_sha256(sha256)
            or not urls
        ):
            continue
        resources.append(
            OpenModelDbResource(
                resource_type=resource_type.casefold(),
                size_bytes=size_bytes,
                sha256=sha256.casefold(),
                urls=urls,
            )
        )
    return tuple(resources)


def _thumbnail_url(payload: object) -> str | None:
    """Return OpenModelDB's preferred output thumbnail URL."""

    if not isinstance(payload, dict):
        return None
    value = _optional_string(payload.get("SR")) or _optional_string(payload.get("url"))
    if value is None:
        return None
    absolute = f"{_THUMBNAIL_ROOT}{value}" if value.startswith("/") else value
    return absolute if _is_safe_https_url(absolute) else None


def _response_header(response: object, name: str) -> str | None:
    """Read one optional response header without coupling to requests."""

    headers = getattr(response, "headers", {})
    return _optional_string(headers.get(name)) if hasattr(headers, "get") else None


def _optional_string(value: object) -> str | None:
    """Return a stripped non-empty string."""

    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_positive_int(value: object) -> int | None:
    """Return a positive integer without accepting booleans."""

    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    """Return non-empty string values from one JSON array."""

    if not isinstance(value, list):
        return ()
    return tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )


def _is_safe_https_url(value: str) -> bool:
    """Return whether a URL uses HTTPS without embedded credentials."""

    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
    )


def _is_sha256(value: str) -> bool:
    """Return whether a value is exactly one hexadecimal SHA-256 digest."""

    normalized = value.casefold()
    return len(normalized) == 64 and all(
        character in "0123456789abcdef" for character in normalized
    )
