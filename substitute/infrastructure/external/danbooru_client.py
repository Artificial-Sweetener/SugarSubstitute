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

"""HTTP client for Danbooru read-only prompt and wiki lookups."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from substitute.domain.common import JsonObject
from substitute.domain.danbooru import (
    DanbooruMediaAssetLookupResult,
    DanbooruMediaAssetRecord,
    DanbooruMediaAssetVariantRecord,
    DanbooruLookupStatus,
    DanbooruPostLookupResult,
    DanbooruPostRecord,
    DanbooruTagLookupResult,
    DanbooruTagRecord,
    DanbooruWikiPageLookupResult,
    DanbooruWikiPageRecord,
)
from substitute.infrastructure.external.http_transport import (
    default_http_get,
    is_request_exception,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.external.danbooru_client")
_BASE_URL = "https://danbooru.donmai.us"
HttpGet = Callable[..., Any]


class DanbooruClient:
    """Query Danbooru's public read API for prompt-editor features."""

    def __init__(
        self,
        *,
        http_get: HttpGet | None = None,
        timeout_seconds: float = 15.0,
        user_agent: str = "SugarSubstitute/1.0",
    ) -> None:
        """Store the HTTP transport and request policy used for lookups."""

        self._http_get = http_get or default_http_get
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent

    def get_post_by_id(self, post_id: int) -> DanbooruPostLookupResult:
        """Return one Danbooru post by its numeric identifier."""

        return self._get_post(f"/posts/{post_id}.json")

    def get_post_by_md5(self, md5: str) -> DanbooruPostLookupResult:
        """Return one Danbooru post by the exact media MD5 hash."""

        payload = self._get_json_object(f"/posts.json?md5={quote(md5)}")
        if payload.status is not DanbooruLookupStatus.FOUND:
            return DanbooruPostLookupResult(status=payload.status, error=payload.error)
        try:
            record = _parse_post_record(payload.object_payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Danbooru post-by-md5 response was invalid.",
                md5=md5,
                error=repr(error),
            )
            return DanbooruPostLookupResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        return DanbooruPostLookupResult(
            status=DanbooruLookupStatus.FOUND,
            post=record,
        )

    def get_wiki_page(self, title: str) -> DanbooruWikiPageLookupResult:
        """Return one Danbooru wiki page by title."""

        payload = self._get_json_object(f"/wiki_pages/{quote(title)}.json")
        if payload.status is not DanbooruLookupStatus.FOUND:
            return DanbooruWikiPageLookupResult(
                status=payload.status,
                error=payload.error,
            )
        try:
            record = _parse_wiki_page_record(payload.object_payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Danbooru wiki page response was invalid.",
                title=title,
                error=repr(error),
            )
            return DanbooruWikiPageLookupResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        return DanbooruWikiPageLookupResult(
            status=DanbooruLookupStatus.FOUND,
            wiki_page=record,
        )

    def get_media_asset_by_id(self, asset_id: int) -> DanbooruMediaAssetLookupResult:
        """Return one Danbooru media asset by numeric identifier."""

        payload = self._get_json_object(f"/media_assets/{asset_id}.json")
        if payload.status is not DanbooruLookupStatus.FOUND:
            return DanbooruMediaAssetLookupResult(
                status=payload.status,
                error=payload.error,
            )
        try:
            record = _parse_media_asset_record(payload.object_payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Danbooru media asset response was invalid.",
                asset_id=asset_id,
                error=repr(error),
            )
            return DanbooruMediaAssetLookupResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        return DanbooruMediaAssetLookupResult(
            status=DanbooruLookupStatus.FOUND,
            media_asset=record,
        )

    def list_posts_by_tag(
        self,
        tag_name: str,
        *,
        limit: int,
        before_post_id: int | None = None,
    ) -> tuple[DanbooruPostRecord, ...]:
        """Return one newest-first batch of posts for the supplied tag name."""

        page_segment = "" if before_post_id is None else f"&page=b{before_post_id}"
        payload = self._get_json_list(
            "/posts.json"
            f"?tags={quote(tag_name)}"
            f"&limit={limit}"
            "&only=id,created_at,updated_at,source,md5,rating,tag_string,"
            "tag_string_general,tag_string_artist,tag_string_copyright,"
            "tag_string_character,tag_string_meta,file_url,large_file_url,"
            f"preview_file_url{page_segment}"
        )
        if payload.status is not DanbooruLookupStatus.FOUND:
            return ()
        records: list[DanbooruPostRecord] = []
        for raw_post in payload.list_payload:
            if not isinstance(raw_post, dict):
                continue
            try:
                records.append(_parse_post_record(raw_post))
            except ValueError as error:
                log_warning(
                    _LOGGER,
                    "Danbooru tag-post response was invalid.",
                    tag_name=tag_name,
                    before_post_id=before_post_id,
                    error=repr(error),
                )
                continue
        return tuple(records)

    def get_tag_by_name(self, name: str) -> DanbooruTagLookupResult:
        """Return one Danbooru tag using exact name matching."""

        payload = self._get_json_list(f"/tags.json?search[name]={quote(name)}&limit=1")
        if payload.status is not DanbooruLookupStatus.FOUND:
            return DanbooruTagLookupResult(status=payload.status, error=payload.error)
        if not payload.list_payload:
            return DanbooruTagLookupResult(status=DanbooruLookupStatus.NOT_FOUND)
        raw_tag = payload.list_payload[0]
        if not isinstance(raw_tag, dict):
            return DanbooruTagLookupResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error="Danbooru tag payload must contain JSON objects.",
            )
        try:
            record = _parse_tag_record(raw_tag)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Danbooru tag response was invalid.",
                name=name,
                error=repr(error),
            )
            return DanbooruTagLookupResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        return DanbooruTagLookupResult(
            status=DanbooruLookupStatus.FOUND,
            tag=record,
        )

    def download_binary(self, url: str) -> bytes | None:
        """Return remote bytes for one Danbooru preview URL when available."""

        try:
            response = self._http_get(
                url,
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            content = getattr(response, "content", None)
        except Exception as error:
            if not is_request_exception(error):
                raise
            log_warning(
                _LOGGER,
                "Danbooru binary GET failed.",
                url=url,
                error=repr(error),
            )
            return None
        return bytes(content) if isinstance(content, bytes) else None

    def _get_post(self, path: str) -> DanbooruPostLookupResult:
        """Return one post record from a route that yields one JSON object."""

        payload = self._get_json_object(path)
        if payload.status is not DanbooruLookupStatus.FOUND:
            return DanbooruPostLookupResult(status=payload.status, error=payload.error)
        try:
            record = _parse_post_record(payload.object_payload)
        except ValueError as error:
            log_warning(
                _LOGGER,
                "Danbooru post response was invalid.",
                path=path,
                error=repr(error),
            )
            return DanbooruPostLookupResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        return DanbooruPostLookupResult(
            status=DanbooruLookupStatus.FOUND,
            post=record,
        )

    def _get_json_object(self, path: str) -> "_JsonObjectResult":
        """GET one Danbooru route and require a JSON object response."""

        try:
            response = self._http_get(
                self._url(path),
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
            if getattr(response, "status_code", None) == 404:
                return _JsonObjectResult(status=DanbooruLookupStatus.NOT_FOUND)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not is_request_exception(error):
                raise
            log_warning(
                _LOGGER,
                "Danbooru GET failed.",
                endpoint=self._url(path),
                error=repr(error),
            )
            return _JsonObjectResult(
                status=DanbooruLookupStatus.UNAVAILABLE,
                error=str(error),
            )
        except (TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Danbooru returned invalid JSON.",
                endpoint=self._url(path),
                error=repr(error),
            )
            return _JsonObjectResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        if not isinstance(payload, dict):
            return _JsonObjectResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error="Danbooru payload must be a JSON object.",
            )
        return _JsonObjectResult(
            status=DanbooruLookupStatus.FOUND,
            object_payload=payload,
        )

    def _get_json_list(self, path: str) -> "_JsonListResult":
        """GET one Danbooru route and require a JSON array response."""

        try:
            response = self._http_get(
                self._url(path),
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
            if getattr(response, "status_code", None) == 404:
                return _JsonListResult(status=DanbooruLookupStatus.NOT_FOUND)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            if not is_request_exception(error):
                raise
            log_warning(
                _LOGGER,
                "Danbooru GET failed.",
                endpoint=self._url(path),
                error=repr(error),
            )
            return _JsonListResult(
                status=DanbooruLookupStatus.UNAVAILABLE,
                error=str(error),
            )
        except (TypeError, ValueError) as error:
            log_warning(
                _LOGGER,
                "Danbooru returned invalid JSON.",
                endpoint=self._url(path),
                error=repr(error),
            )
            return _JsonListResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error=str(error),
            )
        if not isinstance(payload, list):
            return _JsonListResult(
                status=DanbooruLookupStatus.INVALID_RESPONSE,
                error="Danbooru payload must be a JSON list.",
            )
        return _JsonListResult(
            status=DanbooruLookupStatus.FOUND,
            list_payload=tuple(payload),
        )

    def _headers(self) -> dict[str, str]:
        """Return Danbooru request headers without any authentication data."""

        return {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }

    def _url(self, path: str) -> str:
        """Return one absolute Danbooru API URL."""

        return f"{_BASE_URL}{path}"


class _JsonObjectResult:
    """Capture one JSON-object fetch outcome."""

    def __init__(
        self,
        *,
        status: DanbooruLookupStatus,
        object_payload: JsonObject | None = None,
        error: str = "",
    ) -> None:
        """Store the typed object payload and failure metadata."""

        self.status = status
        self.object_payload = object_payload or {}
        self.error = error


class _JsonListResult:
    """Capture one JSON-list fetch outcome."""

    def __init__(
        self,
        *,
        status: DanbooruLookupStatus,
        list_payload: tuple[object, ...] = (),
        error: str = "",
    ) -> None:
        """Store the typed list payload and failure metadata."""

        self.status = status
        self.list_payload = list_payload
        self.error = error


def _parse_post_record(data: JsonObject) -> DanbooruPostRecord:
    """Parse one Danbooru post object into a typed record."""

    return DanbooruPostRecord(
        post_id=_required_int(data, "id"),
        created_at=_read_str(data, "created_at"),
        updated_at=_read_str(data, "updated_at"),
        source=_read_str(data, "source") or "",
        md5=_read_str(data, "md5"),
        rating=_read_str(data, "rating"),
        tag_string=_required_str(data, "tag_string"),
        tag_string_general=_read_str(data, "tag_string_general") or "",
        tag_string_artist=_read_str(data, "tag_string_artist") or "",
        tag_string_copyright=_read_str(data, "tag_string_copyright") or "",
        tag_string_character=_read_str(data, "tag_string_character") or "",
        tag_string_meta=_read_str(data, "tag_string_meta") or "",
        file_url=_read_str(data, "file_url"),
        large_file_url=_read_str(data, "large_file_url"),
        preview_file_url=_read_str(data, "preview_file_url"),
    )


def _parse_wiki_page_record(data: JsonObject) -> DanbooruWikiPageRecord:
    """Parse one Danbooru wiki page into a typed record."""

    return DanbooruWikiPageRecord(
        wiki_page_id=_required_int(data, "id"),
        created_at=_read_str(data, "created_at"),
        updated_at=_read_str(data, "updated_at"),
        title=_required_str(data, "title"),
        body=_required_str(data, "body"),
        other_names=_read_str_tuple(data, "other_names"),
        category_name=_read_str(data, "category_name"),
    )


def _parse_tag_record(data: JsonObject) -> DanbooruTagRecord:
    """Parse one Danbooru tag payload into a typed record."""

    return DanbooruTagRecord(
        tag_id=_required_int(data, "id"),
        created_at=_read_str(data, "created_at"),
        updated_at=_read_str(data, "updated_at"),
        name=_required_str(data, "name"),
        category=_required_int(data, "category"),
        post_count=_required_int(data, "post_count"),
        is_deprecated=_read_bool(data, "is_deprecated"),
    )


def _parse_media_asset_record(data: JsonObject) -> DanbooruMediaAssetRecord:
    """Parse one Danbooru media asset payload into a typed record."""

    variants = data.get("variants")
    if not isinstance(variants, list):
        raise ValueError("Danbooru media asset payload must contain a variant list.")
    parsed_variants: list[DanbooruMediaAssetVariantRecord] = []
    for raw_variant in variants:
        if not isinstance(raw_variant, dict):
            continue
        variant_type = _read_str(raw_variant, "type")
        variant_url = _read_str(raw_variant, "url")
        if variant_type and variant_url:
            parsed_variants.append(
                DanbooruMediaAssetVariantRecord(
                    variant_type=variant_type,
                    url=variant_url,
                    width=_read_int(raw_variant, "width"),
                    height=_read_int(raw_variant, "height"),
                    file_ext=_read_str(raw_variant, "file_ext"),
                )
            )
    return DanbooruMediaAssetRecord(
        asset_id=_required_int(data, "id"),
        created_at=_read_str(data, "created_at"),
        updated_at=_read_str(data, "updated_at"),
        md5=_read_str(data, "md5"),
        file_ext=_read_str(data, "file_ext"),
        image_width=_read_int(data, "image_width"),
        image_height=_read_int(data, "image_height"),
        variants=tuple(parsed_variants),
    )


def _read_str(data: JsonObject, key: str) -> str | None:
    """Return one optional string field from a JSON object."""

    value = data.get(key)
    return value if isinstance(value, str) else None


def _required_str(data: JsonObject, key: str) -> str:
    """Return one required string field or raise ``ValueError``."""

    value = _read_str(data, key)
    if value is None:
        raise ValueError(f"Danbooru payload missing required string field {key}.")
    return value


def _read_int(data: JsonObject, key: str) -> int | None:
    """Return one optional integer field from a JSON object."""

    value = data.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _required_int(data: JsonObject, key: str) -> int:
    """Return one required integer field or raise ``ValueError``."""

    value = _read_int(data, key)
    if value is None:
        raise ValueError(f"Danbooru payload missing required integer field {key}.")
    return value


def _read_bool(data: JsonObject, key: str) -> bool:
    """Return one boolean field, defaulting to ``False`` when absent."""

    value = data.get(key)
    return bool(value) if isinstance(value, bool) else False


def _read_str_tuple(data: JsonObject, key: str) -> tuple[str, ...]:
    """Return one optional tuple of strings from a JSON object."""

    value = data.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


__all__ = ["DanbooruClient"]
