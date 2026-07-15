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

"""Index model catalog rows by exact Comfy choice value for rich LIST pickers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from threading import RLock, current_thread
from typing import cast

from substitute.application.model_metadata.model_catalog_service import (
    ModelCatalogItem,
    ModelCatalogLookup,
    ModelCatalogSnapshot,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.model_metadata.model_choice_catalog_index")
DEFAULT_RICH_CHOICE_MODEL_KINDS = (
    "checkpoints",
    "loras",
    "vae",
    "diffusion_models",
)


class ModelChoiceCatalogIndex:
    """Cache exact-value lookups across rich-picker-enabled model kinds."""

    def __init__(
        self,
        *,
        model_catalog: ModelCatalogLookup,
        enabled_kinds: Iterable[str] = DEFAULT_RICH_CHOICE_MODEL_KINDS,
    ) -> None:
        """Store the catalog and model kinds used for rich choice enrichment."""

        self._model_catalog = model_catalog
        self._enabled_kinds = tuple(
            dict.fromkeys(kind.strip() for kind in enabled_kinds if kind.strip())
        )
        self._items_by_kind: dict[str, tuple[ModelCatalogItem, ...]] = {}
        self._generations_by_kind: dict[str, int] = {}
        self._items_by_value: dict[str, tuple[ModelCatalogItem, ...]] = {}
        self._loaded = False
        self._generation = 0
        self._lock = RLock()

    @property
    def enabled_kinds(self) -> tuple[str, ...]:
        """Return model kinds eligible for rich LIST picker enrichment."""

        return self._enabled_kinds

    @property
    def generation(self) -> int:
        """Return the current catalog index generation."""

        with self._lock:
            return self._generation

    def candidates_for_value(self, value: str) -> tuple[ModelCatalogItem, ...]:
        """Return catalog candidates whose exact backend value matches the choice."""

        self._ensure_loaded(allow_blocking=False)
        with self._lock:
            return self._items_by_value.get(value, ())

    def prewarm(self) -> None:
        """Load enabled model kinds and build the exact-value index."""

        self._ensure_loaded(allow_blocking=True)

    def refresh_kinds(self, kinds: Iterable[str]) -> None:
        """Refresh selected model kinds and rebuild exact-value indexes."""

        selected = tuple(
            kind for kind in dict.fromkeys(kinds) if kind in self._enabled_kinds
        )
        if not selected:
            return
        loaded = {kind: self._load_snapshot(kind, refresh=True) for kind in selected}
        with self._lock:
            for kind, snapshot in loaded.items():
                self._install_snapshot_unlocked(snapshot)
            self._loaded = True
            self._generation += 1
            self._rebuild_value_index_unlocked()

    def invalidate(self, kinds: Iterable[str] | None = None) -> None:
        """Forget loaded model-choice indexes so later lookups reload fresh data."""

        selected = (
            tuple(self._enabled_kinds)
            if kinds is None
            else tuple(
                kind for kind in dict.fromkeys(kinds) if kind in self._enabled_kinds
            )
        )
        if not selected:
            return
        with self._lock:
            for kind in selected:
                self._items_by_kind.pop(kind, None)
            self._loaded = False
            self._generation += 1
            self._rebuild_value_index_unlocked()

    def _ensure_loaded(self, *, allow_blocking: bool) -> None:
        """Load enabled model kinds once before the first lookup."""

        with self._lock:
            if self._loaded:
                return
        if not allow_blocking and self._install_cached_snapshots_for_gui_read():
            return
        loaded = {
            kind: self._load_snapshot(kind, refresh=False)
            for kind in self._enabled_kinds
        }
        with self._lock:
            if self._loaded:
                return
            for snapshot in loaded.values():
                self._install_snapshot_unlocked(snapshot)
            self._loaded = True
            self._rebuild_value_index_unlocked()

    def _install_cached_snapshots_for_gui_read(self) -> bool:
        """Install already-cached snapshots for a nonblocking main-thread lookup."""

        if current_thread().name != "MainThread":
            return False
        cached_snapshot = cast(
            Callable[[str], ModelCatalogSnapshot | None] | None,
            getattr(self._model_catalog, "cached_snapshot_nowait", None),
        )
        if not callable(cached_snapshot):
            return False
        if not self._lock.acquire(blocking=False):
            return True
        try:
            for kind in self._enabled_kinds:
                snapshot = cached_snapshot(kind)
                if snapshot is None:
                    continue
                current_generation = self._generations_by_kind.get(kind, -1)
                if snapshot.generation < current_generation:
                    continue
                self._install_snapshot_unlocked(snapshot)
            self._rebuild_value_index_unlocked()
        finally:
            self._lock.release()
        return True

    def _items_for_kind(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return already loaded items for one kind."""

        with self._lock:
            return self._items_by_kind.get(kind, ())

    def _rebuild_value_index_unlocked(self) -> None:
        """Rebuild exact-value candidates while the caller holds the lock."""

        grouped: defaultdict[str, list[ModelCatalogItem]] = defaultdict(list)
        for kind in self._enabled_kinds:
            for item in self._items_by_kind.get(kind, ()):
                grouped[item.backend_value].append(item)
        self._items_by_value = {value: tuple(items) for value, items in grouped.items()}

    def _load_snapshot(
        self,
        kind: str,
        *,
        refresh: bool,
    ) -> ModelCatalogSnapshot:
        """Load one model snapshot while keeping failures local to classification."""

        try:
            current_generation = self._generation_for_kind(kind)
            if refresh:
                cached_snapshot = self._cached_model_snapshot(kind)
                if (
                    cached_snapshot is not None
                    and cached_snapshot.generation > current_generation
                ):
                    return cached_snapshot
                refresh_snapshot = cast(
                    Callable[[str], ModelCatalogSnapshot] | None,
                    getattr(self._model_catalog, "refresh_snapshot", None),
                )
                if callable(refresh_snapshot):
                    return refresh_snapshot(kind)
                return ModelCatalogSnapshot(
                    kind=kind,
                    items=self._model_catalog.refresh_models(kind),
                    generation=current_generation + 1,
                )
            snapshot_for_kind = cast(
                Callable[[str], ModelCatalogSnapshot] | None,
                getattr(self._model_catalog, "snapshot_for_kind", None),
            )
            if callable(snapshot_for_kind):
                return snapshot_for_kind(kind)
            return ModelCatalogSnapshot(
                kind=kind,
                items=self._model_catalog.list_models(kind),
                generation=max(0, current_generation),
            )
        except Exception as error:
            log_warning(
                _LOGGER,
                "Failed to load model choice catalog kind",
                model_kind=kind,
                refresh=refresh,
                error=repr(error),
            )
            if refresh:
                raise
            return ModelCatalogSnapshot(
                kind=kind,
                items=self._items_for_kind(kind),
                generation=self._generation_for_kind(kind),
            )

    def _cached_model_snapshot(self, kind: str) -> ModelCatalogSnapshot | None:
        """Return a canonical cached snapshot when the catalog exposes one."""

        cached_snapshot = cast(
            Callable[[str], ModelCatalogSnapshot | None] | None,
            getattr(self._model_catalog, "cached_snapshot", None),
        )
        if not callable(cached_snapshot):
            return None
        return cached_snapshot(kind)

    def _generation_for_kind(self, kind: str) -> int:
        """Return the canonical generation last installed for one kind."""

        with self._lock:
            return self._generations_by_kind.get(kind, -1)

    def _install_snapshot_unlocked(self, snapshot: ModelCatalogSnapshot) -> None:
        """Install one canonical model snapshot while the caller holds the lock."""

        self._items_by_kind[snapshot.kind] = snapshot.items
        self._generations_by_kind[snapshot.kind] = snapshot.generation

    def _rebuild_value_index(self) -> None:
        """Rebuild exact backend-value candidate lookup from loaded catalog rows."""

        with self._lock:
            self._rebuild_value_index_unlocked()


__all__ = [
    "DEFAULT_RICH_CHOICE_MODEL_KINDS",
    "ModelChoiceCatalogIndex",
]
