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

"""Own compatibility generation proof, quarantine, and bounded retention."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
import shutil
from uuid import uuid4

from substitute.application.cache_lifecycle import (
    PersistentCacheRegistration,
    PreparedCacheNamespace,
)
from substitute.infrastructure.cache_lifecycle.atomic_json import (
    read_json_mapping,
    write_json_atomically,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning
from substitute.shared.util.path_safety import ensure_within_root

_LOGGER = get_logger("infrastructure.cache_lifecycle.generation_store")
_MARKER_SCHEMA_VERSION = 1
_GENERATION_MARKER_NAME = "generation.json"
_QUARANTINE_DIRECTORY = "quarantine"
Clock = Callable[[], datetime]


class CacheGenerationStore:
    """Prepare and retain marker-proven generations under one managed root."""

    def __init__(self, managed_root: Path, *, clock: Clock) -> None:
        """Store the governed root and deterministic lifecycle clock."""

        self._managed_root = managed_root
        self._clock = clock

    def prepare(
        self,
        registration: PersistentCacheRegistration,
    ) -> PreparedCacheNamespace:
        """Reuse a verified generation or create a fresh isolated namespace."""

        namespace_root = self._managed_root.joinpath(*registration.namespace.parts)
        compatibility_identifier = registration.compatibility.identifier
        generation_path = namespace_root / compatibility_identifier
        ensure_within_root(
            generation_path,
            root_path=self._managed_root,
            subject=f"Persistent cache {registration.cache_id}",
        )
        marker_path = generation_path / _GENERATION_MARKER_NAME
        existing_marker = read_json_mapping(marker_path)
        if generation_path.exists() and not _marker_matches(
            existing_marker,
            registration=registration,
        ):
            self._quarantine(generation_path, cache_id=registration.cache_id)
        generation_path.mkdir(parents=True, exist_ok=True)
        now_text = self._now_text()
        created_at = _created_at(existing_marker, fallback=now_text)
        decision = "reused" if marker_path.exists() else "created"
        write_json_atomically(
            marker_path,
            _generation_marker(
                registration,
                created_at=created_at,
                last_used_at=now_text,
            ),
        )
        self._prune(
            registration,
            namespace_root=namespace_root,
            active_generation=generation_path,
        )
        log_info(
            _LOGGER,
            "Prepared persistent cache generation.",
            cache_id=registration.cache_id,
            compatibility_identifier=compatibility_identifier[:16],
            decision=decision,
        )
        return PreparedCacheNamespace(
            cache_id=registration.cache_id,
            path=generation_path,
            compatibility_identifier=compatibility_identifier,
        )

    def _quarantine(self, generation_path: Path, *, cache_id: str) -> None:
        """Move an unproven generation aside before a consumer can read it."""

        quarantine_root = self._managed_root / _QUARANTINE_DIRECTORY / cache_id
        quarantine_root.mkdir(parents=True, exist_ok=True)
        destination = quarantine_root / (
            f"{generation_path.name}-{self._timestamp_component()}-{uuid4().hex[:8]}"
        )
        ensure_within_root(
            destination,
            root_path=self._managed_root,
            subject=f"Quarantined cache {cache_id}",
        )
        generation_path.replace(destination)
        log_warning(
            _LOGGER,
            "Quarantined an unproven persistent cache generation.",
            cache_id=cache_id,
            generation=generation_path.name[:16],
        )

    def _prune(
        self,
        registration: PersistentCacheRegistration,
        *,
        namespace_root: Path,
        active_generation: Path,
    ) -> None:
        """Delete only marker-proven generations outside retention bounds."""

        proven = self._proven_generations(registration, namespace_root=namespace_root)
        maximum = registration.retention.maximum_generations
        cutoff = self._retention_cutoff(registration)
        for index, (last_used, candidate) in enumerate(proven):
            if candidate == active_generation:
                continue
            over_count = index >= maximum
            over_age = cutoff is not None and last_used.timestamp() < cutoff
            if not over_count and not over_age:
                continue
            self._delete_proven_generation(
                registration.cache_id,
                candidate,
                reason="retention_count" if over_count else "retention_age",
            )

    def _proven_generations(
        self,
        registration: PersistentCacheRegistration,
        *,
        namespace_root: Path,
    ) -> list[tuple[datetime, Path]]:
        """Return newest-first generations whose markers grant prune authority."""

        proven: list[tuple[datetime, Path]] = []
        for candidate in namespace_root.iterdir():
            if not candidate.is_dir():
                continue
            marker = read_json_mapping(candidate / _GENERATION_MARKER_NAME)
            if marker is None or not _marker_proves_owned_generation(
                marker,
                cache_id=registration.cache_id,
                generation_name=candidate.name,
            ):
                log_warning(
                    _LOGGER,
                    "Left unproven content inside a persistent cache namespace.",
                    cache_id=registration.cache_id,
                    entry_name=candidate.name,
                )
                continue
            last_used = _marker_timestamp(marker, "last_used_at")
            if last_used is None:
                log_warning(
                    _LOGGER,
                    "Left a cache generation whose retention timestamp is invalid.",
                    cache_id=registration.cache_id,
                    generation=candidate.name[:16],
                )
                continue
            proven.append((last_used, candidate))
        proven.sort(key=lambda item: (item[0], item[1].name), reverse=True)
        return proven

    def _retention_cutoff(
        self,
        registration: PersistentCacheRegistration,
    ) -> float | None:
        """Return the oldest retained timestamp, or no age boundary."""

        maximum_age_days = registration.retention.maximum_age_days
        if maximum_age_days is None:
            return None
        return self._clock().astimezone(UTC).timestamp() - (
            maximum_age_days * 24 * 60 * 60
        )

    def _delete_proven_generation(
        self,
        cache_id: str,
        candidate: Path,
        *,
        reason: str,
    ) -> None:
        """Delete one contained marker-proven generation without blocking startup."""

        ensure_within_root(
            candidate,
            root_path=self._managed_root,
            subject=f"Pruned cache {cache_id}",
        )
        try:
            shutil.rmtree(candidate)
        except OSError as error:
            log_warning(
                _LOGGER,
                "Failed to prune a proven persistent cache generation.",
                cache_id=cache_id,
                generation=candidate.name[:16],
                error=repr(error),
            )
            return
        log_info(
            _LOGGER,
            "Pruned a persistent cache generation.",
            cache_id=cache_id,
            generation=candidate.name[:16],
            reason=reason,
        )

    def _now_text(self) -> str:
        """Return one normalized UTC lifecycle timestamp."""

        return self._clock().astimezone(UTC).isoformat(timespec="microseconds")

    def _timestamp_component(self) -> str:
        """Return a filesystem-safe timestamp component."""

        return self._clock().astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _marker_matches(
    marker: Mapping[str, object] | None,
    *,
    registration: PersistentCacheRegistration,
) -> bool:
    """Return whether a generation marker proves exact compatibility."""

    return marker is not None and (
        marker.get("schema_version") == _MARKER_SCHEMA_VERSION
        and marker.get("cache_id") == registration.cache_id
        and marker.get("compatibility_identifier")
        == registration.compatibility.identifier
    )


def _created_at(marker: Mapping[str, object] | None, *, fallback: str) -> str:
    """Preserve a valid generation creation timestamp across reuse."""

    if marker is None:
        return fallback
    value = marker.get("created_at")
    return value if isinstance(value, str) else fallback


def _generation_marker(
    registration: PersistentCacheRegistration,
    *,
    created_at: str,
    last_used_at: str,
) -> dict[str, object]:
    """Serialize proof binding a generation path to its registered owner."""

    return {
        "schema_version": _MARKER_SCHEMA_VERSION,
        "cache_id": registration.cache_id,
        "compatibility_identifier": registration.compatibility.identifier,
        "storage_schema": registration.compatibility.storage_schema,
        "semantic_epoch": registration.compatibility.semantic_epoch,
        "created_at": created_at,
        "last_used_at": last_used_at,
    }


def _marker_proves_owned_generation(
    marker: Mapping[str, object],
    *,
    cache_id: str,
    generation_name: str,
) -> bool:
    """Return whether a marker grants pruning authority over its directory."""

    return (
        marker.get("schema_version") == _MARKER_SCHEMA_VERSION
        and marker.get("cache_id") == cache_id
        and marker.get("compatibility_identifier") == generation_name
    )


def _marker_timestamp(
    marker: Mapping[str, object],
    key: str,
) -> datetime | None:
    """Parse one timezone-aware marker timestamp for retention decisions."""

    value = marker.get(key)
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


__all__ = ["CacheGenerationStore"]
