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

"""Own root cache diagnostics, manifest recovery, and unknown-content reporting."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from substitute.application.cache_lifecycle import (
    PersistentCacheCatalog,
    PreparedCacheNamespace,
)
from substitute.infrastructure.cache_lifecycle.atomic_json import (
    read_json_mapping,
    write_json_atomically,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.cache_lifecycle.manifest_store")
_MANIFEST_SCHEMA_VERSION = 1
_MANAGED_DIRECTORY = "managed"
_MANIFEST_NAME = "persistent-cache-manifest.json"
_MANIFEST_TEMP_NAME = f"{_MANIFEST_NAME}.tmp"
Clock = Callable[[], datetime]


class PersistentCacheManifestStore:
    """Persist diagnostic active-generation state without owning compatibility."""

    def __init__(
        self,
        cache_root: Path,
        *,
        application_version: str,
        clock: Clock,
    ) -> None:
        """Store the root, diagnostic version, and lifecycle clock."""

        self._cache_root = cache_root
        self._application_version = application_version
        self._clock = clock

    def validate_or_quarantine(self) -> None:
        """Quarantine an unreadable manifest while preserving valid generations."""

        manifest_path = self._cache_root / _MANIFEST_NAME
        if not manifest_path.exists():
            return
        manifest = read_json_mapping(manifest_path)
        if (
            manifest is not None
            and manifest.get("schema_version") == _MANIFEST_SCHEMA_VERSION
        ):
            return
        quarantine_path = self._cache_root / (
            f"{_MANIFEST_NAME}.corrupt-{self._timestamp_component()}-{uuid4().hex[:8]}"
        )
        manifest_path.replace(quarantine_path)
        log_warning(
            _LOGGER,
            "Quarantined an unreadable persistent cache manifest.",
            cache_root=self._cache_root,
        )

    def save(
        self,
        catalog: PersistentCacheCatalog,
        *,
        prepared: tuple[PreparedCacheNamespace, ...],
    ) -> None:
        """Atomically record active generations without affecting compatibility."""

        registrations = {item.cache_id: item for item in catalog.registrations}
        payload: dict[str, object] = {
            "schema_version": _MANIFEST_SCHEMA_VERSION,
            "application_version": self._application_version,
            "updated_at": self._now_text(),
            "active_generations": {
                item.cache_id: {
                    "namespace": registrations[item.cache_id].namespace.as_posix(),
                    "compatibility_identifier": item.compatibility_identifier,
                }
                for item in prepared
            },
        }
        write_json_atomically(self._cache_root / _MANIFEST_NAME, payload)

    def report_unknown_root_content(self, catalog: PersistentCacheCatalog) -> None:
        """Report unowned cache-root entries without mutating them."""

        known_names = {_MANAGED_DIRECTORY, _MANIFEST_NAME, _MANIFEST_TEMP_NAME}
        for registration in catalog.registrations:
            known_names.update(
                path.parts[0] for path in registration.legacy_namespaces if path.parts
            )
        for child in self._cache_root.iterdir():
            if child.name not in known_names and not child.name.startswith(
                f"{_MANIFEST_NAME}.corrupt-"
            ):
                log_warning(
                    _LOGGER,
                    "Found unregistered content under the persistent cache root.",
                    entry_name=child.name,
                )

    def _now_text(self) -> str:
        """Return one normalized UTC lifecycle timestamp."""

        return self._clock().astimezone(UTC).isoformat(timespec="microseconds")

    def _timestamp_component(self) -> str:
        """Return a filesystem-safe timestamp component."""

        return self._clock().astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


__all__ = ["PersistentCacheManifestStore"]
