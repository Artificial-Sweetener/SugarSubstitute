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

"""Define cached Danbooru content models used by the native wiki viewer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from substitute.application.danbooru.models import (
    DanbooruFailureReason,
    DanbooruWikiNavigationEntry,
)


class DanbooruContentFreshnessState(str, Enum):
    """Describe whether content came from a fresh or stale cache snapshot."""

    FRESH = "fresh"
    STALE = "stale"


class DanbooruImagePreviewState(str, Enum):
    """Describe how one wiki image should be presented."""

    READY = "ready"
    HIDDEN = "hidden"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class DanbooruWikiContentPage:
    """Describe one cached Danbooru wiki page prepared for native rendering."""

    title: str
    display_title: str
    category_name: str | None
    post_count: int | None
    other_names: tuple[str, ...]
    canonical_url: str
    body_dtext: str
    freshness_state: DanbooruContentFreshnessState


@dataclass(frozen=True, slots=True)
class DanbooruWikiContentLookupResult:
    """Return one cached-content lookup outcome for the native wiki dialog."""

    page: DanbooruWikiContentPage | None
    navigation_entry: DanbooruWikiNavigationEntry | None
    requested_text: str
    resolved_title: str | None = None
    failure_reason: DanbooruFailureReason | None = None
    error: str = ""

    @property
    def succeeded(self) -> bool:
        """Return whether the lookup produced a wiki page."""

        return self.page is not None


@dataclass(frozen=True, slots=True)
class DanbooruWikiImagePreview:
    """Describe one Danbooru wiki image preview or placeholder outcome."""

    post_id: int
    canonical_post_url: str
    state: DanbooruImagePreviewState
    local_path: Path | None
    rating: str | None
    width: int | None
    height: int | None
    hidden_reason: str = ""


__all__ = [
    "DanbooruContentFreshnessState",
    "DanbooruImagePreviewState",
    "DanbooruWikiContentLookupResult",
    "DanbooruWikiContentPage",
    "DanbooruWikiImagePreview",
]
