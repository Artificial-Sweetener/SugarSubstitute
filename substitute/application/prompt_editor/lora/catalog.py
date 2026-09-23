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

"""Own the lifecycle of cached prompt-editor LoRA catalog snapshots."""

from __future__ import annotations

import logging
from dataclasses import replace
from threading import RLock

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogService,
)
from substitute.application.prompt_editor.lora.catalog_lookup import (
    build_lora_catalog_snapshot,
    find_lora_in_snapshot,
)
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraCatalogLookup,
    PromptLoraCatalogLookupResult,
    PromptLoraCatalogSnapshot,
    PromptLoraThumbnailVariant,
)
from substitute.application.prompt_editor.lora.catalog_projection import (
    project_lora_catalog_items,
)
from substitute.application.prompt_editor.lora.diagnostics import lora_prompt_context
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LORA_KIND = "loras"
_LOGGER = get_logger("application.prompt_editor.lora.catalog")


class PromptLoraCatalogService:
    """Return current Comfy-visible LoRAs enriched with cached provider metadata."""

    def __init__(
        self,
        *,
        model_catalog: ModelCatalogService,
    ) -> None:
        """Store catalog collaborators for LoRA metadata lookup."""

        self._model_catalog = model_catalog
        self._snapshot: PromptLoraCatalogSnapshot | None = None
        self._cache_revision = 0
        self._lock = RLock()
        self._install_cached_canonical_or_metadata_bootstrap()

    @property
    def cache_revision(self) -> int:
        """Return a revision token that changes after derived snapshot installs."""

        with self._lock:
            return self._cache_revision

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return picker-ready LoRA records for the current Comfy model list."""

        with self._lock:
            snapshot = self._listing_snapshot_locked()
            items = snapshot.items
        return items

    def _listing_snapshot_locked(self) -> PromptLoraCatalogSnapshot:
        """Return LoRA rows for non-hot-path pickers with bootstrap fallback."""

        snapshot = self._current_snapshot_locked()
        if snapshot.authoritative:
            return snapshot
        try:
            model_snapshot = self._model_catalog.snapshot_for_kind(_LORA_KIND)
        except Exception as error:  # noqa: BLE001
            log_warning(
                _LOGGER,
                "Failed to passively refresh LoRA catalog; using bootstrap rows",
                error=repr(error),
            )
            return snapshot
        adapted_items = project_lora_catalog_items(model_snapshot.items)
        if not adapted_items and snapshot.items:
            return snapshot
        prompt_snapshot = build_lora_catalog_snapshot(
            adapted_items,
            model_generation=model_snapshot.generation,
            revision=self._cache_revision,
            authoritative=False,
        )
        self._install_snapshot_locked(prompt_snapshot)
        if self._snapshot is None:
            raise RuntimeError("LoRA catalog passive load did not install a snapshot.")
        return self._snapshot

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return installed LoRA records without loading the backend catalog."""

        with self._lock:
            snapshot = self._snapshot
            if snapshot is None:
                items = None
            else:
                items = snapshot.items
        return items

    def can_report_lora_absence(self) -> bool:
        """Return whether current catalog misses may render as missing LoRAs."""

        with self._lock:
            snapshot = self._snapshot
            result = snapshot is not None and snapshot.authoritative
            return result

    def refresh_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Refresh and return picker-ready LoRA records from Backend availability."""

        with self._lock:
            snapshot = self._refresh_snapshot_locked()
            items = snapshot.items
        return items

    def invalidate(self) -> None:
        """Mark the derived LoRA snapshot stale without downgrading authority."""

        with self._lock:
            if self._snapshot is None:
                return
            if self._snapshot.authoritative:
                self._cache_revision += 1
                return
            self._snapshot = None
            self._cache_revision += 1

    def prepare_snapshot_from_models(
        self,
        models: tuple[ModelCatalogItem, ...],
        *,
        model_generation: int,
    ) -> PromptLoraCatalogSnapshot:
        """Build a prompt LoRA snapshot from canonical LoRA model rows."""

        adapted_items = project_lora_catalog_items(models)
        snapshot = build_lora_catalog_snapshot(
            adapted_items,
            model_generation=model_generation,
            revision=0,
            authoritative=True,
        )
        return snapshot

    def install_snapshot(self, snapshot: PromptLoraCatalogSnapshot) -> None:
        """Install a prepared LoRA snapshot and advance revision when changed."""

        with self._lock:
            self._install_snapshot_locked(snapshot)

    def _current_snapshot_locked(self) -> PromptLoraCatalogSnapshot:
        """Return the installed snapshot, loading passively if missing."""

        if self._snapshot is None:
            self._install_cached_metadata_bootstrap_locked()
        if self._snapshot is None:
            model_snapshot = self._model_catalog.snapshot_for_kind(_LORA_KIND)
            adapted_items = project_lora_catalog_items(model_snapshot.items)
            self._snapshot = build_lora_catalog_snapshot(
                adapted_items,
                model_generation=model_snapshot.generation,
                revision=self._cache_revision,
                authoritative=False,
            )
        return self._snapshot

    def _refresh_snapshot_locked(self) -> PromptLoraCatalogSnapshot:
        """Load a fresh canonical LoRA snapshot and install its prompt projection."""

        model_snapshot = self._model_catalog.refresh_snapshot(_LORA_KIND)
        adapted_items = project_lora_catalog_items(model_snapshot.items)
        prompt_snapshot = build_lora_catalog_snapshot(
            adapted_items,
            model_generation=model_snapshot.generation,
            revision=self._cache_revision,
            authoritative=True,
        )
        self._install_snapshot_locked(prompt_snapshot)
        if self._snapshot is None:
            raise RuntimeError("LoRA catalog refresh did not install a snapshot.")
        return self._snapshot

    def _install_snapshot_locked(self, snapshot: PromptLoraCatalogSnapshot) -> None:
        """Install one prepared snapshot while the catalog lock is held."""

        if (
            self._snapshot is not None
            and self._snapshot.authoritative
            and not snapshot.authoritative
        ):
            return
        if (
            self._snapshot is not None
            and self._snapshot.model_generation == snapshot.model_generation
            and self._snapshot.authoritative == snapshot.authoritative
        ):
            return
        self._cache_revision += 1
        self._snapshot = replace(snapshot, revision=self._cache_revision)

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the current catalog item matching one raw prompt LoRA name."""

        return self.lookup_lora(prompt_name).item

    def lookup_lora(self, prompt_name: str) -> PromptLoraCatalogLookupResult:
        """Return the current catalog lookup result for one raw prompt LoRA name."""

        with self._lock:
            snapshot = self._snapshot
            if snapshot is None:
                self._install_cached_metadata_bootstrap_locked()
                snapshot = self._snapshot
            if snapshot is None:
                _log_lora_catalog_lookup(
                    prompt_name,
                    snapshot=None,
                    diagnostic=PromptLoraCatalogLookupResult(match_source="miss"),
                )
                return PromptLoraCatalogLookupResult(match_source="miss")
        diagnostic = find_lora_in_snapshot(snapshot, prompt_name)
        _log_lora_catalog_lookup(
            prompt_name,
            snapshot=snapshot,
            diagnostic=diagnostic,
        )
        return diagnostic

    def _install_cached_canonical_or_metadata_bootstrap(self) -> None:
        """Install available local LoRA data without requiring Backend I/O."""

        with self._lock:
            self._install_cached_canonical_snapshot_locked()
            self._install_cached_metadata_bootstrap_locked()

    def _install_cached_canonical_snapshot_locked(self) -> None:
        """Install an already-loaded canonical LoRA snapshot when available."""

        if self._snapshot is not None:
            return
        durable_snapshot = getattr(self._model_catalog, "load_durable_snapshot", None)
        if callable(durable_snapshot):
            durable_snapshot(_LORA_KIND)
        cached_snapshot = getattr(self._model_catalog, "cached_snapshot", None)
        if not callable(cached_snapshot):
            return
        model_snapshot = cached_snapshot(_LORA_KIND)
        if model_snapshot is None:
            return
        adapted_items = project_lora_catalog_items(model_snapshot.items)
        self._install_snapshot_locked(
            build_lora_catalog_snapshot(
                adapted_items,
                model_generation=model_snapshot.generation,
                revision=self._cache_revision,
                authoritative=True,
            )
        )

    def _install_cached_metadata_bootstrap_locked(self) -> None:
        """Install a non-authoritative local metadata snapshot when available."""

        if self._snapshot is not None:
            return
        cached_snapshot_for_kind = getattr(
            self._model_catalog,
            "cached_metadata_snapshot_for_kind",
            None,
        )
        if not callable(cached_snapshot_for_kind):
            return
        try:
            model_snapshot = cached_snapshot_for_kind(_LORA_KIND)
        except Exception as error:  # noqa: BLE001
            log_warning(
                _LOGGER,
                "Failed to bootstrap LoRA catalog from local metadata cache",
                error=repr(error),
            )
            return
        adapted_items = project_lora_catalog_items(model_snapshot.items)
        if not adapted_items:
            return
        self._install_snapshot_locked(
            build_lora_catalog_snapshot(
                adapted_items,
                model_generation=model_snapshot.generation,
                revision=self._cache_revision,
                authoritative=False,
            )
        )


def _log_lora_catalog_lookup(
    prompt_name: str,
    *,
    snapshot: PromptLoraCatalogSnapshot | None,
    diagnostic: PromptLoraCatalogLookupResult,
) -> None:
    """Emit one structured diagnostic event for a prompt LoRA lookup."""

    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return
    result = diagnostic.result
    log_debug(
        _LOGGER,
        "prompt_lora_catalog.lookup",
        **lora_prompt_context(prompt_name),
        snapshot_present=snapshot is not None,
        snapshot_authoritative=False if snapshot is None else snapshot.authoritative,
        snapshot_revision=None if snapshot is None else snapshot.revision,
        snapshot_model_generation=None
        if snapshot is None
        else snapshot.model_generation,
        snapshot_item_count=0 if snapshot is None else len(snapshot.items),
        match_source=diagnostic.match_source,
        bare_collision_match_count=diagnostic.bare_collision_match_count,
        ambiguous_candidate_count=diagnostic.ambiguous_candidate_count,
        fallback_candidate_count=diagnostic.fallback_candidate_count,
        selected_fallback_rank=diagnostic.selected_fallback_rank,
        result_backend_value="" if result is None else result.backend_value,
        result_relative_path="" if result is None else result.relative_path,
    )


__all__ = [
    "PromptLoraCatalogItem",
    "PromptLoraCatalogLookup",
    "PromptLoraCatalogLookupResult",
    "PromptLoraCatalogSnapshot",
    "PromptLoraCatalogService",
    "PromptLoraThumbnailVariant",
]
