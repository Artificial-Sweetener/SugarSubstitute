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

"""Resolve one exact trusted release from the public Comfy Registry."""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import HTTPError
import urllib.parse
import urllib.request

from substitute.infrastructure.comfy.nodepack_manifest import CoreComfyNodepack
from sugarsubstitute_shared.tls import SystemTrustTlsContext

_REGISTRY_API_ROOT = "https://api.comfy.org"
_REGISTRY_ARCHIVE_HOST = "cdn.comfy.org"
_REGISTRY_REQUEST_TIMEOUT_SECONDS = 30
_MAX_DESCRIPTOR_BYTES = 64 * 1024


class RegistryReleaseUnavailableError(RuntimeError):
    """Report that Registry has no requested exact nodepack release."""


class InvalidRegistryReleaseError(RuntimeError):
    """Report Registry metadata that fails the exact-release trust contract."""


@dataclass(frozen=True, slots=True)
class ComfyRegistryRelease:
    """Carry a validated exact Registry archive descriptor."""

    node_id: str
    version: str
    archive_url: str


class ComfyRegistryReleaseClient:
    """Fetch bounded exact-release metadata from fixed Registry infrastructure."""

    def resolve_exact(self, nodepack: CoreComfyNodepack) -> ComfyRegistryRelease:
        """Return one exact release only after validating identity and archive origin."""

        node_id = urllib.parse.quote(nodepack.registry_id, safe="")
        query = urllib.parse.urlencode({"version": nodepack.required_version})
        request = urllib.request.Request(
            f"{_REGISTRY_API_ROOT}/nodes/{node_id}/install?{query}",
            headers={"Accept": "application/json", "User-Agent": "SugarSubstitute"},
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed HTTPS Registry origin.
                request,
                timeout=_REGISTRY_REQUEST_TIMEOUT_SECONDS,
                context=SystemTrustTlsContext.create(),
            ) as response:
                raw_payload = response.read(_MAX_DESCRIPTOR_BYTES + 1)
        except HTTPError as error:
            if error.code == 404:
                raise RegistryReleaseUnavailableError(
                    f"Comfy Registry has no {nodepack.registry_id} "
                    f"{nodepack.required_version} release."
                ) from error
            raise
        if len(raw_payload) > _MAX_DESCRIPTOR_BYTES:
            raise InvalidRegistryReleaseError(
                "Comfy Registry exact-release metadata exceeds the size limit."
            )
        try:
            payload = json.loads(raw_payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InvalidRegistryReleaseError(
                "Comfy Registry returned invalid exact-release metadata."
            ) from error
        if not isinstance(payload, dict):
            raise InvalidRegistryReleaseError(
                "Comfy Registry returned invalid exact-release metadata."
            )
        observed_node_id = _required_text(payload, "node_id")
        observed_version = _required_text(payload, "version")
        archive_url = _required_text(payload, "downloadUrl")
        if observed_node_id.casefold() != nodepack.registry_id.casefold():
            raise InvalidRegistryReleaseError(
                "Comfy Registry exact-release metadata changed nodepack identity."
            )
        if observed_version != nodepack.required_version:
            raise InvalidRegistryReleaseError(
                "Comfy Registry exact-release metadata changed the requested version."
            )
        _validate_archive_url(archive_url)
        return ComfyRegistryRelease(
            node_id=observed_node_id,
            version=observed_version,
            archive_url=archive_url,
        )


def _required_text(payload: dict[object, object], key: str) -> str:
    """Return one non-empty string field from Registry metadata."""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidRegistryReleaseError(
            f"Comfy Registry exact-release metadata has no valid {key}."
        )
    return value.strip()


def _validate_archive_url(archive_url: str) -> None:
    """Restrict Registry packages to the public Comfy CDN over standard TLS."""

    parsed = urllib.parse.urlsplit(archive_url)
    try:
        port = parsed.port
    except ValueError as error:
        raise InvalidRegistryReleaseError(
            "Comfy Registry returned an invalid archive URL."
        ) from error
    if (
        parsed.scheme.casefold() != "https"
        or parsed.hostname != _REGISTRY_ARCHIVE_HOST
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/")
        or parsed.fragment
    ):
        raise InvalidRegistryReleaseError(
            "Comfy Registry returned an untrusted archive URL."
        )


__all__ = [
    "ComfyRegistryRelease",
    "ComfyRegistryReleaseClient",
    "InvalidRegistryReleaseError",
    "RegistryReleaseUnavailableError",
]
