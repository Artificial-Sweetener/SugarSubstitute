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

"""Rank prompt LoRA catalog items for autocomplete-equivalent fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .prompt_lora_catalog_service import PromptLoraCatalogItem


@dataclass(frozen=True, slots=True)
class PromptLoraRankedMatch:
    """Describe one autocomplete-equivalent LoRA match."""

    item: PromptLoraCatalogItem
    score: int
    match_kind: str


def ranked_lora_matches_for_query(
    query_text: str,
    catalog_items: tuple[PromptLoraCatalogItem, ...],
) -> tuple[PromptLoraRankedMatch, ...]:
    """Return catalog rows ranked the same way LoRA autocomplete ranks them."""

    normalized_query = normalize_lora_query(query_text)
    ranked: list[PromptLoraRankedMatch] = []
    for item in catalog_items:
        match = rank_lora_item(item, normalized_query)
        if match is None:
            continue
        score, match_kind = match
        ranked.append(
            PromptLoraRankedMatch(
                item=item,
                score=score,
                match_kind=match_kind,
            )
        )
    return tuple(sorted(ranked, key=lora_rank_sort_key))


def lora_rank_sort_key(match: PromptLoraRankedMatch) -> tuple[int, str, str]:
    """Return the deterministic LoRA autocomplete ordering key."""

    display_text = match.item.display_name or match.item.basename
    return (
        match.score,
        display_text.casefold(),
        match.item.relative_path.casefold(),
    )


def rank_lora_item(
    item: PromptLoraCatalogItem,
    normalized_query: str,
) -> tuple[int, str] | None:
    """Return one autocomplete-equivalent score and match label."""

    if not normalized_query:
        return (900, "empty")

    display_name = normalize_lora_query(item.display_name)
    basename = normalize_lora_query(item.basename)
    prompt_name = normalize_lora_query(item.prompt_name)
    backend_without_extension = normalize_lora_query(
        strip_lora_extension(item.backend_value)
    )
    query_has_path = query_has_path_separator(normalized_query)

    exact_fields = (prompt_name, backend_without_extension, display_name, basename)
    if normalized_query in exact_fields:
        return (0, "exact")

    if basename.startswith(normalized_query):
        return (100, "basename_prefix")
    if display_name.startswith(normalized_query):
        return (110, "display_prefix")
    if query_has_path and prompt_name.startswith(normalized_query):
        return (120, "path_prefix")

    if normalized_query in basename:
        return (300, "basename_substring")
    if normalized_query in display_name:
        return (310, "display_substring")
    if normalized_query in prompt_name:
        return (330, "path_substring")

    if normalized_query in normalize_lora_query(item.search_text):
        return (700, "metadata")

    return None


def normalize_lora_query(value: str) -> str:
    """Normalize one LoRA query string for autocomplete-equivalent matching."""

    return value.replace("\\", "/").casefold()


def strip_lora_extension(value: str) -> str:
    """Remove the final supported LoRA file extension from one value."""

    lowered = value.casefold()
    for extension in (".safetensors", ".ckpt", ".pt"):
        if lowered.endswith(extension):
            return value[: -len(extension)]
    return value


def query_has_path_separator(value: str) -> bool:
    """Return whether a query includes an explicit path separator."""

    return "/" in value or "\\" in value


__all__ = [
    "PromptLoraRankedMatch",
    "lora_rank_sort_key",
    "normalize_lora_query",
    "query_has_path_separator",
    "rank_lora_item",
    "ranked_lora_matches_for_query",
    "strip_lora_extension",
]
