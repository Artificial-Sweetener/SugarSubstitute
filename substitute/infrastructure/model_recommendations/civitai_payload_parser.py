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

"""Validate CivitAI model payloads for onboarding recommendations."""

from __future__ import annotations

from collections.abc import Callable, Collection
import re
from typing import Any
from urllib.parse import urlparse

from substitute.domain.model_metadata import CivitaiImage, CivitaiThumbnailPolicy
from substitute.domain.model_recommendations import (
    ModelFamilyDefinition,
    ModelRecommendation,
)

_MIN_PORTRAIT_WIDTH = 640
_MIN_PORTRAIT_HEIGHT = 800
_PORTRAIT_PREVIEW_WIDTH = 512


def parse_model(
    value: object,
    *,
    family: ModelFamilyDefinition,
    popularity_rank: int,
    fallback_thumbnail: Callable[[int], tuple[int, str] | None],
    thumbnail_policy: CivitaiThumbnailPolicy,
    accepted_base_models: Collection[str],
    target_version_id: int | None = None,
) -> ModelRecommendation | None:
    """Parse one public model and choose its first family-compatible version."""

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
        if target_version_id is not None and (
            not isinstance(version, dict) or version.get("id") != target_version_id
        ):
            continue
        parsed = _parse_version(
            version,
            accepted_base_models=accepted_base_models,
            fallback_thumbnail=fallback_thumbnail,
            thumbnail_policy=thumbnail_policy,
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
            thumbnail_image_id,
            thumbnail_url,
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
            model_page_url=(
                f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
            ),
            thumbnail_image_id=thumbnail_image_id,
            thumbnail_url=thumbnail_url,
            popularity_rank=popularity_rank,
        )
    return None


def model_page_identity(value: str) -> tuple[int, int | None]:
    """Return the model and optional exact-version identity from a trusted page URL."""

    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.hostname not in {
        "civitai.com",
        "www.civitai.com",
        "civitai.red",
        "www.civitai.red",
    }:
        raise ValueError("Only HTTPS CivitAI model links are supported.")
    match = re.fullmatch(r"/models/(\d+)(?:/[^/?#]+)?/?", parsed.path)
    if match is None:
        raise ValueError("CivitAI link does not identify a model page.")
    model_id = _positive_integer(int(match.group(1)))
    query = dict(item.split("=", 1) for item in parsed.query.split("&") if "=" in item)
    raw_version_id = query.get("modelVersionId")
    version_id = (
        _positive_integer(int(raw_version_id))
        if raw_version_id is not None and raw_version_id.isdigit()
        else None
    )
    if model_id is None or (raw_version_id is not None and version_id is None):
        raise ValueError("CivitAI link contains an invalid model identity.")
    return model_id, version_id


def safe_thumbnail(
    value: object,
    *,
    thumbnail_policy: CivitaiThumbnailPolicy,
) -> tuple[int, str] | None:
    """Return the exact identity and URL of the first allowed provider portrait."""

    if not isinstance(value, list):
        return None
    for image in value:
        if not isinstance(image, dict):
            continue
        url = _text(image.get("url"))
        image_id = _positive_integer(image.get("id"))
        normalized = CivitaiImage(
            image_id=image_id,
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
            image_id is not None
            and url is not None
            and _is_civitai_asset_url(url)
            and thumbnail_policy.allows_image(normalized)
            and normalized.width is not None
            and normalized.height is not None
            and normalized.width >= _MIN_PORTRAIT_WIDTH
            and normalized.height >= _MIN_PORTRAIT_HEIGHT
            and normalized.height > normalized.width
        ):
            return image_id, _large_preview_url(url)
    return None


def _parse_version(
    value: object,
    *,
    accepted_base_models: Collection[str],
    fallback_thumbnail: Callable[[int], tuple[int, str] | None],
    thumbnail_policy: CivitaiThumbnailPolicy,
) -> tuple[int, str, str, int, str, str, int, str] | None:
    """Return one compatible version with an allowed image and verified file."""

    if not isinstance(value, dict):
        return None
    version_id = _positive_integer(value.get("id"))
    version_name = _text(value.get("name"))
    base_model = _text(value.get("baseModel"))
    availability = _text(value.get("availability"))
    if (
        version_id is None
        or version_name is None
        or base_model not in accepted_base_models
        or (availability is not None and availability.casefold() != "public")
    ):
        return None
    thumbnail = safe_thumbnail(value.get("images"), thumbnail_policy=thumbnail_policy)
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
            return (version_id, version_name, *parsed, *thumbnail)
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


def _large_preview_url(url: str) -> str:
    """Request a bounded 512-pixel CivitAI CDN derivative when supported."""

    return re.sub(
        r"/(?:width=\d+|original=true)/",
        f"/width={_PORTRAIT_PREVIEW_WIDTH}/",
        url,
        count=1,
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


__all__ = ["model_page_identity", "parse_model", "safe_thumbnail"]
