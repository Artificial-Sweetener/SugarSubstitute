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

"""Enrich installed CNR packages through the authoritative Comfy Registry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

import requests

from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
)
from substitute.domain.comfy_startup_diagnostics import normalize_repository_links
from substitute.shared.logging.logger import get_logger, log_info

_LOGGER = get_logger("infrastructure.comfy.registry_extension_metadata")
_REGISTRY_SOURCE = "comfy_registry_repository"


class ComfyRegistryMetadataEnricher(Protocol):
    """Enrich installed metadata through an authoritative CNR source."""

    def enrich(
        self,
        installed: Mapping[str, ComfyExtensionMetadata],
    ) -> dict[str, ComfyExtensionMetadata]:
        """Return enriched installed metadata."""

        ...


class ComfyRegistryMetadataClient:
    """Resolve CNR identifiers through the official registry API."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.comfy.org",
        timeout_seconds: float = 2.0,
    ) -> None:
        """Store the bounded registry endpoint configuration."""

        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def enrich(
        self,
        installed: Mapping[str, ComfyExtensionMetadata],
    ) -> dict[str, ComfyExtensionMetadata]:
        """Return installed records enriched by authoritative registry nodes."""

        identifiers = sorted(
            {
                entry.cnr_id
                for entry in installed.values()
                if entry.cnr_id and not entry.repository_url
            }
        )
        if not identifiers:
            return dict(installed)
        try:
            response = requests.get(
                f"{self._base_url}/nodes",
                params=[
                    *(("node_id", identifier) for identifier in identifiers),
                    ("limit", str(len(identifiers))),
                ],
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:
            log_info(
                _LOGGER,
                "Failed to fetch Comfy Registry extension metadata",
                error=repr(error),
                identifiers=identifiers,
            )
            return dict(installed)
        registry_nodes = _registry_nodes_by_id(payload)
        enriched = dict(installed)
        for key, metadata in installed.items():
            if metadata.repository_url or metadata.cnr_id is None:
                continue
            node = registry_nodes.get(metadata.cnr_id)
            if node is None:
                continue
            repository = node.get("repository")
            if not isinstance(repository, str):
                continue
            links = normalize_repository_links(repository, source=_REGISTRY_SOURCE)
            if links is None:
                continue
            enriched[key] = ComfyExtensionMetadata(
                key=metadata.key,
                version=metadata.version or _registry_version(node),
                cnr_id=metadata.cnr_id,
                aux_id=metadata.aux_id,
                repository_url=links.repository_url,
                issues_url=links.issues_url,
                source=links.source,
            )
        return enriched


def _registry_nodes_by_id(payload: object) -> dict[str, dict[str, object]]:
    """Return well-formed registry nodes keyed by CNR identifier."""

    if not isinstance(payload, dict):
        return {}
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return {}
    result: dict[str, dict[str, object]] = {}
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        node = cast("dict[str, object]", raw_node)
        identifier = node.get("id")
        if isinstance(identifier, str):
            result[identifier] = node
    return result


def _registry_version(node: Mapping[str, object]) -> str | None:
    """Return the latest registry version when installed data lacks one."""

    latest = node.get("latest_version")
    if not isinstance(latest, dict):
        return None
    version = latest.get("version")
    return version if isinstance(version, str) and version else None


__all__ = ["ComfyRegistryMetadataClient", "ComfyRegistryMetadataEnricher"]
