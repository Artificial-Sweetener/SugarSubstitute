#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Load active-only core and custom node translations from a Comfy server."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Any, BinaryIO, cast

import ijson  # type: ignore[import-untyped]

from substitute.application.localization import ActiveComfyNodeCatalogStore
from substitute.domain.localization import NodeTextCatalog, NodeTextSource
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.external.http_transport import (
    default_http_get,
    is_request_exception,
)
from substitute.infrastructure.localization.comfy_i18n_cache import (
    CachedComfyI18nBranches,
    ComfyI18nCache,
)
from substitute.infrastructure.localization.node_catalog_parser import (
    NodeTextCatalogParser,
)
from substitute.shared.logging.logger import get_logger, log_timing

_LOGGER = get_logger("infrastructure.localization.comfy_i18n_client")
_MAX_RESPONSE_BYTES = 32 * 1024 * 1024

HttpGet = Callable[..., Any]
BackgroundScheduler = Callable[[Callable[[], None]], object]
CatalogPublished = Callable[[], None]
FrontendNodeDefinitionsLoader = Callable[
    [tuple[str, ...]], dict[str, dict[str, object]]
]


@dataclass(frozen=True, slots=True)
class ComfyI18nLanguageSelection:
    """Describe the active app language and ordered Comfy locale aliases."""

    effective_language_identifier: str
    comfy_aliases: tuple[str, ...]


class ComfyI18nCatalogClient:
    """Publish bounded English-plus-active Comfy node catalogs off the GUI thread."""

    def __init__(
        self,
        *,
        endpoint: ComfyEndpoint,
        cache_root: Path,
        language_selection: Callable[[], ComfyI18nLanguageSelection],
        store: ActiveComfyNodeCatalogStore,
        background_scheduler: BackgroundScheduler,
        catalog_published: CatalogPublished | None = None,
        http_get: HttpGet | None = None,
        frontend_node_definitions_loader: FrontendNodeDefinitionsLoader | None = None,
    ) -> None:
        """Store transport, selection, cache, and publication collaborators."""

        self._endpoint = endpoint
        self._language_selection = language_selection
        self._store = store
        self._background_scheduler = background_scheduler
        self._catalog_published = catalog_published or (lambda: None)
        self._http_get = http_get or default_http_get
        self._frontend_node_definitions_loader = frontend_node_definitions_loader
        self._cache = ComfyI18nCache(cache_root, endpoint)
        self._parser = NodeTextCatalogParser()
        self._lock = RLock()
        self._refresh_inflight = False
        self._inflight_selection: ComfyI18nLanguageSelection | None = None
        self._refresh_pending = False
        self._target_fingerprint = sha256(
            f"{endpoint.host.casefold()}:{endpoint.port}".encode("utf-8")
        ).hexdigest()[:12]

    def load_cached_selection(self) -> bool:
        """Publish a matching active-only disk cache before network refresh."""

        selection = self._language_selection()
        active_alias = _primary_alias(selection)
        cached = self._cache.load(active_alias=active_alias)
        if cached is None:
            self._store.clear_for_language(selection.effective_language_identifier)
            return False
        self._publish_raw_branches(selection, cached)
        return True

    def refresh_async(self) -> bool:
        """Queue one network refresh when another generation is not in flight."""

        selection = self._language_selection()
        with self._lock:
            if self._refresh_inflight:
                if selection != self._inflight_selection:
                    self._refresh_pending = True
                return False
            self._refresh_inflight = True
            self._inflight_selection = selection
        try:
            self._background_scheduler(self._refresh_in_background)
        except Exception:
            with self._lock:
                self._refresh_inflight = False
                self._inflight_selection = None
            raise
        return True

    def select_language_and_refresh(self) -> bool:
        """Drop the obsolete active generation, load cache, and queue refresh."""

        selection = self._language_selection()
        self._store.clear_for_language(selection.effective_language_identifier)
        self.load_cached_selection()
        return self.refresh_async()

    def refresh(self) -> bool:
        """Merge available live Comfy sources and publish one active generation."""

        started_at = perf_counter()
        selection = self._language_selection()
        ordered_aliases = _unique_aliases((*selection.comfy_aliases, "en"))
        custom_branches, custom_loaded = self._load_custom_branches(
            selection,
            frozenset(ordered_aliases),
        )
        frontend_branches, frontend_loaded = self._load_frontend_branches(
            selection,
            ordered_aliases,
        )
        if not custom_loaded and not frontend_loaded:
            log_timing(
                _LOGGER,
                "Comfy node localization refresh found no available source",
                started_at=started_at,
                level="warning",
                target_fingerprint=self._target_fingerprint,
                effective_language=selection.effective_language_identifier,
            )
            return False
        if self._language_selection() != selection:
            return False

        branches = _merge_locale_branches(frontend_branches, custom_branches)
        active_alias = _primary_alias(selection)
        active_node_definitions = _merge_alias_branches(
            branches,
            selection.comfy_aliases,
        )
        cached = CachedComfyI18nBranches(
            active_alias=active_alias,
            active_node_definitions=active_node_definitions,
            english_node_definitions=(
                None if active_alias == "en" else branches.get("en", {})
            ),
        )
        try:
            self._publish_raw_branches(selection, cached)
            self._save_cache(cached)
            log_timing(
                _LOGGER,
                "Published Comfy node localization",
                started_at=started_at,
                target_fingerprint=self._target_fingerprint,
                effective_language=selection.effective_language_identifier,
                active_alias=active_alias,
                active_node_count=len(cached.active_node_definitions),
                english_node_count=len(cached.english_node_definitions or {}),
                custom_source_loaded=custom_loaded,
                frontend_source_loaded=frontend_loaded,
            )
            return True
        except Exception as error:
            if not _is_expected_catalog_error(error):
                raise
            log_timing(
                _LOGGER,
                "Comfy node localization publication failed",
                started_at=started_at,
                level="warning",
                target_fingerprint=self._target_fingerprint,
                effective_language=selection.effective_language_identifier,
                error=repr(error),
            )
            return False

    def _load_custom_branches(
        self,
        selection: ComfyI18nLanguageSelection,
        desired_aliases: frozenset[str],
    ) -> tuple[dict[str, dict[str, object]], bool]:
        """Load custom-node `/i18n` branches without coupling core availability."""

        response: Any | None = None
        try:
            response = self._http_get(
                self._endpoint.i18n_url(),
                timeout=5,
                stream=True,
            )
            response.raise_for_status()
            _validate_content_length(response)
            return (
                _stream_selected_node_definitions(
                    cast(BinaryIO, response.raw),
                    desired_aliases=desired_aliases,
                ),
                True,
            )
        except Exception as error:
            if not _is_expected_catalog_error(error):
                raise
            _LOGGER.warning(
                "Custom Comfy node localization source unavailable",
                extra={
                    "target_fingerprint": self._target_fingerprint,
                    "effective_language": selection.effective_language_identifier,
                    "error": repr(error),
                },
            )
            return {}, False
        finally:
            if response is not None:
                response.close()

    def _load_frontend_branches(
        self,
        selection: ComfyI18nLanguageSelection,
        aliases: tuple[str, ...],
    ) -> tuple[dict[str, dict[str, object]], bool]:
        """Load official core locale assets independently of custom-node `/i18n`."""

        loader = self._frontend_node_definitions_loader
        if loader is None:
            return {}, False
        try:
            return loader(aliases), True
        except Exception as error:
            if not _is_expected_catalog_error(error):
                raise
            _LOGGER.warning(
                "Official Comfy frontend node localization source unavailable",
                extra={
                    "target_fingerprint": self._target_fingerprint,
                    "effective_language": selection.effective_language_identifier,
                    "error": repr(error),
                },
            )
            return {}, False

    def _save_cache(self, cached: CachedComfyI18nBranches) -> None:
        """Persist a published generation without making disk cache authoritative."""

        try:
            self._cache.save(
                active_alias=cached.active_alias,
                active_node_definitions=cached.active_node_definitions,
                english_node_definitions=cached.english_node_definitions,
            )
        except (OSError, ValueError) as error:
            _LOGGER.warning(
                "Comfy node localization cache write failed",
                extra={
                    "target_fingerprint": self._target_fingerprint,
                    "active_alias": cached.active_alias,
                    "error": repr(error),
                },
            )

    def _refresh_in_background(self) -> None:
        """Refresh one generation and release the scheduling guard."""

        schedule_pending = False
        try:
            self.refresh()
        finally:
            with self._lock:
                self._refresh_inflight = False
                self._inflight_selection = None
                schedule_pending = self._refresh_pending
                self._refresh_pending = False
        if schedule_pending:
            self.refresh_async()

    def _publish_raw_branches(
        self,
        selection: ComfyI18nLanguageSelection,
        cached: CachedComfyI18nBranches,
    ) -> None:
        """Parse selected raw branches and atomically replace the store generation."""

        active_catalog = self._parse_custom_catalog(
            cached.active_node_definitions,
            language_identifier=selection.effective_language_identifier,
            source=NodeTextSource.ACTIVE_COMFY,
            source_label=f"remote:{cached.active_alias}",
        )
        english_catalog: NodeTextCatalog | None = None
        if cached.english_node_definitions is not None:
            english_catalog = self._parse_custom_catalog(
                cached.english_node_definitions,
                language_identifier="en",
                source=NodeTextSource.ENGLISH_COMFY,
                source_label="remote:en",
            )
        self._store.publish(
            effective_language_identifier=selection.effective_language_identifier,
            active_catalog=active_catalog,
            english_catalog=english_catalog,
        )
        self._catalog_published()

    def _parse_custom_catalog(
        self,
        node_definitions: dict[str, object],
        *,
        language_identifier: str,
        source: NodeTextSource,
        source_label: str,
    ) -> NodeTextCatalog | None:
        """Parse one branch and omit empty layers from the runtime snapshot."""

        catalog = self._parser.parse(
            node_definitions,
            language_identifier=language_identifier,
            source=source,
            source_label=source_label,
            strict=False,
        )
        return catalog if catalog.node_definitions else None


class _LimitedBinaryReader:
    """Reject streamed JSON after a fixed number of bytes has been consumed."""

    def __init__(self, raw: BinaryIO, limit: int) -> None:
        """Wrap one response stream with a monotonic byte counter."""

        self._raw = raw
        self._limit = limit
        self._consumed = 0

    def read(self, size: int = -1) -> bytes:
        """Read bytes and fail closed when the response crosses the limit."""

        chunk = self._raw.read(size)
        self._consumed += len(chunk)
        if self._consumed > self._limit:
            raise ValueError(
                "Custom Comfy localization response exceeds the size limit."
            )
        return chunk


def _stream_selected_node_definitions(
    raw: BinaryIO,
    *,
    desired_aliases: frozenset[str],
) -> dict[str, dict[str, object]]:
    """Parse top-level locale branches incrementally and discard unselected locales."""

    selected: dict[str, dict[str, object]] = {}
    reader = _LimitedBinaryReader(raw, _MAX_RESPONSE_BYTES)
    for alias, raw_branch in ijson.kvitems(reader, ""):
        if alias not in desired_aliases or not isinstance(raw_branch, Mapping):
            continue
        raw_node_definitions = raw_branch.get("nodeDefs")
        if isinstance(raw_node_definitions, dict):
            selected[alias] = cast(dict[str, object], raw_node_definitions)
    return selected


def _merge_locale_branches(
    base: dict[str, dict[str, object]],
    overlays: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    """Merge custom node locale branches over official core branches."""

    aliases = base.keys() | overlays.keys()
    return {
        alias: _merge_mapping_tree(base.get(alias, {}), overlays.get(alias, {}))
        for alias in aliases
    }


def _merge_alias_branches(
    branches: dict[str, dict[str, object]],
    aliases: tuple[str, ...],
) -> dict[str, object]:
    """Collapse ordered aliases so primary locale values override fallbacks."""

    merged: dict[str, object] = {}
    for alias in reversed(aliases):
        merged = _merge_mapping_tree(merged, branches.get(alias, {}))
    return merged


def _merge_mapping_tree(
    base: Mapping[str, object],
    overlay: Mapping[str, object],
) -> dict[str, object]:
    """Return a recursive mapping merge matching Comfy frontend semantics."""

    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_mapping_tree(existing, value)
        else:
            merged[key] = value
    return merged


def _validate_content_length(response: Any) -> None:
    """Reject an advertised response size before parsing begins."""

    raw_length = response.headers.get("Content-Length")
    if raw_length is None:
        return
    try:
        content_length = int(raw_length)
    except (TypeError, ValueError) as error:
        raise ValueError("Invalid custom Comfy localization content length.") from error
    if content_length <= 0 or content_length > _MAX_RESPONSE_BYTES:
        raise ValueError("Custom Comfy localization content length is out of bounds.")


def _primary_alias(selection: ComfyI18nLanguageSelection) -> str:
    """Return the first configured Comfy alias or fail composition explicitly."""

    if not selection.comfy_aliases:
        raise ValueError("The active language has no Comfy localization alias.")
    return selection.comfy_aliases[0]


def _unique_aliases(aliases: tuple[str, ...]) -> tuple[str, ...]:
    """Preserve alias priority while removing duplicate locale requests."""

    return tuple(dict.fromkeys(aliases))


def _is_expected_catalog_error(error: BaseException) -> bool:
    """Return whether a remote/cache catalog failure should preserve fallback layers."""

    return isinstance(
        error,
        OSError | TypeError | ValueError | ijson.JSONError,
    ) or is_request_exception(error)


__all__ = ["ComfyI18nCatalogClient", "ComfyI18nLanguageSelection"]
