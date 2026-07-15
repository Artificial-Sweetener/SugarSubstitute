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

"""Expose prompt scene parsing for prompt-editor projection consumers."""

from __future__ import annotations

from collections import OrderedDict

from substitute.domain.prompt import (
    PromptSceneDocument,
    materialize_scene_prompt,
    parse_prompt_scene_document,
    scene_block_at_source_position,
)
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.prompt_editor.prompt_scene_projection_service")
_SCENE_PARSE_CACHE_LIMIT = 512
_SCENE_PARSE_CACHE: OrderedDict[str, PromptSceneDocument] = OrderedDict()


def parse_prompt_scene_projection_document(text: str) -> PromptSceneDocument:
    """Return parsed prompt scene structure for projection and painting."""

    cached = _SCENE_PARSE_CACHE.get(text)
    if cached is not None:
        _SCENE_PARSE_CACHE.move_to_end(text)
        log_debug(
            _LOGGER,
            "Prompt scene projection parse cache hit",
            text_length=len(text),
            cache_size=len(_SCENE_PARSE_CACHE),
        )
        return cached

    document = parse_prompt_scene_document(text)
    _SCENE_PARSE_CACHE[text] = document
    _SCENE_PARSE_CACHE.move_to_end(text)
    while len(_SCENE_PARSE_CACHE) > _SCENE_PARSE_CACHE_LIMIT:
        _SCENE_PARSE_CACHE.popitem(last=False)
    log_debug(
        _LOGGER,
        "Prompt scene projection parse cache miss",
        text_length=len(text),
        cache_size=len(_SCENE_PARSE_CACHE),
    )
    return document


def prompt_scene_key_at_projection_source_position(
    *,
    text: str,
    source_position: int,
) -> str | None:
    """Return the normalized scene key at one prompt projection source position."""

    document = parse_prompt_scene_projection_document(text)
    scene = scene_block_at_source_position(document, source_position)
    return None if scene is None else scene.marker.normalized_key


def effective_prompt_text_at_source_position(
    *,
    text: str,
    source_position: int,
) -> str:
    """Return the prompt text effective for source-local scene context."""

    document = parse_prompt_scene_projection_document(text)
    if not document.has_scenes:
        return text
    scene = scene_block_at_source_position(document, source_position)
    if scene is None:
        return document.universal_text
    return materialize_scene_prompt(
        universal_text=document.universal_text,
        scene_text=scene.text,
    )


def clear_prompt_scene_projection_cache() -> None:
    """Clear process-wide prompt scene projection parse caches."""

    _SCENE_PARSE_CACHE.clear()


def prewarm_prompt_scene_projection_documents(texts: tuple[str, ...]) -> int:
    """Populate process-wide scene projection caches for restored prompt texts."""

    for text in texts:
        parse_prompt_scene_projection_document(text)
    return len(texts)


__all__ = [
    "parse_prompt_scene_projection_document",
    "prompt_scene_key_at_projection_source_position",
    "effective_prompt_text_at_source_position",
    "clear_prompt_scene_projection_cache",
    "prewarm_prompt_scene_projection_documents",
]
