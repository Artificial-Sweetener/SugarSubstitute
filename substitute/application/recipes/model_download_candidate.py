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

"""Select safe exact-hash CivitAI download candidates for model recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.application.model_metadata import CivitaiMetadataGateway
from substitute.domain.model_metadata import (
    CivitaiDownloadAccess,
    CivitaiFile,
    CivitaiModelVersion,
    CivitaiThumbnailPolicy,
)


@dataclass(frozen=True, slots=True)
class RecipeModelDownloadCandidate:
    """Represent one exact-hash CivitAI model file safe enough to offer."""

    kind: str
    sha256: str
    name: str
    download_url: str
    size_kb: float | None
    model_id: int
    model_version_id: int
    model_name: str
    version_name: str
    base_model: str | None
    creator: str | None
    file_id: int | None
    file_type: str | None
    metadata_format: str | None
    pickle_scan_result: str | None
    virus_scan_result: str | None
    model_page_url: str
    thumbnail_url: str | None = None
    download_access: CivitaiDownloadAccess = CivitaiDownloadAccess.UNKNOWN
    provider_id: str = "civitai"
    provider_name: str = "CivitAI"
    size_bytes: int | None = None


class RecipeModelRecoveryGateway(Protocol):
    """Resolve a verified recovery candidate from an exact model hash."""

    def candidate(
        self,
        *,
        kind: str,
        sha256: str,
    ) -> RecipeModelDownloadCandidate | None:
        """Return a safe exact-hash candidate for a supported model role."""


def candidate_from_recovery_gateways(
    gateways: tuple[RecipeModelRecoveryGateway, ...],
    *,
    kind: str,
    sha256: str,
) -> RecipeModelDownloadCandidate | None:
    """Return the first provider-ordered exact-hash recovery candidate."""

    return next(
        (
            candidate
            for gateway in gateways
            for candidate in (gateway.candidate(kind=kind, sha256=sha256),)
            if candidate is not None
        ),
        None,
    )


def candidate_from_civitai_version(
    *,
    kind: str,
    sha256: str,
    version: CivitaiModelVersion,
    thumbnail_policy: CivitaiThumbnailPolicy,
    download_access: CivitaiDownloadAccess = CivitaiDownloadAccess.UNKNOWN,
) -> RecipeModelDownloadCandidate | None:
    """Return the first safe exact-hash CivitAI file candidate."""

    matching_files = [
        file
        for file in version.files
        if _file_sha256(file) == sha256 and _is_safe_download_file(file)
    ]
    if not matching_files:
        return None
    file = sorted(matching_files, key=lambda item: (not item.primary, item.name))[0]
    assert file.download_url is not None
    return RecipeModelDownloadCandidate(
        kind=kind,
        sha256=sha256,
        name=file.name,
        download_url=file.download_url,
        size_kb=file.size_kb,
        model_id=version.model_id,
        model_version_id=version.model_version_id,
        model_name=version.model_name,
        version_name=version.version_name,
        base_model=version.base_model,
        creator=version.creator_username,
        file_id=file.file_id,
        file_type=file.file_type,
        metadata_format=_string_metadata(file, "format"),
        pickle_scan_result=file.pickle_scan_result,
        virus_scan_result=file.virus_scan_result,
        model_page_url=version.model_page_url,
        thumbnail_url=_thumbnail_url(version, thumbnail_policy=thumbnail_policy),
        download_access=download_access,
        size_bytes=(None if file.size_kb is None else round(file.size_kb * 1024)),
    )


def civitai_download_access(
    civitai: CivitaiMetadataGateway,
    model_version_id: int,
) -> CivitaiDownloadAccess:
    """Return access metadata when the configured CivitAI adapter supports it."""

    lookup = getattr(civitai, "model_version_download_access", None)
    if not callable(lookup):
        return CivitaiDownloadAccess.UNKNOWN
    result = lookup(model_version_id)
    return (
        result
        if isinstance(result, CivitaiDownloadAccess)
        else CivitaiDownloadAccess.UNKNOWN
    )


def _file_sha256(file: CivitaiFile) -> str | None:
    """Return one CivitAI file SHA256 normalized to uppercase."""

    value = file.hashes.get("SHA256")
    return value.upper() if isinstance(value, str) else None


def _thumbnail_url(
    version: CivitaiModelVersion,
    *,
    thumbnail_policy: CivitaiThumbnailPolicy,
) -> str | None:
    """Return an allowed thumbnail URL from already-fetched version metadata."""

    selection = thumbnail_policy.select(version)
    if selection.image is None:
        return None
    return selection.image.url


def _is_safe_download_file(file: CivitaiFile) -> bool:
    """Return whether a CivitAI file is safe enough to offer by default."""

    if not file.download_url:
        return False
    if file.file_type is None or file.file_type.casefold() != "model":
        return False
    if not file.name.casefold().endswith(".safetensors"):
        return False
    format_value = file.metadata.get("format")
    if not isinstance(format_value, str) or format_value.casefold() != "safetensor":
        return False
    for scan_result in (file.pickle_scan_result, file.virus_scan_result):
        if scan_result is None or scan_result.casefold() != "success":
            return False
    return True


def _string_metadata(file: CivitaiFile, key: str) -> str | None:
    """Read one string metadata value from a CivitAI file."""

    value = file.metadata.get(key)
    return value if isinstance(value, str) else None


__all__ = [
    "RecipeModelDownloadCandidate",
    "RecipeModelRecoveryGateway",
    "candidate_from_recovery_gateways",
    "candidate_from_civitai_version",
    "civitai_download_access",
]
