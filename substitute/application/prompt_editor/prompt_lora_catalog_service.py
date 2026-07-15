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

"""Build picker-ready LoRA catalog records from backend and metadata cache data."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import PurePosixPath, PureWindowsPath
from threading import RLock
from types import MappingProxyType
from typing import Protocol

from substitute.application.model_metadata import (
    ModelCatalogItem,
    ModelCatalogService,
    ModelThumbnailVariant,
)
from substitute.application.prompt_editor.prompt_lora_diagnostics import (
    lora_prompt_context,
)
from substitute.application.prompt_editor.prompt_lora_ranking import (
    normalize_lora_query,
    ranked_lora_matches_for_query,
    strip_lora_extension,
)
from substitute.domain.model_metadata import STANDARD_THUMBNAIL_ROLE
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LORA_KIND = "loras"
_SUPPORTED_MODEL_EXTENSIONS = frozenset({".safetensors", ".ckpt", ".pt"})
_LOGGER = get_logger("application.prompt_editor.prompt_lora_catalog_service")


@dataclass(frozen=True, slots=True)
class PromptLoraThumbnailVariant:
    """Reference one prepared LoRA thumbnail asset safe for presentation use."""

    size: int
    storage_key: str
    width: int
    height: int
    content_format: str
    byte_size: int
    role: str = STANDARD_THUMBNAIL_ROLE


@dataclass(frozen=True, slots=True)
class PromptLoraCatalogItem:
    """Describe one LoRA record ready for prompt picker and renderer use."""

    display_name: str
    display_subtitle: str | None
    prompt_name: str
    backend_value: str
    relative_path: str
    folder: str
    basename: str
    extension: str
    thumbnail_variants: tuple[PromptLoraThumbnailVariant, ...]
    base_model: str | None
    trained_words: tuple[str, ...]
    tags: tuple[str, ...]
    model_page_url: str | None
    collision_key: str
    collision_count: int
    has_collision: bool
    search_text: str


@dataclass(frozen=True, slots=True)
class PromptLoraCatalogSnapshot:
    """Store one immutable LoRA catalog generation plus lookup indexes.

    Bootstrap snapshots are allowed to prove a LoRA exists from persisted local
    metadata, but only authoritative Backend-derived snapshots can prove absence.
    """

    items: tuple[PromptLoraCatalogItem, ...]
    prompt_name_items: Mapping[str, PromptLoraCatalogItem]
    backend_value_items: Mapping[str, PromptLoraCatalogItem]
    backend_prompt_items: Mapping[str, PromptLoraCatalogItem]
    collision_items: Mapping[str, tuple[PromptLoraCatalogItem, ...]]
    autocomplete_exact_items: Mapping[str, tuple[PromptLoraCatalogItem, ...]]
    path_suffix_items: Mapping[str, tuple[PromptLoraCatalogItem, ...]]
    model_generation: int
    revision: int
    authoritative: bool = True


@dataclass(frozen=True, slots=True)
class PromptLoraCatalogLookupResult:
    """Describe how one prompt LoRA lookup resolved against a snapshot."""

    match_source: str
    bare_collision_match_count: int = 0
    ambiguous_candidate_count: int = 0
    fallback_candidate_count: int = 0
    selected_fallback_rank: int | None = None
    item: PromptLoraCatalogItem | None = None

    @property
    def result(self) -> PromptLoraCatalogItem | None:
        """Return the matched LoRA item for compatibility with older tests."""

        return self.item


class PromptLoraCatalogLookup(Protocol):
    """Describe read-only LoRA catalog lookup needed by prompt syntax services."""

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return installed LoRA records without loading the backend catalog."""

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return picker-ready LoRA records for the current Comfy model list."""

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the catalog item matching one prompt LoRA reference."""


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
        adapted_items = self._adapt_loras(model_snapshot.items)
        if not adapted_items and snapshot.items:
            return snapshot
        prompt_snapshot = self._snapshot_for_items(
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

        adapted_items = self._adapt_loras(models)
        snapshot = self._snapshot_for_items(
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
            adapted_items = self._adapt_loras(model_snapshot.items)
            self._snapshot = self._snapshot_for_items(
                adapted_items,
                model_generation=model_snapshot.generation,
                revision=self._cache_revision,
                authoritative=False,
            )
        return self._snapshot

    def _refresh_snapshot_locked(self) -> PromptLoraCatalogSnapshot:
        """Load a fresh canonical LoRA snapshot and install its prompt projection."""

        model_snapshot = self._model_catalog.refresh_snapshot(_LORA_KIND)
        adapted_items = self._adapt_loras(model_snapshot.items)
        prompt_snapshot = self._snapshot_for_items(
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

    def _adapt_loras(
        self,
        models: tuple[ModelCatalogItem, ...],
    ) -> tuple[PromptLoraCatalogItem, ...]:
        """Adapt generic catalog records into prompt-editor LoRA catalog items."""

        items: list[PromptLoraCatalogItem] = []
        for model in models:
            items.append(
                PromptLoraCatalogItem(
                    display_name=model.display_name,
                    display_subtitle=model.display_subtitle,
                    prompt_name=_prompt_name_for_backend_value(model.backend_value),
                    backend_value=model.backend_value,
                    relative_path=model.relative_path,
                    folder=model.folder,
                    basename=model.basename,
                    extension=model.extension,
                    thumbnail_variants=_thumbnail_variants_for_model(model),
                    base_model=model.base_model,
                    trained_words=model.trained_words,
                    tags=model.tags,
                    model_page_url=model.model_page_url,
                    collision_key=model.collision_key,
                    collision_count=model.collision_count,
                    has_collision=model.has_collision,
                    search_text=_search_text(
                        display_name=model.display_name,
                        display_subtitle=model.display_subtitle,
                        backend_value=model.backend_value,
                        relative_path=model.relative_path,
                        folder=model.folder,
                        basename=model.basename,
                        base_model=model.base_model,
                        trained_words=model.trained_words,
                        tags=model.tags,
                    ),
                )
            )

        adapted = tuple(
            sorted(
                items,
                key=lambda item: (
                    item.display_name.casefold(),
                    item.relative_path.casefold(),
                ),
            )
        )
        return adapted

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
        diagnostic = _find_lora_in_snapshot(snapshot, prompt_name)
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
        adapted_items = self._adapt_loras(model_snapshot.items)
        self._install_snapshot_locked(
            self._snapshot_for_items(
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
        adapted_items = self._adapt_loras(model_snapshot.items)
        if not adapted_items:
            return
        self._install_snapshot_locked(
            self._snapshot_for_items(
                adapted_items,
                model_generation=model_snapshot.generation,
                revision=self._cache_revision,
                authoritative=False,
            )
        )

    def _snapshot_for_items(
        self,
        items: tuple[PromptLoraCatalogItem, ...],
        *,
        model_generation: int,
        revision: int,
        authoritative: bool,
    ) -> PromptLoraCatalogSnapshot:
        """Build indexed catalog lookup state from ordered LoRA items."""

        prompt_name_items: dict[str, PromptLoraCatalogItem] = {}
        backend_value_items: dict[str, PromptLoraCatalogItem] = {}
        backend_prompt_items: dict[str, PromptLoraCatalogItem] = {}
        collision_lists: dict[str, list[PromptLoraCatalogItem]] = defaultdict(list)
        autocomplete_exact_lists: dict[str, list[PromptLoraCatalogItem]] = defaultdict(
            list
        )
        path_suffix_lists: dict[str, list[PromptLoraCatalogItem]] = defaultdict(list)
        for item in items:
            prompt_name_items.setdefault(_prompt_lookup_key(item.prompt_name), item)
            backend_value_items.setdefault(
                _backend_lookup_key(item.backend_value), item
            )
            backend_prompt_items.setdefault(
                _prompt_lookup_key(item.backend_value), item
            )
            collision_lists[item.collision_key].append(item)
            for key in _autocomplete_exact_keys(item):
                autocomplete_exact_lists[key].append(item)
            for key in _path_suffix_keys(item):
                path_suffix_lists[key].append(item)
        collision_items = {
            key: tuple(bucket) for key, bucket in collision_lists.items()
        }
        autocomplete_exact_items = {
            key: _ranked_items_for_query(key, tuple(bucket))
            for key, bucket in autocomplete_exact_lists.items()
        }
        path_suffix_items = {
            key: _ranked_items_for_query(key, tuple(bucket))
            for key, bucket in path_suffix_lists.items()
        }
        snapshot = PromptLoraCatalogSnapshot(
            items=items,
            prompt_name_items=MappingProxyType(prompt_name_items),
            backend_value_items=MappingProxyType(backend_value_items),
            backend_prompt_items=MappingProxyType(backend_prompt_items),
            collision_items=MappingProxyType(collision_items),
            autocomplete_exact_items=MappingProxyType(autocomplete_exact_items),
            path_suffix_items=MappingProxyType(path_suffix_items),
            model_generation=model_generation,
            revision=revision,
            authoritative=authoritative,
        )
        return snapshot


def _find_lora_in_snapshot(
    snapshot: PromptLoraCatalogSnapshot,
    prompt_name: str,
) -> PromptLoraCatalogLookupResult:
    """Return one LoRA lookup result plus its matching branch."""

    normalized_prompt_name = _prompt_lookup_key(prompt_name)
    normalized_backend_value = _backend_lookup_key(_with_known_extension(prompt_name))
    item = snapshot.prompt_name_items.get(normalized_prompt_name)
    if item is not None:
        return PromptLoraCatalogLookupResult(match_source="prompt_name", item=item)
    item = snapshot.backend_value_items.get(normalized_backend_value)
    if item is not None:
        return PromptLoraCatalogLookupResult(match_source="backend_value", item=item)
    item = snapshot.backend_prompt_items.get(normalized_prompt_name)
    if item is not None:
        return PromptLoraCatalogLookupResult(match_source="backend_prompt", item=item)

    fallback = _autocomplete_ranked_fallback(snapshot, prompt_name)
    if fallback.item is not None:
        return fallback

    bare_name_matches = snapshot.collision_items.get(
        _collision_key_for_value(prompt_name),
        (),
    )
    bare_name_match_count = len(bare_name_matches)
    if len(bare_name_matches) == 1:
        return PromptLoraCatalogLookupResult(
            match_source="autocomplete_ranked_basename",
            bare_collision_match_count=bare_name_match_count,
            fallback_candidate_count=bare_name_match_count,
            selected_fallback_rank=0,
            item=bare_name_matches[0],
        )
    if len(bare_name_matches) > 1:
        ranked_matches = ranked_lora_matches_for_query(
            _basename_without_extension(prompt_name),
            bare_name_matches,
        )
        if ranked_matches:
            return PromptLoraCatalogLookupResult(
                match_source=f"autocomplete_ranked_{ranked_matches[0].match_kind}",
                bare_collision_match_count=bare_name_match_count,
                fallback_candidate_count=len(ranked_matches),
                selected_fallback_rank=0,
                item=ranked_matches[0].item,
            )
        return PromptLoraCatalogLookupResult(
            match_source="miss",
            bare_collision_match_count=bare_name_match_count,
        )
    return PromptLoraCatalogLookupResult(
        match_source="miss",
        bare_collision_match_count=bare_name_match_count,
    )


def _autocomplete_ranked_fallback(
    snapshot: PromptLoraCatalogSnapshot,
    prompt_name: str,
) -> PromptLoraCatalogLookupResult:
    """Return an autocomplete-equivalent fallback lookup result."""

    normalized_prompt_name = _prompt_lookup_key(prompt_name)
    exact_candidates = snapshot.autocomplete_exact_items.get(normalized_prompt_name, ())
    if exact_candidates:
        return _fallback_result(
            match_source="autocomplete_ranked_exact",
            items=exact_candidates,
        )
    path_candidates = snapshot.path_suffix_items.get(normalized_prompt_name, ())
    if path_candidates:
        return _fallback_result(
            match_source="autocomplete_ranked_path",
            items=path_candidates,
        )
    basename_key = normalize_lora_query(_basename_without_extension(prompt_name))
    basename_candidates = snapshot.autocomplete_exact_items.get(basename_key, ())
    if basename_candidates:
        return _fallback_result(
            match_source="autocomplete_ranked_basename",
            items=basename_candidates,
        )
    return PromptLoraCatalogLookupResult(match_source="miss")


def _fallback_result(
    *,
    match_source: str,
    items: tuple[PromptLoraCatalogItem, ...],
) -> PromptLoraCatalogLookupResult:
    """Return the first-ranked autocomplete-equivalent fallback item."""

    return PromptLoraCatalogLookupResult(
        match_source=match_source,
        bare_collision_match_count=len(items),
        fallback_candidate_count=len(items),
        selected_fallback_rank=0,
        item=items[0],
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


def _autocomplete_exact_keys(item: PromptLoraCatalogItem) -> frozenset[str]:
    """Return exact query keys that should behave like LoRA autocomplete."""

    return frozenset(
        key
        for key in (
            normalize_lora_query(item.prompt_name),
            normalize_lora_query(strip_lora_extension(item.backend_value)),
            normalize_lora_query(item.display_name),
            normalize_lora_query(item.basename),
        )
        if key
    )


def _path_suffix_keys(item: PromptLoraCatalogItem) -> frozenset[str]:
    """Return normalized path suffix keys for stale restored path repair."""

    keys: set[str] = set()
    for value in (item.prompt_name, strip_lora_extension(item.backend_value)):
        normalized = _prompt_lookup_key(value)
        parts = tuple(part for part in normalized.split("/") if part)
        for index in range(1, len(parts)):
            keys.add("/".join(parts[index:]))
    return frozenset(keys)


def _ranked_items_for_query(
    query_text: str,
    items: tuple[PromptLoraCatalogItem, ...],
) -> tuple[PromptLoraCatalogItem, ...]:
    """Return items ordered by the same key as LoRA autocomplete."""

    ranked = ranked_lora_matches_for_query(query_text, items)
    if ranked:
        return tuple(match.item for match in ranked)
    return tuple(
        sorted(
            items,
            key=lambda item: (
                (item.display_name or item.basename).casefold(),
                item.relative_path.casefold(),
            ),
        )
    )


def _prompt_name_for_backend_value(value: str) -> str:
    """Return the scheduler-safe prompt name for one backend LoRA value."""

    return _strip_supported_extension(value)


def _thumbnail_variants_for_model(
    model: ModelCatalogItem,
) -> tuple[PromptLoraThumbnailVariant, ...]:
    """Return LoRA thumbnail references adapted from generic model variants."""

    return tuple(
        _thumbnail_variant_for_model_variant(variant)
        for variant in model.thumbnail_variants
    )


def _thumbnail_variant_for_model_variant(
    variant: ModelThumbnailVariant,
) -> PromptLoraThumbnailVariant:
    """Return a LoRA thumbnail variant from a generic model variant."""

    return PromptLoraThumbnailVariant(
        size=variant.size,
        storage_key=variant.storage_key,
        width=variant.width,
        height=variant.height,
        content_format=variant.content_format,
        byte_size=variant.byte_size,
        role=variant.role,
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


def _collision_key_for_value(value: str) -> str:
    """Return the collision key used to detect bare-name ambiguity."""

    return _basename_without_extension(value).casefold()


def _prompt_lookup_key(value: str) -> str:
    """Return the normalized extensionless key used for prompt LoRA lookup."""

    return _strip_supported_extension(value).replace("\\", "/").casefold()


def _backend_lookup_key(value: str) -> str:
    """Return the normalized backend-value key used for prompt LoRA lookup."""

    return value.replace("\\", "/").casefold()


def _has_path_separator(value: str) -> bool:
    """Return whether one prompt LoRA name includes an explicit folder path."""

    return "\\" in value or "/" in value


def _with_known_extension(prompt_name: str) -> str:
    """Return prompt name with the default LoRA extension when it has none."""

    if _extension_for_value(prompt_name):
        return prompt_name
    return f"{prompt_name}.safetensors"


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


__all__ = [
    "PromptLoraCatalogItem",
    "PromptLoraCatalogLookup",
    "PromptLoraCatalogLookupResult",
    "PromptLoraCatalogSnapshot",
    "PromptLoraCatalogService",
    "PromptLoraThumbnailVariant",
]
