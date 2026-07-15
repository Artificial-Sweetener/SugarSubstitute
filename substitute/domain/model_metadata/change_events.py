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

"""Define model catalog change events received from Substitute BackEnd."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

MODEL_CATALOG_CHANGE_SCHEMA_VERSION = 1
MODEL_CATALOG_CHANGE_EVENT_TYPE = "substitute_model_catalog_changed"


@dataclass(frozen=True, slots=True)
class BackendModelCatalogChangedSource:
    """Identify a changed model file without exposing absolute local paths."""

    root_id: str
    relative_path: str


@dataclass(frozen=True, slots=True)
class BackendModelCatalogChangedFile:
    """Describe cheap freshness evidence for one changed model file."""

    size_bytes: int
    modified_at: str


@dataclass(frozen=True, slots=True)
class BackendModelCatalogChangedEntry:
    """Represent one added, removed, or modified backend model file."""

    kind: str
    value: str
    source: BackendModelCatalogChangedSource
    file: BackendModelCatalogChangedFile

    @property
    def queue_key(self) -> tuple[str, str, str, int, str]:
        """Return a stable deduplication key for scoped metadata refresh."""

        return (
            self.kind,
            self.source.root_id,
            self.source.relative_path,
            self.file.size_bytes,
            self.file.modified_at,
        )


@dataclass(frozen=True, slots=True)
class BackendModelCatalogChangeEvent:
    """Represent one backend model catalog change notification."""

    schema_version: int
    revision: str
    previous_revision: str
    generated_at: str
    reason: str
    kinds: tuple[str, ...]
    affected_node_classes: tuple[str, ...]
    added: tuple[BackendModelCatalogChangedEntry, ...]
    removed: tuple[BackendModelCatalogChangedEntry, ...]
    modified: tuple[BackendModelCatalogChangedEntry, ...]

    @property
    def enrichable_entries(self) -> tuple[BackendModelCatalogChangedEntry, ...]:
        """Return added and modified entries eligible for CivitAI refresh."""

        return (*self.added, *self.modified)


def parse_backend_model_catalog_change_event(
    data: Mapping[str, object],
) -> BackendModelCatalogChangeEvent | None:
    """Parse a versioned backend model catalog change event payload."""

    schema_version = _required_int(data, "schemaVersion")
    if schema_version != MODEL_CATALOG_CHANGE_SCHEMA_VERSION:
        return None
    revision = _required_string(data, "revision")
    previous_revision = _required_string(data, "previousRevision")
    generated_at = _required_string(data, "generatedAt")
    reason = _required_string(data, "reason")
    if (
        revision is None
        or previous_revision is None
        or generated_at is None
        or reason is None
    ):
        return None
    kinds = _string_tuple(data.get("kinds"))
    affected_node_classes = _string_tuple(data.get("affectedNodeClasses"))
    added = _changed_entries(data.get("added"))
    removed = _changed_entries(data.get("removed"))
    modified = _changed_entries(data.get("modified"))
    if added is None or removed is None or modified is None:
        return None
    return BackendModelCatalogChangeEvent(
        schema_version=schema_version,
        revision=revision,
        previous_revision=previous_revision,
        generated_at=generated_at,
        reason=reason,
        kinds=kinds,
        affected_node_classes=affected_node_classes,
        added=added,
        removed=removed,
        modified=modified,
    )


def _changed_entries(
    value: object,
) -> tuple[BackendModelCatalogChangedEntry, ...] | None:
    """Parse a list of changed model entries."""

    if not isinstance(value, list):
        return None
    entries: list[BackendModelCatalogChangedEntry] = []
    for item in value:
        if not isinstance(item, Mapping):
            return None
        source = item.get("source")
        file_data = item.get("file")
        if not isinstance(source, Mapping) or not isinstance(file_data, Mapping):
            return None
        kind = _required_string(item, "kind")
        value_name = _required_string(item, "value")
        root_id = _required_string(source, "rootId")
        relative_path = _required_string(source, "relativePath")
        size_bytes = _required_int(file_data, "sizeBytes")
        modified_at = _required_string(file_data, "modifiedAt")
        if (
            kind is None
            or value_name is None
            or root_id is None
            or relative_path is None
            or modified_at is None
            or size_bytes is None
        ):
            return None
        entries.append(
            BackendModelCatalogChangedEntry(
                kind=kind,
                value=value_name,
                source=BackendModelCatalogChangedSource(
                    root_id=root_id,
                    relative_path=relative_path,
                ),
                file=BackendModelCatalogChangedFile(
                    size_bytes=size_bytes,
                    modified_at=modified_at,
                ),
            )
        )
    return tuple(entries)


def _string_tuple(value: object) -> tuple[str, ...]:
    """Parse a JSON list of non-empty strings into a stable tuple."""

    if not isinstance(value, list):
        return ()
    return tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )


def _required_string(data: Mapping[str, object], key: str) -> str | None:
    """Return one non-empty string field."""

    value = data.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _required_int(data: Mapping[str, object], key: str) -> int | None:
    """Return one required integer field, excluding bool values."""

    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


__all__ = [
    "MODEL_CATALOG_CHANGE_EVENT_TYPE",
    "MODEL_CATALOG_CHANGE_SCHEMA_VERSION",
    "BackendModelCatalogChangeEvent",
    "BackendModelCatalogChangedEntry",
    "BackendModelCatalogChangedFile",
    "BackendModelCatalogChangedSource",
    "parse_backend_model_catalog_change_event",
]
