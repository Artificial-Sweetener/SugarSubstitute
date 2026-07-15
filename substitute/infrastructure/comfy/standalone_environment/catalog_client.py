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

"""Resolve live Comfy standalone releases to checksum-addressed GitHub assets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import requests

from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifact,
    StandaloneCatalogError,
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)


LATEST_CATALOG_URL = (
    "https://desktop-assets.comfy.org/standalone-environments/latest.json"
)
GITHUB_RELEASE_API_TEMPLATE = (
    "https://api.github.com/repos/Comfy-Org/ComfyUI-Standalone-Environments/"
    "releases/tags/{tag}"
)
_SHA256_PATTERN = re.compile(r"^sha256:([0-9a-f]{64})$")


class StandaloneEnvironmentCatalogClient:
    """Join Comfy's live variant catalog with GitHub's published asset digests."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        """Store the bounded HTTP client used for catalog metadata."""

        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds

    def resolve(self, variant: StandaloneVariantId) -> StandaloneEnvironmentRelease:
        """Resolve one live variant to verified downloadable archive parts."""

        latest = self._fetch_object(LATEST_CATALOG_URL)
        raw_release = latest.get(variant.value)
        if not isinstance(raw_release, dict):
            raise StandaloneCatalogError(
                f"The live Comfy catalog does not publish {variant.value}."
            )
        release = _string_keyed(raw_release, context=variant.value)
        tag = _required_string(release, "tag")
        catalog_filename = _required_string(release, "file")
        expected_size = _required_positive_int(release, "size")
        github_release = self._fetch_object(GITHUB_RELEASE_API_TEMPLATE.format(tag=tag))
        artifacts = _matching_github_artifacts(
            payload=github_release,
            catalog_filename=catalog_filename,
        )
        if sum(artifact.size_bytes for artifact in artifacts) != expected_size:
            raise StandaloneCatalogError(
                f"GitHub assets for {variant.value} do not match the live catalog size."
            )
        return StandaloneEnvironmentRelease(
            variant=variant,
            release_tag=tag,
            comfyui_version=_required_string(release, "comfyui_version"),
            comfyui_commit=_required_string(release, "comfyui_commit"),
            python_version=_required_string(release, "python_version"),
            torch_version=_required_string(release, "torch_version"),
            archive_kind=_archive_kind(catalog_filename),
            artifacts=artifacts,
        )

    def _fetch_object(self, url: str) -> dict[str, Any]:
        """Fetch one JSON object with explicit network bounds."""

        try:
            response = self._session.get(url, timeout=self._timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise StandaloneCatalogError(
                f"Could not load standalone environment metadata from {url}: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise StandaloneCatalogError(
                f"Standalone environment metadata must be a JSON object: {url}"
            )
        return _string_keyed(payload, context=url)


def _matching_github_artifacts(
    *,
    payload: Mapping[str, Any],
    catalog_filename: str,
) -> tuple[StandaloneArtifact, ...]:
    """Return contiguous digest-bearing GitHub parts for one catalog archive."""

    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list):
        raise StandaloneCatalogError("GitHub release metadata has no asset list.")
    matching: list[StandaloneArtifact] = []
    for raw_asset in raw_assets:
        if not isinstance(raw_asset, dict):
            continue
        asset = _string_keyed(raw_asset, context="GitHub release asset")
        filename = asset.get("name")
        if not isinstance(filename, str) or not _matches_archive_part(
            filename,
            catalog_filename,
        ):
            continue
        digest = asset.get("digest")
        match = _SHA256_PATTERN.fullmatch(digest) if isinstance(digest, str) else None
        if match is None:
            raise StandaloneCatalogError(
                f"GitHub did not publish a SHA256 digest for {filename}."
            )
        matching.append(
            StandaloneArtifact(
                filename=filename,
                url=_required_string(asset, "browser_download_url"),
                size_bytes=_required_positive_int(asset, "size"),
                sha256=match.group(1),
            )
        )
    matching.sort(key=lambda artifact: artifact.filename)
    if not matching:
        raise StandaloneCatalogError(
            f"GitHub release does not contain {catalog_filename}."
        )
    _validate_archive_parts(matching, catalog_filename=catalog_filename)
    return tuple(matching)


def _matches_archive_part(filename: str, catalog_filename: str) -> bool:
    """Return whether a GitHub asset is the archive or one numbered part."""

    return filename == catalog_filename or bool(
        re.fullmatch(re.escape(catalog_filename) + r"\.\d{3}", filename)
    )


def _validate_archive_parts(
    artifacts: list[StandaloneArtifact],
    *,
    catalog_filename: str,
) -> None:
    """Reject mixed or non-contiguous multipart archive metadata."""

    if len(artifacts) == 1 and artifacts[0].filename == catalog_filename:
        return
    expected = [
        f"{catalog_filename}.{part_number:03d}"
        for part_number in range(1, len(artifacts) + 1)
    ]
    actual = [artifact.filename for artifact in artifacts]
    if actual != expected:
        raise StandaloneCatalogError(
            f"Standalone archive parts are not contiguous: {actual}"
        )


def _archive_kind(filename: str) -> StandaloneArchiveKind:
    """Resolve the supported archive format from its catalog filename."""

    if filename.endswith(".7z"):
        return StandaloneArchiveKind.SEVEN_ZIP
    if filename.endswith(".tar.gz"):
        return StandaloneArchiveKind.TAR_GZIP
    raise StandaloneCatalogError(f"Unsupported standalone archive format: {filename}")


def _string_keyed(payload: Mapping[object, object], *, context: str) -> dict[str, Any]:
    """Normalize one decoded object while rejecting non-string JSON keys."""

    if any(not isinstance(key, str) for key in payload):
        raise StandaloneCatalogError(f"{context} contains a non-string object key.")
    return {str(key): value for key, value in payload.items()}


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    """Read one required non-empty catalog string."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise StandaloneCatalogError(f"Catalog field must be a string: {key}")
    return value


def _required_positive_int(payload: Mapping[str, Any], key: str) -> int:
    """Read one required positive catalog integer."""

    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise StandaloneCatalogError(f"Catalog field must be a positive integer: {key}")
    return value
