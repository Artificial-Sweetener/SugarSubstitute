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

"""Define immutable wildcard feature values shared across presentation owners."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass

from substitute.application.ports import PromptAutocompleteSuggestion

from ..async_work import PromptAsyncResultIdentity
from ..core.state.revisions import PromptSourceIdentity
from .catalog_snapshots import CatalogSnapshotIdentity, CatalogSnapshotStatus

PromptWildcardAutocompleteCacheKey = tuple[Hashable, str, int]
PromptWildcardAutocompleteRefreshCallback = Callable[[], None]
PromptWildcardAutocompleteQueryIdentityProvider = Callable[[], Hashable | None]


@dataclass(frozen=True, slots=True)
class PromptWildcardAutocompleteQuerySnapshot:
    """Publish prepared wildcard autocomplete rows for one query."""

    identity: CatalogSnapshotIdentity
    status: CatalogSnapshotStatus
    prefix: str
    limit: int
    suggestions: tuple[PromptAutocompleteSuggestion, ...]
    cache_key: PromptWildcardAutocompleteCacheKey | None = None
    pending: bool = False

    @property
    def consumable(self) -> bool:
        """Return whether foreground code may display the prepared suggestions."""

        return self.status.consumable


@dataclass(frozen=True, slots=True)
class PromptWildcardAutocompleteRequest:
    """Carry one wildcard autocomplete request without prompt text."""

    identity: PromptAsyncResultIdentity
    cache_key: PromptWildcardAutocompleteCacheKey
    prefix: str
    limit: int
    source_identity: PromptSourceIdentity | None
    current_query_identity: PromptWildcardAutocompleteQueryIdentityProvider | None
    refresh_current_query: PromptWildcardAutocompleteRefreshCallback | None


__all__ = [
    "PromptWildcardAutocompleteCacheKey",
    "PromptWildcardAutocompleteQueryIdentityProvider",
    "PromptWildcardAutocompleteQuerySnapshot",
    "PromptWildcardAutocompleteRefreshCallback",
    "PromptWildcardAutocompleteRequest",
]
