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

"""Define application-facing Danbooru view models and typed lookup outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DanbooruFailureReason(str, Enum):
    """Describe why one Danbooru-backed application request did not succeed."""

    EMPTY_INPUT = "empty_input"
    UNSUPPORTED_URL = "unsupported_url"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"


class DanbooruUrlKind(str, Enum):
    """Identify the supported Danbooru URL classes handled by v1."""

    POST = "post"
    CDN = "cdn"


@dataclass(frozen=True, slots=True)
class DanbooruImportedPrompt:
    """Describe prompt text imported from one Danbooru post."""

    display_text: str
    source_post_id: int
    included_tags: tuple[str, ...]
    excluded_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DanbooruWikiPageView:
    """Describe one Danbooru wiki page prepared for native presentation."""

    title: str
    display_title: str
    category_name: str | None
    post_count: int | None
    other_names: tuple[str, ...]
    body_dtext: str
    canonical_url: str
    exists: bool


@dataclass(frozen=True, slots=True)
class DanbooruWikiNavigationEntry:
    """Describe one navigable wiki title for in-dialog history."""

    title: str
    display_title: str


@dataclass(frozen=True, slots=True)
class DanbooruUrlClassification:
    """Describe one supported Danbooru URL and the lookup key it resolved to."""

    url: str
    kind: DanbooruUrlKind
    lookup_value: str


@dataclass(frozen=True, slots=True)
class DanbooruPromptImportResult:
    """Return one prompt-import outcome with typed success or failure details."""

    imported_prompt: DanbooruImportedPrompt | None
    failure_reason: DanbooruFailureReason | None = None
    error: str = ""
    classification: DanbooruUrlClassification | None = None

    @property
    def succeeded(self) -> bool:
        """Return whether the Danbooru URL import produced prompt text."""

        return self.imported_prompt is not None


@dataclass(frozen=True, slots=True)
class DanbooruWikiLookupResult:
    """Return one wiki lookup outcome with presentation-facing page data."""

    page_view: DanbooruWikiPageView | None
    navigation_entry: DanbooruWikiNavigationEntry | None
    requested_text: str
    resolved_title: str | None = None
    failure_reason: DanbooruFailureReason | None = None
    error: str = ""

    @property
    def succeeded(self) -> bool:
        """Return whether the selection resolved to one wiki page view."""

        return self.page_view is not None


__all__ = [
    "DanbooruFailureReason",
    "DanbooruImportedPrompt",
    "DanbooruPromptImportResult",
    "DanbooruUrlClassification",
    "DanbooruUrlKind",
    "DanbooruWikiLookupResult",
    "DanbooruWikiNavigationEntry",
    "DanbooruWikiPageView",
]
