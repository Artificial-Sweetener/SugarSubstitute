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

"""Define Danbooru cache records shared by persistence and application services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.domain.danbooru.models import (
    DanbooruLookupStatus,
    DanbooruPostRecord,
    DanbooruTagRecord,
    DanbooruWikiPageRecord,
)


@dataclass(frozen=True, slots=True)
class DanbooruCachedWikiPage:
    """Persist one cached Danbooru wiki page lookup result."""

    title: str
    lookup_status: DanbooruLookupStatus
    wiki_page: DanbooruWikiPageRecord | None
    fetched_at: str
    expires_at: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class DanbooruCachedTag:
    """Persist one cached Danbooru tag lookup result."""

    name: str
    lookup_status: DanbooruLookupStatus
    tag: DanbooruTagRecord | None
    fetched_at: str
    expires_at: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class DanbooruCachedPost:
    """Persist one cached Danbooru post lookup result."""

    post_id: int
    lookup_status: DanbooruLookupStatus
    post: DanbooruPostRecord | None
    fetched_at: str
    expires_at: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class DanbooruCachedPostSearch:
    """Persist one cached Danbooru tag-post search candidate set."""

    tag_name: str
    post_ids: tuple[int, ...]
    fetched_at: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class DanbooruCachedImageAsset:
    """Persist one cached Danbooru preview image asset."""

    cache_key: str
    source_url: str
    local_path: Path
    rating: str | None
    width: int | None
    height: int | None
    fetched_at: str
    last_used_at: str
    byte_size: int


@dataclass(frozen=True, slots=True)
class DanbooruCacheSummary:
    """Summarize current Danbooru cache usage for presentation and diagnostics."""

    metadata_entry_count: int
    image_entry_count: int
    image_bytes: int


__all__ = [
    "DanbooruCacheSummary",
    "DanbooruCachedImageAsset",
    "DanbooruCachedPost",
    "DanbooruCachedPostSearch",
    "DanbooruCachedTag",
    "DanbooruCachedWikiPage",
]
