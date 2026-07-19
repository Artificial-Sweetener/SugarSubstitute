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

"""Merge user tag lists with the bundled prompt autocomplete catalog."""

from __future__ import annotations

from threading import RLock

from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptAutocompleteSuggestion,
    PromptTagLexicon,
)
from substitute.application.ports.prompt_tag_lexicon import (
    PromptTagLexiconSnapshot,
    PromptTagLexiconSnapshotProvider,
)
from substitute.application.prompt_autocomplete_lists import (
    PromptAutocompleteListService,
    PromptAutocompleteListSnapshot,
    normalize_prompt_tag,
)


class ConfiguredPromptAutocompleteGateway(PromptAutocompleteGateway, PromptTagLexicon):
    """Serve one prepared catalog with custom additions and exact censorship."""

    def __init__(
        self,
        bundled_gateway: PromptAutocompleteGateway,
        list_service: PromptAutocompleteListService,
    ) -> None:
        """Store the bundled catalog and prepare initial user-list state."""

        self._bundled_gateway = bundled_gateway
        self._list_service = list_service
        self._lock = RLock()
        self._snapshot = list_service.snapshot()
        self._cache_revision = 0

    @property
    def cache_revision(self) -> int:
        """Return identity that changes after any managed-list mutation."""

        with self._lock:
            return self._cache_revision

    def refresh(self) -> None:
        """Prepare current filesystem list state outside interactive query paths."""

        snapshot = self._list_service.snapshot()
        with self._lock:
            self._snapshot = snapshot
            self._cache_revision += 1

    def warm(self) -> None:
        """Warm the bundled catalog and refresh configured list state."""

        warmer = getattr(self._bundled_gateway, "warm", None)
        if callable(warmer):
            warmer()
        self.refresh()

    def search(
        self, prefix: str, limit: int = 10
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return custom-first suggestions after exact normalized censorship."""

        normalized_prefix = normalize_prompt_tag(prefix)
        normalized_limit = max(limit, 0)
        if not normalized_prefix or normalized_limit == 0:
            return ()
        snapshot = self._prepared_snapshot()
        results: list[PromptAutocompleteSuggestion] = []
        seen: set[str] = set()
        for tag in snapshot.custom_tags:
            normalized = normalize_prompt_tag(tag)
            if not normalized.startswith(normalized_prefix):
                continue
            results.append(
                PromptAutocompleteSuggestion(
                    tag=tag,
                    popularity=None,
                    source_label="custom",
                    source_kind="tag",
                )
            )
            seen.add(normalized)
            if len(results) >= normalized_limit:
                return tuple(results)
        bundled_limit = normalized_limit + len(snapshot.censored_tags) + len(seen)
        for suggestion in self._bundled_gateway.search(prefix, bundled_limit):
            normalized = normalize_prompt_tag(suggestion.tag)
            if normalized in snapshot.censored_tags or normalized in seen:
                continue
            results.append(suggestion)
            seen.add(normalized)
            if len(results) >= normalized_limit:
                break
        return tuple(results)

    def contains_prompt_tag(self, text: str) -> bool:
        """Return exact membership after custom merge and censorship."""

        normalized = normalize_prompt_tag(text)
        if not normalized:
            return False
        snapshot = self._prepared_snapshot()
        if normalized in snapshot.censored_tags:
            return False
        if any(normalize_prompt_tag(tag) == normalized for tag in snapshot.custom_tags):
            return True
        bundled = self._bundled_lexicon()
        return bundled.contains_prompt_tag(text) if bundled is not None else False

    def prepared_prompt_tag_snapshot(self) -> PromptTagLexiconSnapshot:
        """Return prepared exact membership without filesystem access."""

        return self._merged_lexicon_snapshot(load=False)

    def load_prompt_tag_snapshot(self) -> PromptTagLexiconSnapshot:
        """Load bundled exact membership and merge prepared user list state."""

        return self._merged_lexicon_snapshot(load=True)

    def _prepared_snapshot(self) -> PromptAutocompleteListSnapshot:
        """Return the immutable current user-list snapshot."""

        with self._lock:
            return self._snapshot

    def _bundled_lexicon(self) -> PromptTagLexicon | None:
        """Return the bundled gateway when it provides exact tag membership."""

        return (
            self._bundled_gateway
            if isinstance(self._bundled_gateway, PromptTagLexicon)
            else None
        )

    def _merged_lexicon_snapshot(self, *, load: bool) -> PromptTagLexiconSnapshot:
        """Merge custom and censored identities into the bundled lexicon."""

        bundled = self._bundled_lexicon()
        normalized_tags: frozenset[str] = frozenset()
        if load:
            loader = getattr(self._bundled_gateway, "load_prompt_tag_snapshot", None)
            loaded = loader() if callable(loader) else None
            if isinstance(loaded, PromptTagLexiconSnapshot):
                normalized_tags = loaded.normalized_tags
        elif isinstance(self._bundled_gateway, PromptTagLexiconSnapshotProvider):
            normalized_tags = (
                self._bundled_gateway.prepared_prompt_tag_snapshot().normalized_tags
            )
        elif bundled is not None:
            normalized_tags = frozenset()
        snapshot = self._prepared_snapshot()
        custom = frozenset(normalize_prompt_tag(tag) for tag in snapshot.custom_tags)
        return PromptTagLexiconSnapshot(
            normalized_tags=(normalized_tags | custom) - snapshot.censored_tags
        )


__all__ = ["ConfiguredPromptAutocompleteGateway"]
