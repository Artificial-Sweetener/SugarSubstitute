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

"""Own the bounded LRU rows used by wildcard autocomplete refreshes."""

from __future__ import annotations

from collections import OrderedDict

from substitute.application.ports import PromptAutocompleteSuggestion

from .wildcard_models import PromptWildcardAutocompleteCacheKey


class PromptWildcardAutocompleteCache:
    """Store current and stale wildcard rows with one bounded LRU policy."""

    def __init__(self, *, limit: int) -> None:
        """Initialize a bounded cache with the supplied positive capacity."""

        if limit <= 0:
            raise ValueError("Wildcard autocomplete cache limit must be positive.")
        self._limit = limit
        self._rows: OrderedDict[
            PromptWildcardAutocompleteCacheKey,
            tuple[PromptAutocompleteSuggestion, ...],
        ] = OrderedDict()

    def get(
        self,
        cache_key: PromptWildcardAutocompleteCacheKey,
    ) -> tuple[PromptAutocompleteSuggestion, ...] | None:
        """Return one current cache entry and make it most recently used."""

        rows = self._rows.get(cache_key)
        if rows is not None:
            self._rows.move_to_end(cache_key)
        return rows

    def store(
        self,
        cache_key: PromptWildcardAutocompleteCacheKey,
        rows: tuple[PromptAutocompleteSuggestion, ...],
    ) -> None:
        """Store rows and evict the oldest entries above the fixed limit."""

        self._rows[cache_key] = rows
        self._rows.move_to_end(cache_key)
        while len(self._rows) > self._limit:
            self._rows.popitem(last=False)

    def stale_rows(
        self,
        *,
        prefix: str,
        limit: int,
    ) -> (
        tuple[
            PromptWildcardAutocompleteCacheKey,
            tuple[PromptAutocompleteSuggestion, ...],
        ]
        | None
    ):
        """Return most-recent rows matching a query across catalog revisions."""

        for cache_key, rows in reversed(self._rows.items()):
            _catalog_identity, cached_prefix, cached_limit = cache_key
            if cached_prefix == prefix and cached_limit == limit:
                return cache_key, rows
        return None

    def clear(self) -> None:
        """Remove every cached wildcard query row."""

        self._rows.clear()

    def keys(self) -> tuple[PromptWildcardAutocompleteCacheKey, ...]:
        """Return cache keys in least-to-most recently used order."""

        return tuple(self._rows)

    @property
    def count(self) -> int:
        """Return the current bounded row count."""

        return len(self._rows)
