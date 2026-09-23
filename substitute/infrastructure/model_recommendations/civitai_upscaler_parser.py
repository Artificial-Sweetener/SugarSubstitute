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

"""Validate explicit CivitAI upscaler links and their exact downloadable files."""

from __future__ import annotations

import math
import re
from urllib.parse import urlparse

from substitute.domain.model_recommendations import ModelFamilyId, ModelRecommendation


def parse_civitai_upscaler(
    payload: object, *, target_version_id: int | None
) -> ModelRecommendation | None:
    """Select a public, scan-clean upscaler file with a published SHA-256."""

    if not isinstance(payload, dict) or payload.get("type") != "Upscaler":
        return None
    if payload.get("nsfw") is not False or payload.get("mode") is not None:
        return None
    model_id = _positive_integer(payload.get("id"))
    model_name = _text(payload.get("name"))
    versions = payload.get("modelVersions")
    if model_id is None or model_name is None or not isinstance(versions, list):
        return None
    creator = payload.get("creator")
    creator_name = _text(creator.get("username")) if isinstance(creator, dict) else None
    for version in versions:
        if not isinstance(version, dict):
            continue
        version_id = _positive_integer(version.get("id"))
        if version_id is None or (
            target_version_id is not None and target_version_id != version_id
        ):
            continue
        availability = _text(version.get("availability"))
        if availability is not None and availability.casefold() != "public":
            continue
        files = version.get("files")
        if not isinstance(files, list):
            continue
        for file in sorted(
            (item for item in files if isinstance(item, dict)),
            key=lambda item: item.get("primary") is not True,
        ):
            safe_file = _safe_file(file)
            if safe_file is None:
                continue
            file_name, size_bytes, sha256, download_url = safe_file
            return ModelRecommendation(
                family_id=ModelFamilyId.UPSCALERS,
                model_id=model_id,
                version_id=version_id,
                model_name=model_name,
                version_name=_text(version.get("name")) or "Upscaler",
                creator=creator_name,
                file_name=file_name,
                size_bytes=size_bytes,
                sha256=sha256,
                download_url=download_url,
                model_page_url=(
                    f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
                ),
                thumbnail_image_id=version_id,
                thumbnail_url=None,
                popularity_rank=0,
            )
    return None


def _safe_file(value: dict[str, object]) -> tuple[str, int, str, str] | None:
    """Accept only model weights with clean provider scans and exact identity."""

    name = _text(value.get("name"))
    url = _text(value.get("downloadUrl"))
    hashes = value.get("hashes")
    sha256 = _text(hashes.get("SHA256")) if isinstance(hashes, dict) else None
    size_kb = value.get("sizeKB")
    if name is None or name != name.split("/")[-1] or "\\" in name:
        return None
    suffix = name.rpartition(".")[2].casefold()
    if suffix not in {"pt", "pth", "safetensors"}:
        return None
    if (
        url is None
        or not _trusted_download_url(url)
        or sha256 is None
        or len(sha256) != 64
        or any(character not in "0123456789abcdef" for character in sha256.casefold())
        or not isinstance(size_kb, (int, float))
        or isinstance(size_kb, bool)
        or size_kb <= 0
        or not math.isfinite(size_kb)
        or _text(value.get("pickleScanResult")) != "Success"
        or _text(value.get("virusScanResult")) != "Success"
    ):
        return None
    metadata = value.get("metadata")
    file_format = _text(metadata.get("format")) if isinstance(metadata, dict) else None
    expected_format = "SafeTensor" if suffix == "safetensors" else "PickleTensor"
    if file_format != expected_format:
        return None
    return name, int(round(size_kb * 1024)), sha256.casefold(), url


def _trusted_download_url(value: str) -> bool:
    """Require the fixed CivitAI model-download endpoint."""

    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"civitai.com", "www.civitai.com"}
        and re.fullmatch(r"/api/download/models/\d+", parsed.path) is not None
        and parsed.username is None
        and parsed.password is None
        and parsed.port in {None, 443}
    )


def _positive_integer(value: object) -> int | None:
    """Return a positive provider integer excluding boolean values."""

    return value if type(value) is int and value > 0 else None


def _text(value: object) -> str | None:
    """Return one nonempty normalized provider string."""

    return value.strip() if isinstance(value, str) and value.strip() else None


__all__ = ["parse_civitai_upscaler"]
