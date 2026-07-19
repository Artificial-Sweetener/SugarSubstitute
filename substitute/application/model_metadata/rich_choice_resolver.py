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

"""Resolve Comfy LIST values into model-enriched picker choices."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from threading import RLock

from substitute.application.model_metadata.model_catalog_service import ModelCatalogItem
from substitute.application.model_metadata.model_choice_catalog_index import (
    ModelChoiceCatalogIndex,
)
from substitute.application.model_metadata.rich_choice_models import (
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.model_metadata.rich_choice_resolver")
_MIN_ENRICHED_OPTIONS = 2
_MIN_ENRICHED_RATIO = 0.50
_SUPPORTED_MODEL_EXTENSIONS = frozenset({".safetensors", ".ckpt", ".pt"})


@dataclass(frozen=True, slots=True)
class RichChoiceContext:
    """Carry diagnostic identity for one LIST field classification."""

    node_class: str | None = None
    field_key: str | None = None
    node_name: str | None = None
    model_kind: str | None = None


class ResolvedRichChoiceSource:
    """Provide cached and refreshed rich-choice resolutions for one option list."""

    def __init__(
        self,
        *,
        resolver: RichChoiceResolver,
        options: Iterable[str],
        context: RichChoiceContext | None = None,
        initial_resolution: RichChoiceResolution | None = None,
    ) -> None:
        """Store the resolver, exact Comfy options, and optional first resolution."""

        self._resolver = resolver
        self._options = tuple(options)
        self._context = context or RichChoiceContext()
        self._resolution = initial_resolution

    def current_resolution(self) -> RichChoiceResolution:
        """Return the cached resolution, computing it when needed."""

        if self._resolution is None:
            self._resolution = self._resolver.resolve(
                self._options,
                context=self._context,
            )
        return self._resolution

    def refresh(self) -> RichChoiceResolution:
        """Refresh matched model kinds and recompute this option list."""

        self._resolution = self._resolver.refresh(
            self._options,
            context=self._context,
            previous_resolution=self.current_resolution(),
        )
        return self._resolution

    def extra_item_for_value(self, value: str) -> RichChoiceItem | None:
        """Return an enriched item for a selected value absent from Comfy options."""

        return self._resolver.extra_item_for_value(
            value,
            previous_resolution=self.current_resolution(),
        )


class RichChoiceResolver:
    """Classify exact Comfy LIST values against model catalog metadata."""

    def __init__(self, *, catalog_index: ModelChoiceCatalogIndex) -> None:
        """Store the catalog index used for exact-value enrichment."""

        self._catalog_index = catalog_index
        self._cache: dict[
            tuple[tuple[str, ...], int, tuple[str, ...]], RichChoiceResolution
        ] = {}
        self._lock = RLock()

    @property
    def enabled_kinds(self) -> tuple[str, ...]:
        """Return the model kinds this resolver can enrich."""

        return self._catalog_index.enabled_kinds

    def source_for_options(
        self,
        options: Iterable[str],
        *,
        context: RichChoiceContext | None = None,
        initial_resolution: RichChoiceResolution | None = None,
    ) -> ResolvedRichChoiceSource:
        """Return a reusable source object for one exact Comfy option list."""

        return ResolvedRichChoiceSource(
            resolver=self,
            options=tuple(options),
            context=context,
            initial_resolution=initial_resolution,
        )

    def resolve(
        self,
        options: Iterable[str],
        *,
        context: RichChoiceContext | None = None,
    ) -> RichChoiceResolution:
        """Resolve exact Comfy options into picker choices and a render decision."""

        exact_options = tuple(str(option) for option in options)
        cache_key = (
            exact_options,
            self._catalog_index.generation,
            self._catalog_index.enabled_kinds,
        )
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                log_debug(
                    _LOGGER,
                    "Rich model choice resolution cache hit",
                    node_class=(context or RichChoiceContext()).node_class,
                    node_name=(context or RichChoiceContext()).node_name,
                    field_key=(context or RichChoiceContext()).field_key,
                    option_count=len(exact_options),
                    catalog_generation=self._catalog_index.generation,
                    enabled_kinds=self._catalog_index.enabled_kinds,
                    cached_resolution_count=len(self._cache),
                )
                return cached

        resolution = self._resolve_uncached(exact_options)
        with self._lock:
            self._cache[cache_key] = resolution
            cached_resolution_count = len(self._cache)
        log_debug(
            _LOGGER,
            "Rich model choice resolution cache miss",
            node_class=(context or RichChoiceContext()).node_class,
            node_name=(context or RichChoiceContext()).node_name,
            field_key=(context or RichChoiceContext()).field_key,
            option_count=len(exact_options),
            catalog_generation=self._catalog_index.generation,
            enabled_kinds=self._catalog_index.enabled_kinds,
            cached_resolution_count=cached_resolution_count,
        )
        self._log_resolution(resolution, context or RichChoiceContext())
        return resolution

    def resolve_prepared(
        self,
        options: Iterable[str],
        *,
        catalog_items: Iterable[ModelCatalogItem],
        context: RichChoiceContext | None = None,
    ) -> RichChoiceResolution:
        """Resolve exact Comfy options against an already-prepared catalog snapshot."""

        exact_options = tuple(str(option) for option in options)
        items_by_value: defaultdict[str, list[ModelCatalogItem]] = defaultdict(list)
        for item in catalog_items:
            items_by_value[item.backend_value].append(item)
        candidate_groups = tuple(
            tuple(items_by_value.get(option, ())) for option in exact_options
        )
        resolution = _resolution_for_candidate_groups(
            exact_options,
            candidate_groups,
        )
        self._log_resolution(resolution, context or RichChoiceContext())
        return resolution

    def prewarm(self, option_lists: Iterable[Iterable[str]] = ()) -> int:
        """Warm model choice indexes and optional exact rich-choice resolutions."""

        self._catalog_index.prewarm()
        warmed_count = 0
        for options in option_lists:
            self.resolve(options)
            warmed_count += 1
        return warmed_count

    def cached_resolution_count(self) -> int:
        """Return the number of exact option-list resolutions cached."""

        with self._lock:
            return len(self._cache)

    def refresh(
        self,
        options: Iterable[str],
        *,
        context: RichChoiceContext | None = None,
        previous_resolution: RichChoiceResolution | None = None,
    ) -> RichChoiceResolution:
        """Refresh matched kinds and resolve the options against the new generation."""

        resolved_context = context or RichChoiceContext()
        refresh_kinds = _refresh_kinds_for_resolution(
            previous_resolution,
            resolved_context,
        )
        if refresh_kinds:
            try:
                self._catalog_index.refresh_kinds(refresh_kinds)
            except Exception as error:
                return _unavailable_resolution(
                    options=tuple(str(option) for option in options),
                    matched_kinds=refresh_kinds,
                    reason=(
                        "model selection unavailable: backend model catalog "
                        f"refresh failed ({type(error).__name__})"
                    ),
                )
        return self.resolve(options, context=resolved_context)

    def invalidate(self, kinds: Iterable[str] | str | None = None) -> None:
        """Clear cached rich-choice resolutions after model catalog data changes."""

        if isinstance(kinds, str):
            normalized_kinds: tuple[str, ...] | None = (kinds,)
        elif kinds is None:
            normalized_kinds = None
        else:
            normalized_kinds = tuple(kinds)
        self._catalog_index.invalidate(normalized_kinds)
        with self._lock:
            self._cache.clear()

    def extra_item_for_value(
        self,
        value: str,
        *,
        previous_resolution: RichChoiceResolution | None = None,
    ) -> RichChoiceItem | None:
        """Return an enriched choice for a current value missing from Comfy choices."""

        if not value:
            return None
        if previous_resolution is not None and previous_resolution.matched_kinds:
            self._catalog_index.refresh_kinds(previous_resolution.matched_kinds)
        candidate = _select_candidate(
            self._catalog_index.candidates_for_value(value),
            _dominant_kind_for_resolution(previous_resolution),
        )
        if candidate is None:
            return None
        return _enriched_choice_item(value=value, item=candidate)

    def _resolve_uncached(
        self,
        options: tuple[str, ...],
    ) -> RichChoiceResolution:
        """Build one rich-choice resolution without consulting the resolution cache."""

        candidate_groups = tuple(
            self._catalog_index.candidates_for_value(option) for option in options
        )
        return _resolution_for_candidate_groups(options, candidate_groups)

    def _log_resolution(
        self,
        resolution: RichChoiceResolution,
        context: RichChoiceContext,
    ) -> None:
        """Log one rich-choice classification decision with actionable context."""

        log_debug(
            _LOGGER,
            "Resolved rich model choice list",
            node_class=context.node_class,
            node_name=context.node_name,
            field_key=context.field_key,
            option_count=resolution.option_count,
            enriched_count=resolution.enriched_count,
            unmatched_count=resolution.unmatched_count,
            ambiguous_count=resolution.ambiguous_count,
            matched_kinds=resolution.matched_kinds,
            use_rich_picker=resolution.should_use_rich_picker,
            reason=resolution.reason,
            unavailable_reason=resolution.unavailable_reason,
        )


def _choice_item_for_option(
    *,
    value: str,
    candidates: tuple[ModelCatalogItem, ...],
    dominant_kind: str | None,
) -> RichChoiceItem:
    """Return one choice item from exact candidates and the dominant list kind."""

    candidate = _select_candidate(candidates, dominant_kind)
    if candidate is not None:
        return _enriched_choice_item(value=value, item=candidate)
    is_ambiguous = bool(candidates)
    title = _fallback_title(value)
    return RichChoiceItem(
        value=value,
        title=title,
        subtitle=None,
        search_text=_fallback_search_text(value=value, title=title),
        model_kind=None,
        catalog_item=None,
        thumbnail_variants=(),
        is_enriched=False,
        is_ambiguous=is_ambiguous,
    )


def _resolution_for_candidate_groups(
    options: tuple[str, ...],
    candidate_groups: tuple[tuple[ModelCatalogItem, ...], ...],
) -> RichChoiceResolution:
    """Return a picker decision from exact option-to-catalog candidate groups."""

    dominant_kind = _dominant_kind(candidate_groups, option_count=len(options))
    items = tuple(
        _choice_item_for_option(
            value=option,
            candidates=candidates,
            dominant_kind=dominant_kind,
        )
        for option, candidates in zip(options, candidate_groups, strict=True)
    )
    enriched_count = sum(1 for item in items if item.is_enriched)
    ambiguous_count = sum(1 for item in items if item.is_ambiguous)
    unmatched_count = len(items) - enriched_count - ambiguous_count
    matched_kinds = tuple(
        sorted({item.model_kind for item in items if item.model_kind is not None})
    )
    should_use, reason = _render_decision(
        option_count=len(items),
        enriched_count=enriched_count,
        ambiguous_count=ambiguous_count,
    )
    if should_use and len(matched_kinds) != 1:
        should_use = False
        reason = "model choices do not resolve to one catalog kind"
    return RichChoiceResolution(
        items=items,
        should_use_rich_picker=should_use,
        matched_kinds=matched_kinds,
        option_count=len(items),
        enriched_count=enriched_count,
        ambiguous_count=ambiguous_count,
        unmatched_count=unmatched_count,
        reason=reason,
    )


def _enriched_choice_item(*, value: str, item: ModelCatalogItem) -> RichChoiceItem:
    """Return one metadata-backed rich choice item."""

    return RichChoiceItem(
        value=value,
        title=item.display_name or item.basename,
        subtitle=item.display_subtitle,
        search_text=item.search_text,
        model_kind=item.kind,
        catalog_item=item,
        thumbnail_variants=item.thumbnail_variants,
        is_enriched=True,
        is_ambiguous=False,
    )


def _select_candidate(
    candidates: tuple[ModelCatalogItem, ...],
    dominant_kind: str | None,
) -> ModelCatalogItem | None:
    """Return the safe enrichment candidate for one exact Comfy choice."""

    if len(candidates) == 1:
        return candidates[0]
    if dominant_kind is None:
        return None
    dominant_candidates = tuple(
        candidate for candidate in candidates if candidate.kind == dominant_kind
    )
    if len(dominant_candidates) == 1:
        return dominant_candidates[0]
    return None


def _dominant_kind(
    candidate_groups: tuple[tuple[ModelCatalogItem, ...], ...],
    *,
    option_count: int,
) -> str | None:
    """Return a list-dominant model kind used to resolve exact-value ambiguity."""

    counts: Counter[str] = Counter()
    for candidates in candidate_groups:
        if len(candidates) == 1:
            counts[candidates[0].kind] += 1
    if not counts:
        return None
    [(kind, count)] = counts.most_common(1)
    competing_count = counts.most_common(2)[1][1] if len(counts) > 1 else 0
    if (
        count < _MIN_ENRICHED_OPTIONS
        or count / max(1, option_count) < _MIN_ENRICHED_RATIO
    ):
        return None
    if competing_count >= count:
        return None
    return kind


def _dominant_kind_for_resolution(
    resolution: RichChoiceResolution | None,
) -> str | None:
    """Return the only matched kind from a previous picker resolution."""

    if resolution is None or len(resolution.matched_kinds) != 1:
        return None
    return resolution.matched_kinds[0]


def _refresh_kinds_for_resolution(
    resolution: RichChoiceResolution | None,
    context: RichChoiceContext,
) -> tuple[str, ...]:
    """Return model kinds that should be refreshed for a picker reopen."""

    if resolution is not None and resolution.matched_kinds:
        return resolution.matched_kinds
    if context.model_kind:
        return (context.model_kind,)
    return ()


def _unavailable_resolution(
    *,
    options: tuple[str, ...],
    matched_kinds: tuple[str, ...],
    reason: str,
) -> RichChoiceResolution:
    """Return a rich-choice resolution for unavailable Backend model selection."""

    return RichChoiceResolution(
        items=(),
        should_use_rich_picker=True,
        matched_kinds=matched_kinds,
        option_count=len(options),
        enriched_count=0,
        ambiguous_count=0,
        unmatched_count=0,
        reason=reason,
        unavailable_reason=reason,
    )


def _render_decision(
    *,
    option_count: int,
    enriched_count: int,
    ambiguous_count: int,
) -> tuple[bool, str]:
    """Return whether a rich picker should be used and why."""

    if option_count <= 0:
        return False, "empty option list"
    if enriched_count < _MIN_ENRICHED_OPTIONS:
        return False, "too few enriched choices"
    enriched_ratio = enriched_count / option_count
    if enriched_ratio < _MIN_ENRICHED_RATIO:
        return False, "enriched choice ratio below threshold"
    if enriched_count <= ambiguous_count:
        return False, "ambiguous choices dominate enrichment"
    return True, "model metadata enriches enough Comfy choices"


def _fallback_title(value: str) -> str:
    """Return a conservative display title for an unenriched Comfy choice."""

    stripped_value = value.strip()
    if not stripped_value:
        return ""
    normalized_value = stripped_value.replace("\\", "/")
    name = PurePosixPath(normalized_value).name
    return _strip_supported_extension(name) or stripped_value


def _fallback_search_text(*, value: str, title: str) -> str:
    """Return normalized search text for a choice without model metadata."""

    return " ".join((value, title)).replace("\\", "/").casefold()


def _strip_supported_extension(value: str) -> str:
    """Strip the final supported model extension from a value when present."""

    extension = _extension_for_value(value)
    if extension in _SUPPORTED_MODEL_EXTENSIONS:
        return value[: -len(extension)]
    return value


def _extension_for_value(value: str) -> str:
    """Return the final extension for a Comfy choice value."""

    windows_suffix = PureWindowsPath(value).suffix
    posix_suffix = PurePosixPath(value).suffix
    return (windows_suffix or posix_suffix).lower()


__all__ = [
    "ResolvedRichChoiceSource",
    "RichChoiceContext",
    "RichChoiceResolver",
]
