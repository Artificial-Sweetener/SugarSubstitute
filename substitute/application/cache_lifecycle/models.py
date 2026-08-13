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

"""Define typed persistent-cache governance models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re

_CACHE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CacheDataClass(StrEnum):
    """Classify the reusable data stored by one persistent cache owner."""

    DERIVED_PROJECTION = "derived_projection"
    REMOTE_CONTENT = "remote_content"
    RENDERED_ASSET = "rendered_asset"
    DURABLE_SNAPSHOT = "durable_snapshot"


@dataclass(frozen=True, slots=True)
class CacheCompatibility:
    """Describe namespace-level inputs that make cache data reusable."""

    storage_schema: str
    semantic_epoch: int
    producer_fingerprint: str = ""
    runtime_fingerprint: str = ""
    emergency_epoch: int = 0

    def __post_init__(self) -> None:
        """Reject incomplete or negative compatibility declarations."""

        if not self.storage_schema.strip():
            raise ValueError("Cache storage schema must be non-empty.")
        if self.semantic_epoch < 0:
            raise ValueError("Cache semantic epoch cannot be negative.")
        if self.emergency_epoch < 0:
            raise ValueError("Cache emergency epoch cannot be negative.")

    @property
    def identifier(self) -> str:
        """Return a stable identifier for this exact compatibility contract."""

        encoded = json.dumps(
            {
                "emergency_epoch": self.emergency_epoch,
                "producer_fingerprint": self.producer_fingerprint,
                "runtime_fingerprint": self.runtime_fingerprint,
                "semantic_epoch": self.semantic_epoch,
                "storage_schema": self.storage_schema,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class CacheRetentionPolicy:
    """Bound retained compatibility generations for one cache owner."""

    maximum_generations: int = 2
    maximum_age_days: int | None = 30

    def __post_init__(self) -> None:
        """Reject retention policies that cannot preserve an active generation."""

        if self.maximum_generations < 1:
            raise ValueError("Cache retention must preserve at least one generation.")
        if self.maximum_age_days is not None and self.maximum_age_days < 1:
            raise ValueError("Cache retention age must be positive when provided.")


@dataclass(frozen=True, slots=True)
class PersistentCacheRegistration:
    """Register one persistent cache owner and its complete lifecycle contract."""

    cache_id: str
    namespace: PurePosixPath
    data_class: CacheDataClass
    compatibility: CacheCompatibility
    retention: CacheRetentionPolicy = CacheRetentionPolicy()
    legacy_namespaces: tuple[PurePosixPath, ...] = ()

    def __post_init__(self) -> None:
        """Validate stable identifiers and cache-root-relative namespaces."""

        if _CACHE_ID_PATTERN.fullmatch(self.cache_id) is None:
            raise ValueError(
                "Cache id must use lowercase alphanumeric kebab-case: "
                f"{self.cache_id!r}."
            )
        _validate_namespace(self.namespace, subject=f"Cache {self.cache_id}")
        if (
            self.data_class
            in {
                CacheDataClass.DERIVED_PROJECTION,
                CacheDataClass.DURABLE_SNAPSHOT,
                CacheDataClass.RENDERED_ASSET,
            }
            and not self.compatibility.producer_fingerprint
        ):
            raise ValueError(
                f"Cache {self.cache_id!r} requires a semantic producer fingerprint."
            )
        if (
            self.data_class is CacheDataClass.RENDERED_ASSET
            and not self.compatibility.runtime_fingerprint
        ):
            raise ValueError(
                f"Rendered cache {self.cache_id!r} requires a runtime fingerprint."
            )
        for legacy_namespace in self.legacy_namespaces:
            _validate_namespace(
                legacy_namespace,
                subject=f"Legacy cache {self.cache_id}",
            )


@dataclass(frozen=True, slots=True)
class PersistentCacheCatalog:
    """Own the complete, non-overlapping persistent-cache registration set."""

    registrations: tuple[PersistentCacheRegistration, ...]

    def __post_init__(self) -> None:
        """Reject duplicate identities and overlapping owned namespaces."""

        ids = [registration.cache_id for registration in self.registrations]
        if len(ids) != len(set(ids)):
            raise ValueError("Persistent cache ids must be unique.")
        owned_namespaces = [
            (registration.cache_id, registration.namespace)
            for registration in self.registrations
        ]
        for index, (cache_id, namespace) in enumerate(owned_namespaces):
            for other_id, other_namespace in owned_namespaces[index + 1 :]:
                if _namespaces_overlap(namespace, other_namespace):
                    raise ValueError(
                        "Persistent cache namespaces overlap: "
                        f"{cache_id!r} owns {namespace.as_posix()!r} and "
                        f"{other_id!r} owns {other_namespace.as_posix()!r}."
                    )

    def registration(self, cache_id: str) -> PersistentCacheRegistration:
        """Return the registered cache or fail for an ungoverned identifier."""

        for registration in self.registrations:
            if registration.cache_id == cache_id:
                return registration
        raise KeyError(f"Persistent cache is not registered: {cache_id!r}.")


@dataclass(frozen=True, slots=True)
class PreparedCacheNamespace:
    """Grant one cache owner access to its prepared compatibility generation."""

    cache_id: str
    path: Path
    compatibility_identifier: str
    persistent: bool = True


@dataclass(frozen=True, slots=True)
class PreparedCacheCatalog:
    """Expose only namespaces prepared by the cache lifecycle authority."""

    namespaces: tuple[PreparedCacheNamespace, ...]

    def namespace(self, cache_id: str) -> PreparedCacheNamespace:
        """Return one prepared namespace or reject unregistered cache access."""

        for namespace in self.namespaces:
            if namespace.cache_id == cache_id:
                return namespace
        raise KeyError(f"Persistent cache namespace was not prepared: {cache_id!r}.")


def _validate_namespace(namespace: PurePosixPath, *, subject: str) -> None:
    """Reject absolute, traversal-like, or platform-sensitive namespaces."""

    value = namespace.as_posix()
    if (
        not value
        or value == "."
        or namespace.is_absolute()
        or ".." in namespace.parts
        or "\\" in value
        or any(":" in part for part in namespace.parts)
    ):
        raise ValueError(f"{subject} namespace is unsafe: {value!r}.")


def _namespaces_overlap(left: PurePosixPath, right: PurePosixPath) -> bool:
    """Return whether either namespace contains the other."""

    left_parts = left.parts
    right_parts = right.parts
    shared_length = min(len(left_parts), len(right_parts))
    return left_parts[:shared_length] == right_parts[:shared_length]


__all__ = [
    "CacheCompatibility",
    "CacheDataClass",
    "CacheRetentionPolicy",
    "PersistentCacheCatalog",
    "PersistentCacheRegistration",
    "PreparedCacheCatalog",
    "PreparedCacheNamespace",
]
