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

"""Own process-wide prompt document parse and view caches."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from threading import RLock
from typing import TypeVar

from substitute.domain.prompt import PromptDocument, parse_prompt_document
from substitute.shared.logging.logger import get_logger, log_debug

from .prompt_document_views import PromptDocumentView

_LOGGER = get_logger("application.prompt_editor.prompt_document_cache")
_DOCUMENT_CACHE_LIMIT = 512
_DOCUMENT_VIEW_CACHE_LIMIT = 512
_DOCUMENT_CACHE: OrderedDict[str, PromptDocument] = OrderedDict()
_DOCUMENT_VIEW_CACHE: OrderedDict[str, PromptDocumentView] = OrderedDict()
_DOCUMENT_CACHE_LOCK = RLock()
_CacheKey = TypeVar("_CacheKey")
_CacheValue = TypeVar("_CacheValue")


def cached_prompt_document(text: str) -> PromptDocument:
    """Return a cached immutable domain prompt document for one source string."""

    with _DOCUMENT_CACHE_LOCK:
        cached = _DOCUMENT_CACHE.get(text)
        if cached is not None:
            _DOCUMENT_CACHE.move_to_end(text)
            log_debug(
                _LOGGER,
                "Prompt document parse cache hit",
                text_length=len(text),
                cache_size=len(_DOCUMENT_CACHE),
            )
            return cached

    document = parse_prompt_document(text)
    with _DOCUMENT_CACHE_LOCK:
        _store_lru(_DOCUMENT_CACHE, text, document, _DOCUMENT_CACHE_LIMIT)
        log_debug(
            _LOGGER,
            "Prompt document parse cache miss",
            text_length=len(text),
            cache_size=len(_DOCUMENT_CACHE),
        )
    return document


def cached_prompt_document_view(text: str) -> PromptDocumentView | None:
    """Return one cached application prompt view when already projected."""

    with _DOCUMENT_CACHE_LOCK:
        cached = _DOCUMENT_VIEW_CACHE.get(text)
        if cached is None:
            return None
        _DOCUMENT_VIEW_CACHE.move_to_end(text)
        log_debug(
            _LOGGER,
            "Prompt document view cache hit",
            text_length=len(text),
            cache_size=len(_DOCUMENT_VIEW_CACHE),
        )
        return cached


def store_prompt_document_view(
    text: str,
    document_view: PromptDocumentView,
) -> None:
    """Store one projected prompt view in the process-wide LRU view cache."""

    with _DOCUMENT_CACHE_LOCK:
        _store_lru(
            _DOCUMENT_VIEW_CACHE,
            text,
            document_view,
            _DOCUMENT_VIEW_CACHE_LIMIT,
        )
        log_debug(
            _LOGGER,
            "Prompt document view cache miss",
            text_length=len(text),
            cache_size=len(_DOCUMENT_VIEW_CACHE),
        )


def prewarm_prompt_document_views(
    texts: tuple[str, ...],
    build_document_view: Callable[[str], PromptDocumentView],
) -> int:
    """Populate process-wide prompt document caches for restored prompt texts."""

    warmed = 0
    for text in texts:
        build_document_view(text)
        warmed += 1
    return warmed


def clear_prompt_document_caches() -> None:
    """Clear process-wide prompt document parse and projection-input caches."""

    with _DOCUMENT_CACHE_LOCK:
        _DOCUMENT_CACHE.clear()
        _DOCUMENT_VIEW_CACHE.clear()


def _store_lru(
    cache: OrderedDict[_CacheKey, _CacheValue],
    key: _CacheKey,
    value: _CacheValue,
    limit: int,
) -> None:
    """Store one cache value and evict the oldest entries beyond the limit."""

    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)


__all__ = [
    "cached_prompt_document",
    "cached_prompt_document_view",
    "clear_prompt_document_caches",
    "prewarm_prompt_document_views",
    "store_prompt_document_view",
]
