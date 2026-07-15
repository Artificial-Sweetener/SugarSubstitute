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

"""Define typed Danbooru API records and lookup results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DanbooruLookupStatus(str, Enum):
    """Describe the outcome of one Danbooru API lookup."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True, slots=True)
class DanbooruPostRecord:
    """Represent the prompt-relevant subset of one Danbooru post payload."""

    post_id: int
    created_at: str | None
    updated_at: str | None
    source: str
    md5: str | None
    rating: str | None
    tag_string: str
    tag_string_general: str
    tag_string_artist: str
    tag_string_copyright: str
    tag_string_character: str
    tag_string_meta: str
    file_url: str | None
    large_file_url: str | None
    preview_file_url: str | None


@dataclass(frozen=True, slots=True)
class DanbooruWikiPageRecord:
    """Represent one Danbooru wiki page."""

    wiki_page_id: int
    created_at: str | None
    updated_at: str | None
    title: str
    body: str
    other_names: tuple[str, ...]
    category_name: str | None


@dataclass(frozen=True, slots=True)
class DanbooruMediaAssetVariantRecord:
    """Represent one concrete Danbooru media-asset variant."""

    variant_type: str
    url: str
    width: int | None
    height: int | None
    file_ext: str | None


@dataclass(frozen=True, slots=True)
class DanbooruMediaAssetRecord:
    """Represent one Danbooru media asset used by wiki image embeds."""

    asset_id: int
    created_at: str | None
    updated_at: str | None
    md5: str | None
    file_ext: str | None
    image_width: int | None
    image_height: int | None
    variants: tuple[DanbooruMediaAssetVariantRecord, ...]


@dataclass(frozen=True, slots=True)
class DanbooruTagRecord:
    """Represent the metadata needed for one Danbooru tag."""

    tag_id: int
    created_at: str | None
    updated_at: str | None
    name: str
    category: int
    post_count: int
    is_deprecated: bool


@dataclass(frozen=True, slots=True)
class DanbooruPostLookupResult:
    """Return one post lookup outcome with an optional typed record."""

    status: DanbooruLookupStatus
    post: DanbooruPostRecord | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class DanbooruWikiPageLookupResult:
    """Return one wiki-page lookup outcome with an optional typed record."""

    status: DanbooruLookupStatus
    wiki_page: DanbooruWikiPageRecord | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class DanbooruMediaAssetLookupResult:
    """Return one media-asset lookup outcome with an optional typed record."""

    status: DanbooruLookupStatus
    media_asset: DanbooruMediaAssetRecord | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class DanbooruTagLookupResult:
    """Return one tag lookup outcome with an optional typed record."""

    status: DanbooruLookupStatus
    tag: DanbooruTagRecord | None = None
    error: str = ""


__all__ = [
    "DanbooruMediaAssetLookupResult",
    "DanbooruMediaAssetRecord",
    "DanbooruMediaAssetVariantRecord",
    "DanbooruLookupStatus",
    "DanbooruPostLookupResult",
    "DanbooruPostRecord",
    "DanbooruTagLookupResult",
    "DanbooruTagRecord",
    "DanbooruWikiPageLookupResult",
    "DanbooruWikiPageRecord",
]
