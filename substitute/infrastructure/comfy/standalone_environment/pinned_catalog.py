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

"""Load and write the authoritative managed-Comfy standalone pin."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Any, Self
from urllib.parse import urlparse

from substitute.infrastructure.comfy.standalone_environment.models import (
    StandaloneArchiveKind,
    StandaloneArtifact,
    StandaloneCatalogError,
    StandaloneEnvironmentRelease,
    StandaloneVariantId,
)


PIN_SCHEMA_VERSION = 1
DEFAULT_PIN_PATH = Path(__file__).with_name("standalone_environment_pin.json")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PinnedStandaloneEnvironmentCatalog:
    """Resolve managed environments only from reviewed immutable metadata."""

    def __init__(
        self,
        releases: Mapping[StandaloneVariantId, StandaloneEnvironmentRelease],
    ) -> None:
        """Store a complete immutable variant map."""

        missing = set(StandaloneVariantId) - set(releases)
        unexpected = set(releases) - set(StandaloneVariantId)
        if missing or unexpected:
            raise StandaloneCatalogError(
                "Pinned standalone variants are incomplete; "
                f"missing={sorted(item.value for item in missing)}, "
                f"unexpected={sorted(str(item) for item in unexpected)}."
            )
        self._releases = MappingProxyType(dict(releases))

    @classmethod
    def load_default(cls) -> Self:
        """Load the production managed-Comfy pin shipped with the app."""

        return cls.load(DEFAULT_PIN_PATH)

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load and validate one schema-versioned pin file."""

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise StandaloneCatalogError(
                f"Could not load the managed-Comfy pin: {path}"
            ) from error
        return cls.from_json(payload)

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse a complete pinned catalog from decoded JSON."""

        root = _string_mapping(payload, context="managed-Comfy pin")
        if root.get("schema_version") != PIN_SCHEMA_VERSION:
            raise StandaloneCatalogError(
                f"Unsupported managed-Comfy pin schema: {root.get('schema_version')}"
            )
        raw_releases = _string_mapping(
            root.get("releases"), context="managed-Comfy releases"
        )
        expected_keys = {variant.value for variant in StandaloneVariantId}
        actual_keys = set(raw_releases)
        if actual_keys != expected_keys:
            raise StandaloneCatalogError(
                "Pinned standalone variants are incomplete; "
                f"missing={sorted(expected_keys - actual_keys)}, "
                f"unexpected={sorted(actual_keys - expected_keys)}."
            )
        return cls(
            {
                variant: _parse_release(
                    variant,
                    _string_mapping(raw_releases[variant.value], context=variant.value),
                )
                for variant in StandaloneVariantId
            }
        )

    def resolve(self, variant: StandaloneVariantId) -> StandaloneEnvironmentRelease:
        """Return the exact pinned release for one managed target."""

        return self._releases[variant]

    def to_json(self) -> dict[str, object]:
        """Return stable JSON data suitable for the authoritative pin file."""

        return {
            "schema_version": PIN_SCHEMA_VERSION,
            "releases": {
                variant.value: _release_to_json(self._releases[variant])
                for variant in StandaloneVariantId
            },
        }


def write_pinned_catalog(
    path: Path,
    releases: Sequence[StandaloneEnvironmentRelease],
) -> None:
    """Atomically write a complete deterministic managed-Comfy pin."""

    catalog = PinnedStandaloneEnvironmentCatalog(
        {release.variant: release for release in releases}
    )
    payload = json.dumps(catalog.to_json(), indent=2, sort_keys=True) + "\n"
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path.write_text(payload, encoding="utf-8")
    temporary_path.replace(path)


def _parse_release(
    variant: StandaloneVariantId,
    payload: Mapping[str, Any],
) -> StandaloneEnvironmentRelease:
    """Parse one pinned variant release with fail-closed validation."""

    raw_artifacts = payload.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise StandaloneCatalogError(f"Pinned {variant.value} artifacts are missing.")
    artifacts = tuple(
        _parse_artifact(_string_mapping(item, context=f"{variant.value} artifact"))
        for item in raw_artifacts
    )
    if len({artifact.filename for artifact in artifacts}) != len(artifacts):
        raise StandaloneCatalogError(
            f"Pinned {variant.value} artifact filenames must be unique."
        )
    try:
        archive_kind = StandaloneArchiveKind(_required_string(payload, "archive_kind"))
    except ValueError as error:
        raise StandaloneCatalogError(
            f"Pinned {variant.value} archive kind is unsupported."
        ) from error
    return StandaloneEnvironmentRelease(
        variant=variant,
        release_tag=_required_string(payload, "release_tag"),
        comfyui_version=_required_string(payload, "comfyui_version"),
        comfyui_commit=_required_string(payload, "comfyui_commit"),
        python_version=_required_string(payload, "python_version"),
        torch_version=_required_string(payload, "torch_version"),
        archive_kind=archive_kind,
        artifacts=artifacts,
    )


def _parse_artifact(payload: Mapping[str, Any]) -> StandaloneArtifact:
    """Parse one immutable HTTPS artifact and its integrity metadata."""

    filename = _required_string(payload, "filename")
    if PurePath(filename).name != filename or filename in {".", ".."}:
        raise StandaloneCatalogError(
            f"Pinned standalone artifact filename is unsafe: {filename}"
        )
    url = _required_string(payload, "url")
    if urlparse(url).scheme != "https":
        raise StandaloneCatalogError(
            f"Pinned standalone artifact URL must use HTTPS: {filename}"
        )
    sha256 = _required_string(payload, "sha256")
    if _SHA256_PATTERN.fullmatch(sha256) is None:
        raise StandaloneCatalogError(
            f"Pinned standalone artifact SHA256 is invalid: {filename}"
        )
    return StandaloneArtifact(
        filename=filename,
        url=url,
        size_bytes=_required_positive_int(payload, "size_bytes"),
        sha256=sha256,
    )


def _release_to_json(release: StandaloneEnvironmentRelease) -> dict[str, object]:
    """Serialize one pinned release without introducing alternate ownership."""

    return {
        "archive_kind": release.archive_kind.value,
        "artifacts": [
            {
                "filename": artifact.filename,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "url": artifact.url,
            }
            for artifact in release.artifacts
        ],
        "comfyui_commit": release.comfyui_commit,
        "comfyui_version": release.comfyui_version,
        "python_version": release.python_version,
        "release_tag": release.release_tag,
        "torch_version": release.torch_version,
    }


def _string_mapping(payload: object, *, context: str) -> dict[str, Any]:
    """Return one string-keyed object or reject malformed pin data."""

    if not isinstance(payload, dict) or any(
        not isinstance(key, str) for key in payload
    ):
        raise StandaloneCatalogError(f"{context} must be a string-keyed object.")
    return {str(key): value for key, value in payload.items()}


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    """Return one required non-empty pin string."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise StandaloneCatalogError(f"Pinned field must be a string: {key}")
    return value


def _required_positive_int(payload: Mapping[str, Any], key: str) -> int:
    """Return one required positive pin integer."""

    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise StandaloneCatalogError(f"Pinned field must be a positive integer: {key}")
    return value


__all__ = [
    "DEFAULT_PIN_PATH",
    "PIN_SCHEMA_VERSION",
    "PinnedStandaloneEnvironmentCatalog",
    "write_pinned_catalog",
]
