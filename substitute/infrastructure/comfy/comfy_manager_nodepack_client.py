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

"""Resolve legacy workflow nodepacks from official ComfyUI-Manager catalogs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import urllib.request

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
    WorkflowNodepackSourceKind,
)
from substitute.infrastructure.comfy.github_repository_revision_client import (
    canonical_github_repository_url,
)
from sugarsubstitute_shared.tls import SystemTrustTlsContext

_CATALOG_ROOT = "https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/main"
_MAPPING_URL = f"{_CATALOG_ROOT}/extension-node-map.json"
_NODEPACK_URL = f"{_CATALOG_ROOT}/custom-node-list.json"
_REQUEST_TIMEOUT_SECONDS = 30
_MAX_CATALOG_BYTES = 8 * 1024 * 1024
_SUPPORTED_INSTALL_TYPES = frozenset({"git", "git-clone"})


class InvalidComfyManagerNodepackCatalogError(RuntimeError):
    """Report malformed ComfyUI-Manager metadata used for installation."""


class ComfyManagerNodepackClient:
    """Resolve exact node classes to confirmed legacy Git repositories."""

    def __init__(self) -> None:
        """Initialize process-lifetime catalog memoization."""

        self._mapping: Mapping[str, object] | None = None
        self._nodepacks: tuple[Mapping[str, object], ...] | None = None

    def infer_nodepack(self, class_type: str) -> ResolvedWorkflowNodepack | None:
        """Return one unambiguous installable package for an exact class name."""

        requested_class = class_type.strip()
        if not requested_class:
            raise ValueError("Comfy node class must not be empty.")
        matches = self._matching_repositories(requested_class)
        if len(matches) != 1:
            return None
        repository_url, mapping_title = next(iter(matches.items()))
        catalog_entries = tuple(
            entry
            for entry in self._load_nodepacks()
            if _catalog_entry_references(entry, repository_url)
        )
        if not catalog_entries:
            return None
        installable = tuple(
            entry
            for entry in catalog_entries
            if _optional_text(entry.get("install_type")).casefold()
            in _SUPPORTED_INSTALL_TYPES
        )
        if not installable:
            return None
        display_name = next(
            (
                title
                for entry in installable
                for title in (
                    _optional_text(entry.get("title")),
                    _optional_text(entry.get("name")),
                )
                if title
            ),
            mapping_title or repository_url.rsplit("/", 1)[-1],
        )
        return ResolvedWorkflowNodepack(
            identifier=repository_url,
            display_name=display_name,
            source_kind=WorkflowNodepackSourceKind.GIT_REPOSITORY,
            repository_url=repository_url,
            version=None,
        )

    def _matching_repositories(self, class_type: str) -> dict[str, str]:
        """Return canonical repositories that explicitly list one node class."""

        matches: dict[str, str] = {}
        for source, raw_entry in self._load_mapping().items():
            entry = _sequence(raw_entry)
            if not entry:
                continue
            classes = _sequence(entry[0])
            if classes is None or class_type not in classes:
                continue
            repository_url = canonical_github_repository_url(source)
            if repository_url is None:
                continue
            metadata = entry[1] if len(entry) > 1 else None
            title = (
                _optional_text(metadata.get("title_aux"))
                if isinstance(metadata, Mapping)
                else ""
            )
            matches[repository_url] = title
        return matches

    def _load_mapping(self) -> Mapping[str, object]:
        """Load and memoize the official class-to-extension mapping."""

        if self._mapping is None:
            payload = _request_json(_MAPPING_URL)
            if not isinstance(payload, Mapping):
                raise InvalidComfyManagerNodepackCatalogError(
                    "ComfyUI-Manager node mapping is not an object."
                )
            self._mapping = payload
        return self._mapping

    def _load_nodepacks(self) -> tuple[Mapping[str, object], ...]:
        """Load and memoize install metadata for mapped repositories."""

        if self._nodepacks is None:
            payload = _request_json(_NODEPACK_URL)
            if not isinstance(payload, Mapping):
                raise InvalidComfyManagerNodepackCatalogError(
                    "ComfyUI-Manager nodepack catalog is not an object."
                )
            raw_nodepacks = payload.get("custom_nodes")
            if not isinstance(raw_nodepacks, list):
                raise InvalidComfyManagerNodepackCatalogError(
                    "ComfyUI-Manager nodepack catalog has no custom_nodes list."
                )
            self._nodepacks = tuple(
                entry for entry in raw_nodepacks if isinstance(entry, Mapping)
            )
        return self._nodepacks


def _request_json(url: str) -> object:
    """Fetch one bounded official Manager JSON document."""

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "SugarSubstitute"},
    )
    with urllib.request.urlopen(  # noqa: S310 - fixed official HTTPS origins.
        request,
        timeout=_REQUEST_TIMEOUT_SECONDS,
        context=SystemTrustTlsContext.create(),
    ) as response:
        raw_payload = response.read(_MAX_CATALOG_BYTES + 1)
    if len(raw_payload) > _MAX_CATALOG_BYTES:
        raise InvalidComfyManagerNodepackCatalogError(
            "ComfyUI-Manager catalog exceeds the size limit."
        )
    try:
        return json.loads(raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidComfyManagerNodepackCatalogError(
            "ComfyUI-Manager returned invalid catalog metadata."
        ) from error


def _catalog_entry_references(entry: Mapping[str, object], repository_url: str) -> bool:
    """Return whether an install entry confirms the mapped repository."""

    references: list[str] = []
    raw_files = entry.get("files")
    if isinstance(raw_files, Sequence) and not isinstance(raw_files, (str, bytes)):
        references.extend(item for item in raw_files if isinstance(item, str))
    reference = entry.get("reference")
    if isinstance(reference, str):
        references.append(reference)
    return any(
        canonical_github_repository_url(candidate) == repository_url
        for candidate in references
    )


def _sequence(value: object) -> Sequence[object] | None:
    """Narrow JSON arrays without treating strings as element sequences."""

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return None


def _optional_text(value: object) -> str:
    """Return stripped optional catalog text."""

    return value.strip() if isinstance(value, str) else ""


__all__ = [
    "ComfyManagerNodepackClient",
    "InvalidComfyManagerNodepackCatalogError",
]
