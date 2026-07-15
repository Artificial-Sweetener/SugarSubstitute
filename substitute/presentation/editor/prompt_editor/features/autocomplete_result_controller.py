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

"""Own autocomplete result preparation and bounded result caches."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Final, Literal, Protocol

from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptAutocompleteSuggestion,
)
from substitute.application.prompt_editor import (
    filter_noop_autocomplete_suggestions,
    PromptAutocompleteQuery,
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
    PromptLoraAutocompleteService,
    PromptLoraCatalogItem,
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.application.prompt_editor.prompt_autocomplete_query_service import (
    autocomplete_replacement_text,
)

from .wildcard_controller import PromptWildcardAutocompleteQuerySnapshot

_AUTOCOMPLETE_RESULT_CACHE_LIMIT: Final[int] = 128

PromptScheduledLoraSignature = tuple[
    tuple[str, str, str, tuple[str, ...], str],
    ...,
]
PromptAutocompleteResultMode = Literal["empty", "tag", "wildcard", "scene", "lora"]
PromptAutocompleteResultStatus = Literal["ready", "empty", "error"]


class PromptAutocompleteResultSourceIdentity(Protocol):
    """Describe source identity fields used by result cache freshness."""

    @property
    def source_revision(self) -> int:
        """Return the source revision for stale result rejection."""
        ...

    @property
    def source_length(self) -> int | None:
        """Return the source length when the source owner can provide it."""
        ...


class PromptAutocompleteTriggerWordProvider(Protocol):
    """Return trigger-word autocomplete rows without owning async resolution."""

    def trigger_word_suggestions(
        self,
        prefix: str,
        prompt_text: str,
        *,
        source_text: str,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
        query_identity: Hashable | None,
    ) -> "PromptAutocompleteTriggerWordResult":
        """Return trigger-word rows and the signature that keys tag results."""


class PromptAutocompleteSceneResultProvider(Protocol):
    """Return prepared scene-title autocomplete rows."""

    def scene_autocomplete_suggestions(
        self,
        query: PromptSceneAutocompleteQuery,
        *,
        limit: int,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return scene title suggestions for one scene autocomplete query."""


class PromptAutocompleteWildcardResultProvider(Protocol):
    """Return prepared wildcard autocomplete snapshots."""

    def wildcard_autocomplete_snapshot(
        self,
        *,
        prefix: str,
        limit: int,
        source_identity: object | None = None,
        query_identity: Hashable | None = None,
        current_query_identity: Callable[[], Hashable | None] | None = None,
        refresh_current_query: Callable[[], None] | None = None,
    ) -> PromptWildcardAutocompleteQuerySnapshot:
        """Return prepared wildcard rows for one active wildcard query."""


class PromptAutocompleteLoraCatalogSnapshotProvider(Protocol):
    """Return cached LoRA catalog rows without loading or refreshing catalogs."""

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return cached LoRA rows when they are already available."""


@dataclass(frozen=True, slots=True)
class PromptAutocompleteTagContext:
    """Carry tag-context inputs prepared outside the result/cache owner."""

    source_text: str
    effective_prompt_text: str


@dataclass(frozen=True, slots=True)
class PromptAutocompleteTriggerWordResult:
    """Carry prepared trigger-word rows and the scheduled-LoRA signature."""

    suggestions: tuple[PromptAutocompleteSuggestion, ...]
    scheduled_lora_signature: PromptScheduledLoraSignature


@dataclass(frozen=True, slots=True)
class PromptAutocompleteResultCacheKey:
    """Identify one final tag autocomplete result snapshot."""

    source_revision: int | None
    source_length: int
    caret_position: int
    query_identity: tuple[str, str, int, int, int]
    source_text: str
    gateway_identity: Hashable
    scheduled_lora_signature: PromptScheduledLoraSignature
    limit: int


@dataclass(frozen=True, slots=True)
class PromptAutocompleteTagResult:
    """Store final tag matches and whether the raw query produced candidates."""

    matches: tuple[PromptAutocompleteSuggestion, ...]
    had_candidates: bool


@dataclass(frozen=True, slots=True)
class PromptAutocompleteResultSnapshot:
    """Describe prepared autocomplete result state before presentation consumes it."""

    mode: PromptAutocompleteResultMode
    status: PromptAutocompleteResultStatus
    source_identity: PromptAutocompleteResultSourceIdentity | None = None
    query_identity: Hashable | None = None
    cache_key: PromptAutocompleteResultCacheKey | None = None
    suggestions: tuple[PromptAutocompleteSuggestion, ...] = ()
    lora_candidates: tuple[PromptLoraAutocompleteCandidate, ...] = ()
    tag_query: PromptAutocompleteQuery | None = None
    lora_query: PromptLoraAutocompleteQuery | None = None
    wildcard_query: PromptWildcardAutocompleteQuery | None = None
    scene_query: PromptSceneAutocompleteQuery | None = None
    word_start: int | None = None
    word_end: int | None = None
    active_tag_end: int | None = None
    prefix: str = ""
    had_candidates: bool = False
    error_reason: str | None = None

    @classmethod
    def empty(
        cls,
        mode: PromptAutocompleteResultMode = "empty",
        *,
        source_identity: PromptAutocompleteResultSourceIdentity | None = None,
        query_identity: Hashable | None = None,
    ) -> "PromptAutocompleteResultSnapshot":
        """Create an empty prepared autocomplete result."""

        return cls(
            mode=mode,
            status="empty",
            source_identity=source_identity,
            query_identity=query_identity,
        )

    @classmethod
    def error(
        cls,
        mode: PromptAutocompleteResultMode,
        *,
        source_identity: PromptAutocompleteResultSourceIdentity | None = None,
        query_identity: Hashable | None = None,
        error_reason: str,
    ) -> "PromptAutocompleteResultSnapshot":
        """Create a prepared autocomplete error result that clears presentation."""

        return cls(
            mode=mode,
            status="error",
            source_identity=source_identity,
            query_identity=query_identity,
            error_reason=error_reason,
        )


class PromptAutocompleteResultController:
    """Prepare autocomplete result snapshots and own bounded result caches."""

    def __init__(
        self,
        *,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        limit: int,
        scene_feature: PromptAutocompleteSceneResultProvider | None = None,
        wildcard_feature: PromptAutocompleteWildcardResultProvider | None = None,
        prompt_lora_catalog_service: (
            PromptAutocompleteLoraCatalogSnapshotProvider | None
        ) = None,
        lora_autocomplete_service: PromptLoraAutocompleteService | None = None,
        trigger_word_provider: PromptAutocompleteTriggerWordProvider | None = None,
    ) -> None:
        """Store lookup collaborators without owning presentation or source edits."""

        self._prompt_autocomplete_gateway = prompt_autocomplete_gateway
        self._limit = limit
        self._scene_feature = scene_feature
        self._wildcard_feature = wildcard_feature
        self._prompt_lora_catalog_service = prompt_lora_catalog_service
        self._lora_autocomplete_service = (
            lora_autocomplete_service or PromptLoraAutocompleteService()
        )
        self._trigger_word_provider = trigger_word_provider
        self._autocomplete_result_cache: OrderedDict[
            PromptAutocompleteResultCacheKey,
            PromptAutocompleteTagResult,
        ] = OrderedDict()

    @property
    def cached_tag_result_count(self) -> int:
        """Return the number of cached tag autocomplete results."""

        return len(self._autocomplete_result_cache)

    def cached_tag_result_keys(self) -> tuple[PromptAutocompleteResultCacheKey, ...]:
        """Return cached tag result keys in eviction order."""

        return tuple(self._autocomplete_result_cache)

    def result_for_tag_query(
        self,
        query: PromptAutocompleteQuery,
        *,
        context: PromptAutocompleteTagContext,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
    ) -> PromptAutocompleteResultSnapshot:
        """Return a tag result snapshot, retrying the current suffix when needed."""

        result, effective_query, cache_key = (
            self._tag_matches_for_query_with_suffix_fallback(
                query=query,
                context=context,
                source_identity=source_identity,
            )
        )
        query_identity = self.tag_query_identity(
            query=effective_query,
            prompt_text=context.source_text,
        )
        if not result.matches:
            return PromptAutocompleteResultSnapshot.empty(
                "tag",
                source_identity=source_identity,
                query_identity=query_identity,
            )
        return PromptAutocompleteResultSnapshot(
            mode="tag",
            status="ready",
            source_identity=source_identity,
            query_identity=query_identity,
            cache_key=cache_key,
            suggestions=result.matches,
            tag_query=effective_query,
            word_start=effective_query.word_start,
            word_end=effective_query.word_end,
            active_tag_end=effective_query.active_tag_end,
            prefix=effective_query.prefix,
            had_candidates=result.had_candidates,
        )

    def result_for_scene_query(
        self,
        query: PromptSceneAutocompleteQuery,
        *,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
    ) -> PromptAutocompleteResultSnapshot:
        """Return a scene title result snapshot from the scene feature owner."""

        query_identity = (
            "scene",
            query.prefix,
            self._feature_identity(self._scene_feature),
        )
        if self._scene_feature is None:
            return PromptAutocompleteResultSnapshot.empty(
                "scene",
                source_identity=source_identity,
                query_identity=query_identity,
            )
        matches = self._scene_feature.scene_autocomplete_suggestions(
            query,
            limit=self._limit,
        )
        if not matches:
            return PromptAutocompleteResultSnapshot.empty(
                "scene",
                source_identity=source_identity,
                query_identity=query_identity,
            )
        return PromptAutocompleteResultSnapshot(
            mode="scene",
            status="ready",
            source_identity=source_identity,
            query_identity=query_identity,
            suggestions=matches,
            scene_query=query,
            word_start=query.title_start,
            word_end=query.cursor_position,
            prefix=query.prefix,
            had_candidates=True,
        )

    def result_for_wildcard_query(
        self,
        query: PromptWildcardAutocompleteQuery,
        *,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
        current_query_identity: Callable[[], Hashable | None] | None = None,
        refresh_current_query: Callable[[], None] | None = None,
    ) -> PromptAutocompleteResultSnapshot:
        """Return a wildcard result snapshot from the wildcard feature owner."""

        query_identity = (
            "wildcard",
            query.prefix,
            self._limit,
            self._feature_identity(self._wildcard_feature),
        )
        if self._wildcard_feature is None:
            return PromptAutocompleteResultSnapshot.empty(
                "wildcard",
                source_identity=source_identity,
                query_identity=query_identity,
            )
        query_snapshot = self._wildcard_feature.wildcard_autocomplete_snapshot(
            prefix=query.prefix,
            limit=self._limit,
            source_identity=source_identity,
            query_identity=query_identity,
            current_query_identity=current_query_identity,
            refresh_current_query=refresh_current_query,
        )
        if not query_snapshot.consumable or not query_snapshot.suggestions:
            return PromptAutocompleteResultSnapshot.empty(
                "wildcard",
                source_identity=source_identity,
                query_identity=query_identity,
            )
        return PromptAutocompleteResultSnapshot(
            mode="wildcard",
            status="ready",
            source_identity=source_identity,
            query_identity=query_identity,
            suggestions=query_snapshot.suggestions,
            wildcard_query=query,
            word_start=query.opener_start,
            word_end=query.replacement_end,
            prefix=query.prefix,
            had_candidates=True,
        )

    @property
    def limit(self) -> int:
        """Return the configured autocomplete result limit."""

        return self._limit

    def wildcard_feature_identity(self) -> Hashable:
        """Return the wildcard feature identity used in query snapshots."""

        return self._feature_identity(self._wildcard_feature)

    def result_for_lora_query(
        self,
        query: PromptLoraAutocompleteQuery,
        *,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
        enabled: bool,
        thumbnail_cache_available: bool,
    ) -> PromptAutocompleteResultSnapshot:
        """Return a LoRA candidate result snapshot from cached catalog state."""

        query_identity = (
            "lora",
            query.query_text,
            self._feature_identity(self._prompt_lora_catalog_service),
        )
        if (
            not enabled
            or not thumbnail_cache_available
            or self._prompt_lora_catalog_service is None
        ):
            return PromptAutocompleteResultSnapshot.empty(
                "lora",
                source_identity=source_identity,
                query_identity=query_identity,
            )
        loras, error_reason = self._lora_catalog_items_for_autocomplete()
        if error_reason is not None:
            return PromptAutocompleteResultSnapshot.error(
                "lora",
                source_identity=source_identity,
                query_identity=query_identity,
                error_reason=error_reason,
            )
        candidates = self._lora_autocomplete_service.rank_candidates(
            query,
            loras,
        )
        if not candidates:
            return PromptAutocompleteResultSnapshot.empty(
                "lora",
                source_identity=source_identity,
                query_identity=query_identity,
            )
        return PromptAutocompleteResultSnapshot(
            mode="lora",
            status="ready",
            source_identity=source_identity,
            query_identity=query_identity,
            lora_candidates=candidates,
            lora_query=query,
            had_candidates=True,
        )

    def tag_query_identity(
        self,
        *,
        query: PromptAutocompleteQuery,
        prompt_text: str,
    ) -> tuple[str, str, int, int, int, int]:
        """Return the identity used to discard stale async tag publications."""

        return (
            prompt_text,
            query.prefix,
            query.word_start,
            query.word_end,
            query.active_tag_end,
            self._limit,
        )

    def safe_tag_query_identity(
        self,
        query: PromptAutocompleteQuery,
    ) -> tuple[str, int, int, int, int]:
        """Return a prompt-safe tag query identity for async publication checks."""

        return (
            "tag",
            query.word_start,
            query.word_end,
            query.active_tag_end,
            self._limit,
        )

    def _tag_matches_for_query_with_suffix_fallback(
        self,
        *,
        query: PromptAutocompleteQuery,
        context: PromptAutocompleteTagContext,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
    ) -> tuple[
        PromptAutocompleteTagResult,
        PromptAutocompleteQuery,
        PromptAutocompleteResultCacheKey,
    ]:
        """Return tag matches, retrying a suffix fallback after a full miss."""

        result, cache_key = self._tag_matches_for_query(
            query=query,
            context=context,
            source_identity=source_identity,
        )
        if result.matches or result.had_candidates:
            return result, query, cache_key
        suffix_query = _fallback_prompt_autocomplete_query(query)
        if suffix_query is None:
            return result, query, cache_key
        suffix_result, suffix_cache_key = self._tag_matches_for_query(
            query=suffix_query,
            context=context,
            source_identity=source_identity,
        )
        if not suffix_result.matches:
            return result, query, cache_key
        return suffix_result, suffix_query, suffix_cache_key

    def _tag_matches_for_query(
        self,
        *,
        query: PromptAutocompleteQuery,
        context: PromptAutocompleteTagContext,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
    ) -> tuple[PromptAutocompleteTagResult, PromptAutocompleteResultCacheKey]:
        """Return cached tag matches for one concrete query range."""

        trigger_word_result = self._trigger_word_result(
            query.prefix,
            context.effective_prompt_text,
            source_text=context.source_text,
            source_identity=source_identity,
            query_identity=self.safe_tag_query_identity(query),
        )
        cache_key = self._cache_key_for_tag_query(
            query=query,
            prompt_text=context.source_text,
            source_identity=source_identity,
            scheduled_lora_signature=(trigger_word_result.scheduled_lora_signature),
        )
        result = self._cached_autocomplete_result(cache_key)
        if result is None:
            result = self._autocomplete_suggestions_for_query(
                query=query,
                prompt_text=context.source_text,
                trigger_matches=trigger_word_result.suggestions,
            )
            self._cache_autocomplete_result(cache_key, result)
        return result, cache_key

    def _trigger_word_result(
        self,
        prefix: str,
        prompt_text: str,
        *,
        source_text: str,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
        query_identity: Hashable | None,
    ) -> PromptAutocompleteTriggerWordResult:
        """Return trigger-word rows without owning their async resolution path."""

        provider = self._trigger_word_provider
        if provider is None:
            return PromptAutocompleteTriggerWordResult(
                suggestions=(),
                scheduled_lora_signature=(),
            )
        return provider.trigger_word_suggestions(
            prefix,
            prompt_text,
            source_text=source_text,
            source_identity=source_identity,
            query_identity=query_identity,
        )

    def _autocomplete_suggestions_for_query(
        self,
        *,
        query: PromptAutocompleteQuery,
        prompt_text: str,
        trigger_matches: tuple[PromptAutocompleteSuggestion, ...],
    ) -> PromptAutocompleteTagResult:
        """Return merged and filtered tag autocomplete suggestions."""

        file_matches = self._prompt_autocomplete_gateway.search(
            query.prefix,
            limit=self._limit,
        )
        matches = _merge_autocomplete_suggestions(
            trigger_matches=trigger_matches,
            file_matches=file_matches,
            limit=self._limit,
        )
        had_candidates = bool(matches)
        matches = filter_noop_autocomplete_suggestions(
            text=prompt_text,
            query=query,
            suggestions=matches,
        )
        return PromptAutocompleteTagResult(
            matches=matches,
            had_candidates=had_candidates,
        )

    def _cache_key_for_tag_query(
        self,
        *,
        query: PromptAutocompleteQuery,
        prompt_text: str,
        source_identity: PromptAutocompleteResultSourceIdentity | None,
        scheduled_lora_signature: PromptScheduledLoraSignature,
    ) -> PromptAutocompleteResultCacheKey:
        """Build an explicit tag result cache key for one query snapshot."""

        return PromptAutocompleteResultCacheKey(
            source_revision=(
                None if source_identity is None else source_identity.source_revision
            ),
            source_length=(
                len(prompt_text)
                if source_identity is None or source_identity.source_length is None
                else source_identity.source_length
            ),
            caret_position=query.word_end,
            query_identity=(
                "tag",
                query.prefix,
                query.word_start,
                query.word_end,
                query.active_tag_end,
            ),
            source_text=prompt_text,
            gateway_identity=self._feature_identity(self._prompt_autocomplete_gateway),
            scheduled_lora_signature=scheduled_lora_signature,
            limit=self._limit,
        )

    def _cached_autocomplete_result(
        self,
        cache_key: PromptAutocompleteResultCacheKey,
    ) -> PromptAutocompleteTagResult | None:
        """Return a cached final autocomplete result for one exact query."""

        cached = self._autocomplete_result_cache.get(cache_key)
        if cached is not None:
            self._autocomplete_result_cache.move_to_end(cache_key)
        return cached

    def _cache_autocomplete_result(
        self,
        cache_key: PromptAutocompleteResultCacheKey,
        result: PromptAutocompleteTagResult,
    ) -> None:
        """Store one bounded final autocomplete result."""

        self._autocomplete_result_cache[cache_key] = result
        self._autocomplete_result_cache.move_to_end(cache_key)
        while len(self._autocomplete_result_cache) > _AUTOCOMPLETE_RESULT_CACHE_LIMIT:
            self._autocomplete_result_cache.popitem(last=False)

    def _lora_catalog_items_for_autocomplete(
        self,
    ) -> tuple[tuple[PromptLoraCatalogItem, ...], str | None]:
        """Return cached LoRA rows for autocomplete without backend loading."""

        catalog_service = self._prompt_lora_catalog_service
        if catalog_service is None:
            return (), None
        try:
            cached_loras = catalog_service.cached_loras()
            if cached_loras is None:
                return (), None
            return cached_loras, None
        except (OSError, RuntimeError, TypeError, ValueError):
            return (), "lora_catalog_cache_error"

    @staticmethod
    def _feature_identity(feature: object | None) -> Hashable:
        """Return a stable-enough identity token for cache and snapshot ownership."""

        if feature is None:
            return ("none", 0)
        revision = getattr(
            feature,
            "cache_revision",
            getattr(feature, "revision", getattr(feature, "version", None)),
        )
        if isinstance(revision, Hashable):
            return (type(feature).__qualname__, id(feature), revision)
        return (type(feature).__qualname__, id(feature), id(revision))


def _merge_autocomplete_suggestions(
    *,
    trigger_matches: tuple[PromptAutocompleteSuggestion, ...],
    file_matches: tuple[PromptAutocompleteSuggestion, ...],
    limit: int,
) -> tuple[PromptAutocompleteSuggestion, ...]:
    """Merge trigger and file suggestions with trigger metadata taking precedence."""

    merged: list[PromptAutocompleteSuggestion] = []
    seen_replacements: set[str] = set()
    for suggestion in trigger_matches + file_matches:
        replacement_key = _autocomplete_replacement_key(suggestion.tag)
        if replacement_key in seen_replacements:
            continue
        seen_replacements.add(replacement_key)
        merged.append(suggestion)
        if len(merged) >= limit:
            break
    return tuple(merged)


def _autocomplete_replacement_key(tag: str) -> str:
    """Return the normalized replacement key used for suggestion deduplication."""

    return (
        autocomplete_replacement_text(tag)
        .replace("\\(", "(")
        .replace("\\)", ")")
        .replace("_", " ")
        .casefold()
        .strip()
    )


def _fallback_prompt_autocomplete_query(
    query: PromptAutocompleteQuery,
) -> PromptAutocompleteQuery | None:
    """Promote an application-owned fallback query for a missed primary query."""

    fallback_query = query.fallback_query
    if fallback_query is None:
        return None
    return PromptAutocompleteQuery(
        prefix=fallback_query.prefix,
        word_start=fallback_query.word_start,
        word_end=fallback_query.word_end,
        active_tag_end=fallback_query.active_tag_end,
    )


__all__ = [
    "PromptAutocompleteLoraCatalogSnapshotProvider",
    "PromptAutocompleteResultCacheKey",
    "PromptAutocompleteResultController",
    "PromptAutocompleteResultMode",
    "PromptAutocompleteResultSnapshot",
    "PromptAutocompleteResultSourceIdentity",
    "PromptAutocompleteResultStatus",
    "PromptAutocompleteSceneResultProvider",
    "PromptScheduledLoraSignature",
    "PromptAutocompleteTagContext",
    "PromptAutocompleteTagResult",
    "PromptAutocompleteTriggerWordProvider",
    "PromptAutocompleteTriggerWordResult",
    "PromptAutocompleteWildcardResultProvider",
]
