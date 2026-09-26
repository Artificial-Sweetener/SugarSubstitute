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

"""Resolve workflow node classes through bounded public Registry requests."""

from __future__ import annotations

from collections.abc import Mapping
import json
from urllib.error import HTTPError
import urllib.parse
import urllib.request

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
    WorkflowNodepackSourceKind,
)
from sugarsubstitute_shared.tls import SystemTrustTlsContext

_REGISTRY_API_ROOT = "https://api.comfy.org"
_REQUEST_TIMEOUT_SECONDS = 30
_MAX_NODEPACK_BYTES = 256 * 1024
_ACTIVE_NODE_STATUS = "NodeStatusActive"
_ACTIVE_VERSION_STATUS = "NodeVersionStatusActive"


class InvalidRegistryNodepackError(RuntimeError):
    """Report malformed or identity-changing Registry package metadata."""


class ComfyRegistryNodepackClient:
    """Resolve active packages without downloading the global Registry catalog."""

    def get_nodepack(self, registry_id: str) -> ResolvedWorkflowNodepack | None:
        """Return one active package by exact Registry identity."""

        requested_id = _required_request_text(registry_id, "Registry nodepack id")
        payload = self._request(f"/nodes/{urllib.parse.quote(requested_id, safe='')}")
        if payload is None:
            return None
        nodepack = _parse_nodepack(payload)
        if nodepack is None:
            return None
        if nodepack.identifier.casefold() != requested_id.casefold():
            raise InvalidRegistryNodepackError(
                "Comfy Registry changed the requested nodepack identity."
            )
        return nodepack

    def infer_nodepack(self, class_type: str) -> ResolvedWorkflowNodepack | None:
        """Return Registry's preferred active package for one class name."""

        requested_class = _required_request_text(class_type, "Comfy node class")
        payload = self._request(
            f"/comfy-nodes/{urllib.parse.quote(requested_class, safe='')}/node"
        )
        return _parse_nodepack(payload) if payload is not None else None

    @staticmethod
    def _request(path: str) -> Mapping[str, object] | None:
        """Return one bounded JSON object, treating an HTTP 404 as no match."""

        request = urllib.request.Request(
            f"{_REGISTRY_API_ROOT}{path}",
            headers={"Accept": "application/json", "User-Agent": "SugarSubstitute"},
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed HTTPS Registry origin.
                request,
                timeout=_REQUEST_TIMEOUT_SECONDS,
                context=SystemTrustTlsContext.create(),
            ) as response:
                raw_payload = response.read(_MAX_NODEPACK_BYTES + 1)
        except HTTPError as error:
            if error.code == 404:
                return None
            raise
        if len(raw_payload) > _MAX_NODEPACK_BYTES:
            raise InvalidRegistryNodepackError(
                "Comfy Registry nodepack metadata exceeds the size limit."
            )
        try:
            payload = json.loads(raw_payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InvalidRegistryNodepackError(
                "Comfy Registry returned invalid nodepack metadata."
            ) from error
        if not isinstance(payload, Mapping):
            raise InvalidRegistryNodepackError(
                "Comfy Registry returned invalid nodepack metadata."
            )
        return payload


def _parse_nodepack(payload: Mapping[str, object]) -> ResolvedWorkflowNodepack | None:
    """Validate one active package and its latest active release."""

    if payload.get("status") != _ACTIVE_NODE_STATUS:
        return None
    latest = payload.get("latest_version")
    if (
        not isinstance(latest, Mapping)
        or latest.get("status") != _ACTIVE_VERSION_STATUS
    ):
        return None
    registry_id = _required_payload_text(payload, "id")
    display_name = _required_payload_text(payload, "name")
    version = _required_payload_text(latest, "version")
    latest_node_id = _required_payload_text(latest, "node_id")
    if latest_node_id.casefold() != registry_id.casefold():
        raise InvalidRegistryNodepackError(
            "Comfy Registry latest release changed nodepack identity."
        )
    repository = payload.get("repository")
    return ResolvedWorkflowNodepack(
        identifier=registry_id,
        display_name=display_name,
        source_kind=WorkflowNodepackSourceKind.REGISTRY,
        repository_url=(
            repository.strip()
            if isinstance(repository, str) and repository.strip()
            else None
        ),
        version=version,
    )


def _required_request_text(value: str, label: str) -> str:
    """Reject empty request identities before building a Registry URL."""

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must not be empty.")
    return normalized


def _required_payload_text(payload: Mapping[str, object], key: str) -> str:
    """Return one required non-empty Registry response string."""

    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidRegistryNodepackError(
            f"Comfy Registry nodepack metadata has no valid {key}."
        )
    return value.strip()


__all__ = [
    "ComfyRegistryNodepackClient",
    "InvalidRegistryNodepackError",
]
