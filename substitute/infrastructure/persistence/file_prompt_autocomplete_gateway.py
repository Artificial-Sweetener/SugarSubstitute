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

"""Load bundled prompt autocomplete suggestions from the persistence asset package."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from threading import RLock

from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptAutocompleteSuggestion,
    PromptTagLexicon,
)
from substitute.application.ports.prompt_tag_lexicon import PromptTagLexiconSnapshot
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.persistence.file_prompt_autocomplete_gateway")
_DEFAULT_ASSET_PACKAGE = "substitute.infrastructure.persistence.assets"
_DEFAULT_ASSET_NAME = "prompt_autocomplete.txt"
_AUTOCOMPLETE_BUCKET_PREFIX_LENGTH = 2
_QUERY_CACHE_LIMIT = 512


@dataclass(frozen=True)
class _CachedPromptAutocompleteRow:
    """Cache one display suggestion alongside its normalized lookup key."""

    normalized_tag: str
    suggestion: PromptAutocompleteSuggestion


@dataclass(frozen=True, slots=True)
class _PromptAutocompleteIndex:
    """Store immutable prompt autocomplete lookup structures."""

    rows: tuple[_CachedPromptAutocompleteRow, ...]
    exact_tags: frozenset[str]
    prefix_buckets: Mapping[str, tuple[_CachedPromptAutocompleteRow, ...]]


def _parse_popularity_value(raw_line: str) -> int:
    """Extract the popularity score from one raw autocomplete asset row."""

    _prefix, separator, remainder = raw_line.partition(",")
    if not separator:
        return 0
    digits: list[str] = []
    for character in remainder.lstrip():
        if not character.isdigit():
            break
        digits.append(character)
    return int("".join(digits)) if digits else 0


def _display_autocomplete_tag(raw_tag: str) -> str:
    """Return the canonical display tag for one raw asset tag."""

    return raw_tag.replace("_", " ")


def _normalize_autocomplete_lookup_text(text: str) -> str:
    """Return lookup text with spaces and underscores treated equivalently."""

    return " ".join(text.replace("_", " ").casefold().split())


def _parse_autocomplete_rows(
    asset_text: str,
) -> tuple[_CachedPromptAutocompleteRow, ...]:
    """Parse raw autocomplete asset text into immutable suggestion rows."""

    rows: list[_CachedPromptAutocompleteRow] = []
    for raw_line in asset_text.splitlines():
        full_line = raw_line.strip()
        if not full_line:
            continue
        raw_tag = full_line.split(",", 1)[0].strip()
        if not raw_tag:
            continue
        display_tag = _display_autocomplete_tag(raw_tag)
        rows.append(
            _CachedPromptAutocompleteRow(
                normalized_tag=_normalize_autocomplete_lookup_text(display_tag),
                suggestion=PromptAutocompleteSuggestion(
                    tag=display_tag,
                    popularity=_parse_popularity_value(full_line),
                ),
            )
        )
    return tuple(rows)


def _autocomplete_rank_key(
    row: _CachedPromptAutocompleteRow,
) -> tuple[int, int, str]:
    """Return the autocomplete ranking key for one cached row."""

    return (
        -(row.suggestion.popularity or 0),
        len(row.suggestion.tag),
        row.suggestion.tag.casefold(),
    )


def _autocomplete_bucket_key(normalized_text: str) -> str:
    """Return the prefix bucket key for normalized lookup text."""

    return normalized_text[:_AUTOCOMPLETE_BUCKET_PREFIX_LENGTH]


def _autocomplete_row_bucket_keys(normalized_text: str) -> tuple[str, ...]:
    """Return all prefix bucket keys that should contain one row."""

    if not normalized_text:
        return ()
    one_character_key = normalized_text[:1]
    two_character_key = _autocomplete_bucket_key(normalized_text)
    if two_character_key == one_character_key:
        return (one_character_key,)
    return (one_character_key, two_character_key)


def _build_autocomplete_index(
    rows: tuple[_CachedPromptAutocompleteRow, ...],
) -> _PromptAutocompleteIndex:
    """Build immutable exact and prefix lookup structures from parsed rows."""

    buckets: dict[str, list[_CachedPromptAutocompleteRow]] = {}
    for row in rows:
        for bucket_key in _autocomplete_row_bucket_keys(row.normalized_tag):
            buckets.setdefault(bucket_key, []).append(row)
    return _PromptAutocompleteIndex(
        rows=rows,
        exact_tags=frozenset(row.normalized_tag for row in rows),
        prefix_buckets={
            bucket_key: tuple(sorted(bucket_rows, key=_autocomplete_rank_key))
            for bucket_key, bucket_rows in buckets.items()
        },
    )


class FilePromptAutocompleteGateway(PromptAutocompleteGateway, PromptTagLexicon):
    """Serve prompt autocomplete suggestions from the bundled fallback asset."""

    def __init__(
        self,
        *,
        asset_package: str = _DEFAULT_ASSET_PACKAGE,
        asset_name: str = _DEFAULT_ASSET_NAME,
    ) -> None:
        """Configure the packaged fallback asset location for prompt autocomplete."""

        self._asset_package = asset_package
        self._asset_name = asset_name
        self._lock = RLock()
        self._cached_index: _PromptAutocompleteIndex | None = None
        self._query_cache: OrderedDict[
            tuple[str, int], tuple[PromptAutocompleteSuggestion, ...]
        ] = OrderedDict()

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return ranked autocomplete suggestions for one typed prefix."""

        normalized_limit = max(limit, 0)
        normalized_prefix = _normalize_autocomplete_lookup_text(prefix)
        if not normalized_prefix or normalized_limit == 0:
            return ()

        cache_key = (normalized_prefix, normalized_limit)
        with self._lock:
            cached_result = self._query_cache.get(cache_key)
            if cached_result is not None:
                self._query_cache.move_to_end(cache_key)
                return cached_result

        index = self._autocomplete_index()
        bucket = index.prefix_buckets.get(
            _autocomplete_bucket_key(normalized_prefix), ()
        )
        matches: list[PromptAutocompleteSuggestion] = []
        for row in bucket:
            if not row.normalized_tag.startswith(normalized_prefix):
                continue
            matches.append(row.suggestion)
            if len(matches) >= normalized_limit:
                break
        result = tuple(matches)
        with self._lock:
            self._cache_query_result(cache_key, result)
        return result

    def contains_prompt_tag(self, text: str) -> bool:
        """Return whether text exactly matches a bundled autocomplete tag."""

        normalized_text = _normalize_autocomplete_lookup_text(text)
        if not normalized_text:
            return False
        return normalized_text in self._autocomplete_index().exact_tags

    def prepared_prompt_tag_snapshot(self) -> PromptTagLexiconSnapshot:
        """Return cached exact-tag state without loading the asset on this call."""

        with self._lock:
            index = self._cached_index
        if index is None:
            return PromptTagLexiconSnapshot()
        return PromptTagLexiconSnapshot(normalized_tags=index.exact_tags)

    def load_prompt_tag_snapshot(self) -> PromptTagLexiconSnapshot:
        """Load and return exact-tag state at a non-interactive composition boundary."""

        index = self._autocomplete_index()
        return PromptTagLexiconSnapshot(normalized_tags=index.exact_tags)

    def warm(self) -> None:
        """Load the autocomplete index before the first interactive query."""

        self._autocomplete_index()

    def _autocomplete_rows(self) -> tuple[_CachedPromptAutocompleteRow, ...]:
        """Return cached autocomplete rows, loading the bundled asset once."""

        return self._autocomplete_index().rows

    def _autocomplete_index(self) -> _PromptAutocompleteIndex:
        """Return cached autocomplete indexes, loading the bundled asset once."""

        with self._lock:
            if self._cached_index is not None:
                return self._cached_index
        index = _build_autocomplete_index(self._load_rows())
        with self._lock:
            if self._cached_index is None:
                self._cached_index = index
                self._query_cache.clear()
            return self._cached_index

    def _load_rows(self) -> tuple[_CachedPromptAutocompleteRow, ...]:
        """Load and parse bundled autocomplete rows, failing closed on asset errors."""

        try:
            asset_root = files(self._asset_package)
            asset_text = asset_root.joinpath(self._asset_name).read_text(
                encoding="utf-8"
            )
        except (
            AttributeError,
            FileNotFoundError,
            ModuleNotFoundError,
            OSError,
            UnicodeDecodeError,
        ) as error:
            log_warning(
                _LOGGER,
                "Failed to load bundled prompt autocomplete asset",
                asset_package=self._asset_package,
                asset_name=self._asset_name,
                error=repr(error),
            )
            return ()
        return _parse_autocomplete_rows(asset_text)

    def _cache_query_result(
        self,
        cache_key: tuple[str, int],
        result: tuple[PromptAutocompleteSuggestion, ...],
    ) -> None:
        """Store one bounded autocomplete query result."""

        self._query_cache[cache_key] = result
        self._query_cache.move_to_end(cache_key)
        while len(self._query_cache) > _QUERY_CACHE_LIMIT:
            self._query_cache.popitem(last=False)


__all__ = ["FilePromptAutocompleteGateway"]
