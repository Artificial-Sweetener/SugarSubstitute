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

"""Parse Manager metadata payloads without owning HTTP transport."""

from __future__ import annotations

import json
from typing import cast

from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
)
from substitute.domain.comfy_startup_diagnostics import (
    ExtensionRepositoryLinks,
    normalize_repository_links,
    repository_links_from_github_id,
)

_INSTALLED_SOURCE = "manager_installed_aux_id"
_CATALOG_SOURCE = "manager_catalog_repository"


class ComfyManagerMetadataParser:
    """Convert Manager payload schemas into application metadata records."""

    def installed(self, payload: object) -> dict[str, ComfyExtensionMetadata]:
        """Return normalized records from an installed-extension payload."""

        if not isinstance(payload, dict):
            return {}
        metadata: dict[str, ComfyExtensionMetadata] = {}
        for key, raw_entry in payload.items():
            if not isinstance(key, str) or not isinstance(raw_entry, dict):
                continue
            entry = cast("dict[object, object]", raw_entry)
            version = _optional_string(entry.get("ver"))
            cnr_id = _optional_string(entry.get("cnr_id"))
            aux_id = _optional_string(entry.get("aux_id"))
            links = (
                repository_links_from_github_id(aux_id, source=_INSTALLED_SOURCE)
                if aux_id
                else None
            )
            metadata[key] = _metadata_from_links(
                key=key,
                version=version,
                cnr_id=cnr_id,
                aux_id=aux_id,
                links=links,
            )
        return metadata

    def merge_catalog(
        self,
        installed: dict[str, ComfyExtensionMetadata],
        catalog_payload: object,
    ) -> dict[str, ComfyExtensionMetadata]:
        """Enrich installed metadata with legacy Manager catalog records."""

        node_packs = _catalog_node_packs(catalog_payload)
        if not node_packs:
            return installed
        enriched = dict(installed)
        for key, metadata in installed.items():
            if metadata.repository_url:
                continue
            catalog_entry = _catalog_entry_for(
                metadata=metadata,
                key=key,
                node_packs=node_packs,
            )
            if catalog_entry is None:
                continue
            links = _catalog_links(catalog_entry)
            if links is None:
                continue
            enriched[key] = ComfyExtensionMetadata(
                key=metadata.key,
                version=metadata.version
                or _optional_string(catalog_entry.get("version")),
                cnr_id=metadata.cnr_id,
                aux_id=metadata.aux_id,
                repository_url=links.repository_url,
                issues_url=links.issues_url,
                source=links.source,
            )
        return enriched


def needs_catalog(metadata: dict[str, ComfyExtensionMetadata]) -> bool:
    """Return whether legacy catalog data can enrich installed records."""

    return any(entry.cnr_id and not entry.repository_url for entry in metadata.values())


def _catalog_node_packs(payload: object) -> dict[str, dict[object, object]]:
    """Return Manager catalog node-pack records from a decoded payload."""

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {}
    if not isinstance(payload, dict):
        return {}
    node_packs = payload.get("node_packs")
    if not isinstance(node_packs, dict):
        return {}
    return {
        key: cast("dict[object, object]", value)
        for key, value in node_packs.items()
        if isinstance(key, str) and isinstance(value, dict)
    }


def _catalog_entry_for(
    *,
    metadata: ComfyExtensionMetadata,
    key: str,
    node_packs: dict[str, dict[object, object]],
) -> dict[object, object] | None:
    """Return the matching catalog entry for one installed extension."""

    candidates = tuple(
        candidate.casefold()
        for candidate in (key, metadata.cnr_id, metadata.aux_id)
        if candidate
    )
    for pack_key, pack in node_packs.items():
        pack_candidates = (
            pack_key,
            _optional_string(pack.get("id")),
            _optional_string(pack.get("title")),
        )
        if any(
            candidate == (pack_candidate or "").casefold()
            for candidate in candidates
            for pack_candidate in pack_candidates
        ):
            return pack
    return None


def _catalog_links(entry: dict[object, object]) -> ExtensionRepositoryLinks | None:
    """Return repository links from one Manager catalog entry."""

    for key in ("repository", "reference"):
        value = _optional_string(entry.get(key))
        if value is None:
            continue
        links = normalize_repository_links(value, source=_CATALOG_SOURCE)
        if links is not None:
            return links
    return None


def _metadata_from_links(
    *,
    key: str,
    version: str | None,
    cnr_id: str | None,
    aux_id: str | None,
    links: ExtensionRepositoryLinks | None,
) -> ComfyExtensionMetadata:
    """Return metadata with optional repository links applied."""

    return ComfyExtensionMetadata(
        key=key,
        version=version,
        cnr_id=cnr_id,
        aux_id=aux_id,
        repository_url=links.repository_url if links else None,
        issues_url=links.issues_url if links else None,
        source=links.source if links else None,
    )


def _optional_string(value: object) -> str | None:
    """Return a non-empty string value."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


__all__ = ["ComfyManagerMetadataParser", "needs_catalog"]
