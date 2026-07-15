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

"""Build picker-ready model catalog records from backend and metadata cache data."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import RLock
from typing import Protocol

from substitute.application.execution import BlockingSingleFlight
from substitute.application.model_metadata.ports import (
    BackendModelMetadataGateway,
    ModelMetadataCatalogQueryRepository,
)
from substitute.application.model_metadata.model_catalog_snapshot_store import (
    ModelCatalogSnapshotStore,
)
from substitute.domain.model_metadata import (
    BackendModelCatalogEntry,
    ModelMetadataCacheRecord,
    STANDARD_THUMBNAIL_ROLE,
)

_SUPPORTED_MODEL_EXTENSIONS = frozenset({".safetensors", ".ckpt", ".pt"})


@dataclass(frozen=True, slots=True)
class ModelThumbnailVariant:
    """Reference one prepared model thumbnail asset safe for presentation use."""

    size: int
    storage_key: str
    width: int
    height: int
    content_format: str
    byte_size: int
    role: str = STANDARD_THUMBNAIL_ROLE


@dataclass(frozen=True, slots=True)
class ModelCatalogItem:
    """Describe one Comfy-visible model enriched with cached provider metadata."""

    kind: str
    display_name: str
    display_subtitle: str | None
    backend_value: str
    relative_path: str
    folder: str
    basename: str
    extension: str
    thumbnail_variants: tuple[ModelThumbnailVariant, ...]
    base_model: str | None
    trained_words: tuple[str, ...]
    tags: tuple[str, ...]
    model_page_url: str | None
    collision_key: str
    collision_count: int
    has_collision: bool
    search_text: str
    provider_name: str | None = None
    provider_model_id: str | None = None
    provider_model_version_id: str | None = None
    provider_model_name: str | None = None
    provider_model_version_name: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    modified_at: str | None = None


@dataclass(frozen=True, slots=True)
class ModelCatalogSnapshot:
    """Store one canonical model catalog generation for a single kind."""

    kind: str
    items: tuple[ModelCatalogItem, ...]
    generation: int


class ModelCatalogLookup(Protocol):
    """Describe picker-ready catalog lookup for metadata-backed model selectors."""

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return picker-ready model records for one model kind."""

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Reload and return picker-ready model records for one model kind."""

    def invalidate(self, kind: str | None = None) -> None:
        """Clear cached snapshots for one kind or all kinds."""


class ModelCatalogService:
    """Return Comfy-visible models enriched with cached provider metadata."""

    def __init__(
        self,
        *,
        backend: BackendModelMetadataGateway,
        metadata_catalog: ModelMetadataCatalogQueryRepository,
        model_metadata_root: Path,
        snapshot_store: ModelCatalogSnapshotStore | None = None,
    ) -> None:
        """Store catalog collaborators for model metadata lookup."""

        self._backend = backend
        self._metadata_catalog = metadata_catalog
        self._model_metadata_root = model_metadata_root.resolve()
        self._snapshot_store = snapshot_store
        self._snapshots: dict[str, ModelCatalogSnapshot] = {}
        self._generations: dict[str, int] = {}
        self._snapshot_single_flight: BlockingSingleFlight[
            str, ModelCatalogSnapshot
        ] = BlockingSingleFlight()
        self._lock = RLock()

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return picker-ready model records for one model kind."""

        return self.snapshot_for_kind(kind).items

    def snapshot_for_kind(self, kind: str) -> ModelCatalogSnapshot:
        """Return the current canonical snapshot for one kind, loading if needed."""

        normalized_kind = _normalized_kind(kind)
        with self._lock:
            snapshot = self._snapshots.get(normalized_kind)
            if snapshot is not None:
                return snapshot
        return self._snapshot_single_flight.run(
            normalized_kind,
            lambda: self._load_snapshot_for_kind(normalized_kind),
        )

    def _load_snapshot_for_kind(self, normalized_kind: str) -> ModelCatalogSnapshot:
        """Load and install one canonical snapshot for a normalized model kind."""

        with self._lock:
            existing = self._snapshots.get(normalized_kind)
            generation = self._generations.get(normalized_kind, 0)
            if existing is not None:
                return existing
        items = self._load_models(normalized_kind, refresh=False)
        with self._lock:
            existing = self._snapshots.get(normalized_kind)
            if existing is not None:
                return existing
            generation = self._generations.get(normalized_kind, generation)
            snapshot = ModelCatalogSnapshot(
                kind=normalized_kind,
                items=items,
                generation=generation,
            )
            self._snapshots[normalized_kind] = snapshot
            self._generations[normalized_kind] = generation
            return snapshot

    def prewarm_models(self, kinds: tuple[str, ...]) -> None:
        """Load model snapshots for the requested kinds without refreshing metadata."""

        for kind in kinds:
            self.list_models(kind)

    def cached_kinds(self) -> tuple[str, ...]:
        """Return model kinds currently cached in memory."""

        with self._lock:
            return tuple(sorted(self._snapshots))

    def cached_models(self, kind: str) -> tuple[ModelCatalogItem, ...] | None:
        """Return an in-memory model snapshot without loading missing data."""

        snapshot = self.cached_snapshot(kind)
        return None if snapshot is None else snapshot.items

    def cached_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return an in-memory canonical snapshot without loading missing data."""

        with self._lock:
            return self._snapshots.get(_normalized_kind(kind))

    def cached_snapshot_nowait(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a cached snapshot only when the catalog lock is immediately free."""

        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            return None
        try:
            return self._snapshots.get(_normalized_kind(kind))
        finally:
            self._lock.release()

    def load_durable_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Load and install the newest durable authoritative snapshot for one kind."""

        normalized_kind = _normalized_kind(kind)
        with self._lock:
            existing = self._snapshots.get(normalized_kind)
            if existing is not None:
                return existing
        if self._snapshot_store is None:
            return None
        snapshot = self._snapshot_store.load_snapshot(normalized_kind)
        if snapshot is None:
            return None
        with self._lock:
            existing = self._snapshots.get(normalized_kind)
            if existing is not None:
                return existing
            self._snapshots[normalized_kind] = snapshot
            self._generations[normalized_kind] = max(
                self._generations.get(normalized_kind, 0),
                snapshot.generation,
            )
        return snapshot

    def cached_metadata_snapshot_for_kind(self, kind: str) -> ModelCatalogSnapshot:
        """Return metadata-cache model rows without asking Backend for availability.

        This snapshot is intentionally not installed as a canonical model snapshot.
        It exists for startup presentation paths that can use persisted metadata to
        render names and thumbnails before Backend has reported live availability.
        """

        normalized_kind = _normalized_kind(kind)
        cached_records = self._metadata_catalog.list_records(kind=normalized_kind)
        items = _items_from_cached_records(normalized_kind, cached_records)
        with self._lock:
            generation = self._generations.get(normalized_kind, 0)
        snapshot = ModelCatalogSnapshot(
            kind=normalized_kind,
            items=items,
            generation=generation,
        )
        return snapshot

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Reload and return picker-ready model records for one model kind."""

        return self.refresh_snapshot(kind).items

    def refresh_snapshot(self, kind: str) -> ModelCatalogSnapshot:
        """Reload, install, and return the canonical snapshot for one model kind."""

        normalized_kind = _normalized_kind(kind)
        items = self._load_models(normalized_kind, refresh=True)
        with self._lock:
            generation = self._generations.get(normalized_kind, 0) + 1
            self._generations[normalized_kind] = generation
            snapshot = ModelCatalogSnapshot(
                kind=normalized_kind,
                items=items,
                generation=generation,
            )
            self._snapshots[normalized_kind] = snapshot
        self._save_durable_snapshot(snapshot)
        return snapshot

    def invalidate(self, kind: str | None = None) -> None:
        """Clear cached snapshots for one kind or all kinds."""

        with self._lock:
            if kind is None:
                for cached_kind in tuple(set(self._snapshots) | set(self._generations)):
                    self._generations[cached_kind] = (
                        self._generations.get(cached_kind, 0) + 1
                    )
                self._snapshots.clear()
                return
            normalized_kind = _normalized_kind(kind)
            self._snapshots.pop(normalized_kind, None)
            self._generations[normalized_kind] = (
                self._generations.get(normalized_kind, 0) + 1
            )

    def _load_models(
        self,
        kind: str,
        *,
        refresh: bool,
    ) -> tuple[ModelCatalogItem, ...]:
        """Load picker-ready model records from backend and metadata cache."""

        cached_records = self._metadata_catalog.list_records(kind=kind)
        entries = tuple(
            entry
            for entry in self._backend.list_models((kind,), refresh=refresh)
            if entry.kind == kind
        )
        records = _records_by_lookup_key(cached_records)
        collision_counts = Counter(
            _collision_key_for_value(entry.value) for entry in entries
        )

        items: list[ModelCatalogItem] = []
        for entry in entries:
            record = _record_for_entry(entry, records)
            collision_key = _collision_key_for_value(entry.value)
            collision_count = collision_counts[collision_key]
            display_name = _display_name_for_entry(entry, record)
            display_subtitle = _display_subtitle_for_record(record)
            folder = _folder_for_path(entry.source.relative_path)
            basename = _basename_without_extension(entry.value)
            base_model = _base_model_for_entry(entry, record)
            trained_words = (
                ()
                if record is None or record.provider is None
                else record.provider.trained_words
            )
            tags = (
                ()
                if record is None or record.provider is None
                else record.provider.tags
            )
            model_page_url = (
                None
                if record is None or record.provider is None
                else record.provider.model_page_url
            )
            provider_name = _provider_name_for_record(record)
            provider_model_id = _provider_model_id_for_record(record)
            provider_model_version_id = _provider_model_version_id_for_record(record)
            provider_model_name = (
                None
                if record is None or record.provider is None
                else record.provider.model_name
            )
            provider_model_version_name = (
                None
                if record is None or record.provider is None
                else record.provider.version_name
            )
            sha256 = _sha256_for_entry(entry)
            if sha256 is None and record is not None:
                sha256 = record.local.sha256
            items.append(
                ModelCatalogItem(
                    kind=entry.kind,
                    display_name=display_name,
                    display_subtitle=display_subtitle,
                    backend_value=entry.value,
                    relative_path=entry.source.relative_path,
                    folder=folder,
                    basename=basename,
                    extension=_extension_for_value(entry.value),
                    thumbnail_variants=_thumbnail_variants_for_record(record),
                    base_model=base_model,
                    trained_words=trained_words,
                    tags=tags,
                    model_page_url=model_page_url,
                    collision_key=collision_key,
                    collision_count=collision_count,
                    has_collision=collision_count > 1,
                    search_text=_search_text(
                        display_name=display_name,
                        display_subtitle=display_subtitle,
                        backend_value=entry.value,
                        relative_path=entry.source.relative_path,
                        folder=folder,
                        basename=basename,
                        base_model=base_model,
                        trained_words=trained_words,
                        tags=tags,
                    ),
                    provider_name=provider_name,
                    provider_model_id=provider_model_id,
                    provider_model_version_id=provider_model_version_id,
                    provider_model_name=provider_model_name,
                    provider_model_version_name=provider_model_version_name,
                    sha256=sha256.upper() if sha256 else None,
                    size_bytes=entry.file.size_bytes,
                    modified_at=entry.file.modified_at,
                )
            )

        result = tuple(
            sorted(
                items,
                key=lambda item: (
                    item.display_name.casefold(),
                    item.relative_path.casefold(),
                ),
            )
        )
        return result

    def _save_durable_snapshot(self, snapshot: ModelCatalogSnapshot) -> None:
        """Persist one accepted authoritative snapshot when configured."""

        if self._snapshot_store is None:
            return
        self._snapshot_store.save_snapshot(snapshot)


def _normalized_kind(kind: str) -> str:
    """Return the normalized model kind used for backend catalog lookup."""

    return kind.strip()


def _backend_value_for_record(record: ModelMetadataCacheRecord) -> str:
    """Return the backend value represented by one cached local evidence row."""

    value = record.local.value.strip()
    if value:
        return value
    return record.local.relative_path


def _records_by_lookup_key(
    records: tuple[ModelMetadataCacheRecord, ...],
) -> dict[tuple[str, str, str], ModelMetadataCacheRecord]:
    """Index cache records by the stable local evidence keys used for merging."""

    records_by_key: dict[tuple[str, str, str], ModelMetadataCacheRecord] = {}
    for record in records:
        records_by_key[
            (
                record.local.kind,
                record.local.value.casefold(),
                record.local.relative_path.casefold(),
            )
        ] = record
        if record.local.sha256:
            records_by_key[
                (record.local.kind, f"sha256:{record.local.sha256.upper()}", "")
            ] = record
    return records_by_key


def _record_for_entry(
    entry: BackendModelCatalogEntry,
    records: dict[tuple[str, str, str], ModelMetadataCacheRecord],
) -> ModelMetadataCacheRecord | None:
    """Return the cached metadata record matching one backend catalog entry."""

    sha256 = _sha256_for_entry(entry)
    if sha256:
        record = records.get((entry.kind, f"sha256:{sha256.upper()}", ""))
        if record is not None:
            return record
    return records.get(
        (
            entry.kind,
            entry.value.casefold(),
            entry.source.relative_path.casefold(),
        )
    )


def _items_from_cached_records(
    kind: str,
    records: tuple[ModelMetadataCacheRecord, ...],
) -> tuple[ModelCatalogItem, ...]:
    """Build presentation-only model rows from persisted local metadata records."""

    collision_counts = Counter(
        _collision_key_for_value(_backend_value_for_record(record))
        for record in records
        if record.local.kind == kind
    )
    items: list[ModelCatalogItem] = []
    for record in records:
        if record.local.kind != kind:
            continue
        backend_value = _backend_value_for_record(record)
        relative_path = record.local.relative_path.strip() or backend_value
        display_name = _display_name_for_record(record)
        display_subtitle = _display_subtitle_for_record(record)
        folder = _folder_for_path(relative_path)
        basename = _basename_without_extension(backend_value)
        base_model = _base_model_for_record(record)
        trained_words = _trained_words_for_record(record)
        tags = _tags_for_record(record)
        collision_key = _collision_key_for_value(backend_value)
        collision_count = collision_counts[collision_key]
        sha256 = record.local.sha256.strip().upper() if record.local.sha256 else None
        items.append(
            ModelCatalogItem(
                kind=kind,
                display_name=display_name,
                display_subtitle=display_subtitle,
                backend_value=backend_value,
                relative_path=relative_path,
                folder=folder,
                basename=basename,
                extension=_extension_for_value(backend_value),
                thumbnail_variants=_thumbnail_variants_for_record(record),
                base_model=base_model,
                trained_words=trained_words,
                tags=tags,
                model_page_url=_model_page_url_for_record(record),
                collision_key=collision_key,
                collision_count=collision_count,
                has_collision=collision_count > 1,
                search_text=_search_text(
                    display_name=display_name,
                    display_subtitle=display_subtitle,
                    backend_value=backend_value,
                    relative_path=relative_path,
                    folder=folder,
                    basename=basename,
                    base_model=base_model,
                    trained_words=trained_words,
                    tags=tags,
                ),
                provider_name=_provider_name_for_record(record),
                provider_model_id=_provider_model_id_for_record(record),
                provider_model_version_id=_provider_model_version_id_for_record(record),
                provider_model_name=None
                if record.provider is None
                else record.provider.model_name,
                provider_model_version_name=None
                if record.provider is None
                else record.provider.version_name,
                sha256=sha256,
                size_bytes=record.local.size_bytes,
                modified_at=record.local.modified_at,
            )
        )
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.display_name.casefold(),
                item.relative_path.casefold(),
            ),
        )
    )


def _sha256_for_entry(entry: BackendModelCatalogEntry) -> str | None:
    """Return the best SHA256 evidence available on one backend entry."""

    if entry.fingerprint.sha256:
        return entry.fingerprint.sha256
    return entry.sidecar.sha256


def _display_name_for_entry(
    entry: BackendModelCatalogEntry,
    record: ModelMetadataCacheRecord | None,
) -> str:
    """Return the picker display name for one model catalog entry."""

    fallback_name = _fallback_display_name_for_entry(entry)
    if record is not None and record.provider is not None:
        provider_model_name = record.provider.model_name.strip()
        if provider_model_name:
            return provider_model_name
    return fallback_name


def _display_name_for_record(record: ModelMetadataCacheRecord) -> str:
    """Return the picker display name for one local cache record."""

    if record.provider is not None:
        provider_model_name = record.provider.model_name.strip()
        if provider_model_name:
            return provider_model_name
    display_name = record.local.display_name.strip()
    if display_name:
        return _strip_supported_extension(display_name)
    return _basename_without_extension(_backend_value_for_record(record))


def _display_subtitle_for_record(
    record: ModelMetadataCacheRecord | None,
) -> str | None:
    """Return a useful provider version subtitle for one cached record."""

    if record is None or record.provider is None:
        return None
    stripped_version_name = record.provider.version_name.strip()
    if not stripped_version_name:
        return None
    if _normalized_display_name(stripped_version_name) == _normalized_display_name(
        record.provider.model_name
    ):
        return None
    return stripped_version_name


def _base_model_for_record(record: ModelMetadataCacheRecord) -> str | None:
    """Return the provider base model for one cached record when available."""

    if record.provider is None or not record.provider.base_model:
        return None
    return record.provider.base_model


def _trained_words_for_record(record: ModelMetadataCacheRecord) -> tuple[str, ...]:
    """Return cached provider trigger words for one record."""

    if record.provider is None:
        return ()
    return record.provider.trained_words


def _tags_for_record(record: ModelMetadataCacheRecord) -> tuple[str, ...]:
    """Return cached provider tags for one record."""

    if record.provider is None:
        return ()
    return record.provider.tags


def _model_page_url_for_record(record: ModelMetadataCacheRecord) -> str | None:
    """Return the provider model page URL for one cached record."""

    if record.provider is None:
        return None
    return record.provider.model_page_url


def _fallback_display_name_for_entry(entry: BackendModelCatalogEntry) -> str:
    """Return the local fallback label for one model."""

    display_name = entry.display_name.strip()
    if display_name:
        return _strip_supported_extension(display_name)
    return _basename_without_extension(entry.value)


def _base_model_for_entry(
    entry: BackendModelCatalogEntry,
    record: ModelMetadataCacheRecord | None,
) -> str | None:
    """Return the most useful base-model label available for one model."""

    if (
        record is not None
        and record.provider is not None
        and record.provider.base_model
    ):
        return record.provider.base_model
    return entry.sidecar.base_model


def _provider_name_for_record(record: ModelMetadataCacheRecord | None) -> str | None:
    """Return the provider identifier for one cached model record."""

    if record is None or record.provider is None:
        return None
    return "civitai"


def _provider_model_id_for_record(
    record: ModelMetadataCacheRecord | None,
) -> str | None:
    """Return the provider model id as a stable preset key part."""

    if record is None or record.provider is None:
        return None
    return str(record.provider.model_id)


def _provider_model_version_id_for_record(
    record: ModelMetadataCacheRecord | None,
) -> str | None:
    """Return the provider model version id as a stable preset key part."""

    if record is None or record.provider is None:
        return None
    return str(record.provider.model_version_id)


def _thumbnail_variants_for_record(
    record: ModelMetadataCacheRecord | None,
) -> tuple[ModelThumbnailVariant, ...]:
    """Return storage-key thumbnail variants for one cache record."""

    if record is None or record.thumbnail is None:
        return ()
    return tuple(
        sorted(
            (
                ModelThumbnailVariant(
                    size=variant.size,
                    storage_key=variant.storage_key,
                    width=variant.width,
                    height=variant.height,
                    content_format=variant.content_format,
                    byte_size=variant.byte_size,
                    role=variant.role,
                )
                for variant in record.thumbnail.variants
            ),
            key=lambda variant: (variant.role, variant.size),
        )
    )


def _strip_supported_extension(value: str) -> str:
    """Strip the final model extension from one path while preserving separators."""

    extension = _extension_for_value(value)
    if extension in _SUPPORTED_MODEL_EXTENSIONS:
        return value[: -len(extension)]
    return value


def _extension_for_value(value: str) -> str:
    """Return the final file extension from one backend value."""

    windows_suffix = PureWindowsPath(value).suffix
    posix_suffix = PurePosixPath(value).suffix
    return (windows_suffix or posix_suffix).lower()


def _basename_without_extension(value: str) -> str:
    """Return the extensionless basename for one backend value."""

    normalized_value = value.replace("\\", "/")
    name = PurePosixPath(normalized_value).name
    return _strip_supported_extension(name)


def _folder_for_path(value: str) -> str:
    """Return the folder portion of one backend path while preserving separator style."""

    slash_index = max(value.rfind("\\"), value.rfind("/"))
    if slash_index < 0:
        return ""
    return value[:slash_index]


def _collision_key_for_value(value: str) -> str:
    """Return the collision key used to detect bare-name ambiguity."""

    return _basename_without_extension(value).casefold()


def _search_text(
    *,
    display_name: str,
    display_subtitle: str | None,
    backend_value: str,
    relative_path: str,
    folder: str,
    basename: str,
    base_model: str | None,
    trained_words: tuple[str, ...],
    tags: tuple[str, ...],
) -> str:
    """Return precomputed casefolded search text for one catalog item."""

    return (
        " ".join(
            (
                display_name,
                display_subtitle or "",
                backend_value,
                relative_path,
                folder,
                basename,
                base_model or "",
                " ".join(trained_words),
                " ".join(tags),
            )
        )
        .replace("\\", "/")
        .casefold()
    )


def _normalized_display_name(value: str) -> str:
    """Return a compact display-name comparison key."""

    return " ".join(value.replace("_", " ").replace("-", " ").casefold().split())


__all__ = [
    "ModelCatalogItem",
    "ModelCatalogLookup",
    "ModelCatalogService",
    "ModelCatalogSnapshot",
    "ModelThumbnailVariant",
]
