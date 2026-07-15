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

"""Own prepared LoRA picker snapshots and explicit catalog refreshes."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptLoraCatalogLookup,
)
from substitute.presentation.widgets.media_wall import (
    MediaThumbnailReadiness,
    MediaThumbnailReadinessStatus,
    unavailable_thumbnail_readiness,
)

from .catalog_snapshots import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)


class PromptLoraPickerSnapshotIdentityProvider(Protocol):
    """Build freshness identity for one LoRA picker snapshot publication."""

    def __call__(
        self,
        *,
        catalog_revision: Hashable | None,
        stale: bool,
        unavailable_reason: str | None,
    ) -> CatalogSnapshotIdentity:
        """Return the snapshot identity for the requested publication state."""


@runtime_checkable
class PromptLoraPickerRefreshCatalog(Protocol):
    """Describe LoRA catalog refresh work allowed only on explicit paths."""

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Refresh and return picker-ready LoRA rows."""


@dataclass(frozen=True, slots=True)
class PromptLoraPickerSnapshot:
    """Publish prepared LoRA picker rows for popup foreground consumers."""

    identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus
    items: tuple[PromptLoraCatalogItem, ...]
    catalog_revision: Hashable | None
    dirty: bool
    thumbnail_readiness: tuple[MediaThumbnailReadiness, ...] = ()

    @property
    def consumable(self) -> bool:
        """Return whether foreground code may render the prepared rows."""

        return self.status.consumable


@dataclass(frozen=True, slots=True)
class PromptLoraPickerRefreshResult:
    """Describe the visible effects of one explicit LoRA picker refresh."""

    snapshot: PromptLoraPickerSnapshot
    rows_changed: bool
    revision_changed: bool


class PromptLoraPickerSnapshotController:
    """Prepare LoRA picker snapshots outside popup-open foreground paths."""

    def __init__(
        self,
        *,
        lora_catalog: PromptLoraCatalogLookup | None,
        picker_enabled: Callable[[], bool],
        identity_provider: PromptLoraPickerSnapshotIdentityProvider,
        thumbnail_repository_available: Callable[[], bool] | None = None,
    ) -> None:
        """Store catalog collaborators and seed from non-loading cached rows."""

        self._lora_catalog = lora_catalog
        self._picker_enabled = picker_enabled
        self._identity_provider = identity_provider
        self._thumbnail_repository_available = thumbnail_repository_available or (
            lambda: False
        )
        self._refresh_catalog = (
            lora_catalog
            if isinstance(lora_catalog, PromptLoraPickerRefreshCatalog)
            else None
        )
        self._items: tuple[PromptLoraCatalogItem, ...] = ()
        self._dirty = False
        self._snapshot = self._build_snapshot(
            status=self._base_status(),
            items=(),
            dirty=False,
        )
        self.refresh_from_cache()

    @property
    def snapshot(self) -> PromptLoraPickerSnapshot:
        """Return the latest prepared LoRA picker snapshot."""

        return self._snapshot

    @property
    def picker_available(self) -> bool:
        """Return whether the LoRA picker feature has a catalog to present."""

        return self._picker_enabled() and self._lora_catalog is not None

    def mark_dirty(self) -> None:
        """Mark existing prepared rows stale without loading the catalog."""

        self._dirty = True
        status = self._stale_status() if self._items else self._base_status()
        self._publish(status=status, items=self._items, dirty=True)

    def refresh_from_cache(self) -> bool:
        """Publish currently cached rows without loading or refreshing catalog data."""

        if not self._picker_enabled() or self._lora_catalog is None:
            self._items = ()
            self._dirty = False
            self._publish(status=self._base_status(), items=(), dirty=False)
            return False

        cached_rows = self._lora_catalog.cached_loras()
        if cached_rows is None:
            status = self._stale_status() if self._items else self._base_status()
            self._publish(status=status, items=self._items, dirty=self._dirty)
            return False

        rows = tuple(cached_rows)
        rows_changed = rows != self._items
        self._items = rows
        self._dirty = False
        self._publish(
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            items=rows,
            dirty=False,
        )
        return rows_changed

    def refresh_now(self) -> PromptLoraPickerRefreshResult:
        """Run one explicit catalog refresh and publish a fresh picker snapshot."""

        if not self._picker_enabled() or self._lora_catalog is None:
            self._items = ()
            self._dirty = False
            self._publish(status=self._base_status(), items=(), dirty=False)
            return PromptLoraPickerRefreshResult(
                snapshot=self._snapshot,
                rows_changed=False,
                revision_changed=False,
            )

        previous_revision = self._catalog_revision()
        previous_items = self._items
        rows = tuple(self._refresh_rows())
        self._items = rows
        self._dirty = False
        self._publish(
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
            items=rows,
            dirty=False,
        )
        return PromptLoraPickerRefreshResult(
            snapshot=self._snapshot,
            rows_changed=rows != previous_items,
            revision_changed=self._catalog_revision() != previous_revision,
        )

    def record_refresh_failure(self) -> PromptLoraPickerSnapshot:
        """Publish a failed explicit refresh while preserving stale rows."""

        self._dirty = True
        status = (
            CatalogSnapshotStatus(
                CatalogSnapshotReadiness.STALE,
                unavailable_reason="refresh_failed",
            )
            if self._items
            else CatalogSnapshotStatus(
                CatalogSnapshotReadiness.REFRESH_FAILED,
                unavailable_reason="refresh_failed",
            )
        )
        self._publish(status=status, items=self._items, dirty=True)
        return self._snapshot

    def _refresh_rows(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return picker rows from the explicit refresh-capable catalog path."""

        if self._refresh_catalog is not None:
            return self._refresh_catalog.refresh_loras()
        if self._lora_catalog is None:
            return ()
        return self._lora_catalog.list_loras()

    def _publish(
        self,
        *,
        status: CatalogSnapshotStatus,
        items: tuple[PromptLoraCatalogItem, ...],
        dirty: bool,
    ) -> None:
        """Store one prepared picker snapshot."""

        self._snapshot = self._build_snapshot(status=status, items=items, dirty=dirty)

    def _build_snapshot(
        self,
        *,
        status: CatalogSnapshotStatus,
        items: tuple[PromptLoraCatalogItem, ...],
        dirty: bool,
    ) -> PromptLoraPickerSnapshot:
        """Return a prepared picker snapshot for the current catalog generation."""

        catalog_revision = self._catalog_revision()
        identity = self._identity_provider(
            catalog_revision=catalog_revision,
            stale=status.readiness is CatalogSnapshotReadiness.STALE,
            unavailable_reason=status.unavailable_reason,
        )
        return PromptLoraPickerSnapshot(
            identity=identity,
            status=status,
            items=items,
            catalog_revision=catalog_revision,
            dirty=dirty,
            thumbnail_readiness=self._thumbnail_readiness_for_items(items),
        )

    def _thumbnail_readiness_for_items(
        self,
        items: tuple[PromptLoraCatalogItem, ...],
    ) -> tuple[MediaThumbnailReadiness, ...]:
        """Return metadata-only thumbnail readiness for prepared picker rows."""

        if not items:
            return ()
        repository_available = self._thumbnail_repository_available()
        readiness: list[MediaThumbnailReadiness] = []
        for item in items:
            storage_key = _first_thumbnail_storage_key(item)
            if storage_key is None:
                readiness.append(
                    unavailable_thumbnail_readiness("thumbnail_variant_unavailable")
                )
            elif not repository_available:
                readiness.append(
                    unavailable_thumbnail_readiness("thumbnail_repository_unavailable")
                )
            else:
                readiness.append(
                    MediaThumbnailReadiness(
                        status=MediaThumbnailReadinessStatus.PENDING,
                        storage_key=storage_key,
                    )
                )
        return tuple(readiness)

    def _base_status(self) -> CatalogSnapshotStatus:
        """Return the non-row status implied by current feature/catalog state."""

        if not self._picker_enabled():
            return CatalogSnapshotStatus(
                CatalogSnapshotReadiness.DISABLED,
                unavailable_reason="feature_disabled",
            )
        if self._lora_catalog is None:
            return CatalogSnapshotStatus(
                CatalogSnapshotReadiness.UNAVAILABLE,
                unavailable_reason="catalog_unavailable",
            )
        return CatalogSnapshotStatus(CatalogSnapshotReadiness.COLD)

    @staticmethod
    def _stale_status() -> CatalogSnapshotStatus:
        """Return a consumable stale status for previously prepared rows."""

        return CatalogSnapshotStatus(CatalogSnapshotReadiness.STALE)

    def _catalog_revision(self) -> Hashable | None:
        """Return the LoRA catalog revision when the catalog exposes one."""

        if self._lora_catalog is None:
            return None
        revision = getattr(self._lora_catalog, "cache_revision", None)
        return revision if isinstance(revision, Hashable) else repr(revision)


def _first_thumbnail_storage_key(item: PromptLoraCatalogItem) -> str | None:
    """Return a prepared thumbnail storage key without reading thumbnail data."""

    for variant in item.thumbnail_variants:
        if variant.storage_key:
            return variant.storage_key
    return None


__all__ = [
    "PromptLoraPickerRefreshCatalog",
    "PromptLoraPickerRefreshResult",
    "PromptLoraPickerSnapshot",
    "PromptLoraPickerSnapshotController",
    "PromptLoraPickerSnapshotIdentityProvider",
]
