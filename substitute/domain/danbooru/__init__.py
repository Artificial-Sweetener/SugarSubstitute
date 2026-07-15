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

"""Expose Danbooru domain contracts without eager model imports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from substitute.domain.danbooru.cache_models import (
        DanbooruCachedImageAsset,
        DanbooruCachedPost,
        DanbooruCachedPostSearch,
        DanbooruCachedTag,
        DanbooruCachedWikiPage,
        DanbooruCacheSummary,
    )
    from substitute.domain.danbooru.models import (
        DanbooruLookupStatus,
        DanbooruMediaAssetLookupResult,
        DanbooruMediaAssetRecord,
        DanbooruMediaAssetVariantRecord,
        DanbooruPostLookupResult,
        DanbooruPostRecord,
        DanbooruTagLookupResult,
        DanbooruTagRecord,
        DanbooruWikiPageLookupResult,
        DanbooruWikiPageRecord,
    )
    from substitute.domain.danbooru.preferences import (
        DANBOORU_PREFERENCES_SCHEMA_VERSION,
        DanbooruImageRatingPolicy,
        DanbooruPreferences,
        default_danbooru_preferences,
    )

_LAZY_EXPORTS = {
    "DanbooruCacheSummary": "substitute.domain.danbooru.cache_models",
    "DanbooruCachedImageAsset": "substitute.domain.danbooru.cache_models",
    "DanbooruCachedPost": "substitute.domain.danbooru.cache_models",
    "DanbooruCachedPostSearch": "substitute.domain.danbooru.cache_models",
    "DanbooruCachedTag": "substitute.domain.danbooru.cache_models",
    "DanbooruCachedWikiPage": "substitute.domain.danbooru.cache_models",
    "DanbooruMediaAssetLookupResult": "substitute.domain.danbooru.models",
    "DanbooruMediaAssetRecord": "substitute.domain.danbooru.models",
    "DanbooruMediaAssetVariantRecord": "substitute.domain.danbooru.models",
    "DanbooruLookupStatus": "substitute.domain.danbooru.models",
    "DanbooruPostLookupResult": "substitute.domain.danbooru.models",
    "DanbooruPostRecord": "substitute.domain.danbooru.models",
    "DANBOORU_PREFERENCES_SCHEMA_VERSION": "substitute.domain.danbooru.preferences",
    "DanbooruImageRatingPolicy": "substitute.domain.danbooru.preferences",
    "DanbooruPreferences": "substitute.domain.danbooru.preferences",
    "DanbooruTagLookupResult": "substitute.domain.danbooru.models",
    "DanbooruTagRecord": "substitute.domain.danbooru.models",
    "DanbooruWikiPageLookupResult": "substitute.domain.danbooru.models",
    "DanbooruWikiPageRecord": "substitute.domain.danbooru.models",
    "default_danbooru_preferences": "substitute.domain.danbooru.preferences",
}


def __getattr__(name: str) -> object:
    """Load one exported Danbooru domain symbol on first access."""

    try:
        module_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "DanbooruCacheSummary",
    "DanbooruCachedImageAsset",
    "DanbooruCachedPost",
    "DanbooruCachedPostSearch",
    "DanbooruCachedTag",
    "DanbooruCachedWikiPage",
    "DanbooruMediaAssetLookupResult",
    "DanbooruMediaAssetRecord",
    "DanbooruMediaAssetVariantRecord",
    "DanbooruLookupStatus",
    "DanbooruPostLookupResult",
    "DanbooruPostRecord",
    "DANBOORU_PREFERENCES_SCHEMA_VERSION",
    "DanbooruImageRatingPolicy",
    "DanbooruPreferences",
    "DanbooruTagLookupResult",
    "DanbooruTagRecord",
    "DanbooruWikiPageLookupResult",
    "DanbooruWikiPageRecord",
    "default_danbooru_preferences",
]
