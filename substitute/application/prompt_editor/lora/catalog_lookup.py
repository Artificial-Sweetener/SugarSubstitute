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

"""Index and resolve immutable prompt-editor LoRA catalog snapshots."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath, PureWindowsPath
from types import MappingProxyType

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraCatalogLookupResult,
    PromptLoraCatalogSnapshot,
)
from substitute.application.prompt_editor.lora.ranking import (
    normalize_lora_query,
    ranked_lora_matches_for_query,
    strip_lora_extension,
)


def build_lora_catalog_snapshot(
    items: tuple[PromptLoraCatalogItem, ...],
    *,
    model_generation: int,
    revision: int,
    authoritative: bool,
) -> PromptLoraCatalogSnapshot:
    """Build immutable exact, suffix, collision, and ranked lookup indexes."""

    prompt_name_items: dict[str, PromptLoraCatalogItem] = {}
    backend_value_items: dict[str, PromptLoraCatalogItem] = {}
    backend_prompt_items: dict[str, PromptLoraCatalogItem] = {}
    collision_lists: dict[str, list[PromptLoraCatalogItem]] = defaultdict(list)
    autocomplete_exact_lists: dict[str, list[PromptLoraCatalogItem]] = defaultdict(list)
    path_suffix_lists: dict[str, list[PromptLoraCatalogItem]] = defaultdict(list)
    for item in items:
        prompt_name_items.setdefault(_prompt_lookup_key(item.prompt_name), item)
        backend_value_items.setdefault(_backend_lookup_key(item.backend_value), item)
        backend_prompt_items.setdefault(_prompt_lookup_key(item.backend_value), item)
        collision_lists[item.collision_key].append(item)
        for key in _autocomplete_exact_keys(item):
            autocomplete_exact_lists[key].append(item)
        for key in _path_suffix_keys(item):
            path_suffix_lists[key].append(item)
    return PromptLoraCatalogSnapshot(
        items=items,
        prompt_name_items=MappingProxyType(prompt_name_items),
        backend_value_items=MappingProxyType(backend_value_items),
        backend_prompt_items=MappingProxyType(backend_prompt_items),
        collision_items=MappingProxyType(
            {key: tuple(bucket) for key, bucket in collision_lists.items()}
        ),
        autocomplete_exact_items=MappingProxyType(
            {
                key: _ranked_items_for_query(key, tuple(bucket))
                for key, bucket in autocomplete_exact_lists.items()
            }
        ),
        path_suffix_items=MappingProxyType(
            {
                key: _ranked_items_for_query(key, tuple(bucket))
                for key, bucket in path_suffix_lists.items()
            }
        ),
        model_generation=model_generation,
        revision=revision,
        authoritative=authoritative,
    )


def find_lora_in_snapshot(
    snapshot: PromptLoraCatalogSnapshot,
    prompt_name: str,
) -> PromptLoraCatalogLookupResult:
    """Resolve one prompt LoRA name and report the matching lookup branch."""

    normalized_prompt_name = _prompt_lookup_key(prompt_name)
    normalized_backend_value = _backend_lookup_key(_with_known_extension(prompt_name))
    item = snapshot.prompt_name_items.get(normalized_prompt_name)
    if item is not None:
        return PromptLoraCatalogLookupResult(match_source="prompt_name", item=item)
    item = snapshot.backend_value_items.get(normalized_backend_value)
    if item is not None:
        return PromptLoraCatalogLookupResult(match_source="backend_value", item=item)
    item = snapshot.backend_prompt_items.get(normalized_prompt_name)
    if item is not None:
        return PromptLoraCatalogLookupResult(match_source="backend_prompt", item=item)

    fallback = _autocomplete_ranked_fallback(snapshot, prompt_name)
    if fallback.item is not None:
        return fallback

    bare_name_matches = snapshot.collision_items.get(
        _collision_key_for_value(prompt_name),
        (),
    )
    bare_name_match_count = len(bare_name_matches)
    if bare_name_match_count == 1:
        return PromptLoraCatalogLookupResult(
            match_source="autocomplete_ranked_basename",
            bare_collision_match_count=bare_name_match_count,
            fallback_candidate_count=bare_name_match_count,
            selected_fallback_rank=0,
            item=bare_name_matches[0],
        )
    if bare_name_match_count > 1:
        ranked_matches = ranked_lora_matches_for_query(
            _basename_without_extension(prompt_name),
            bare_name_matches,
        )
        if ranked_matches:
            return PromptLoraCatalogLookupResult(
                match_source=f"autocomplete_ranked_{ranked_matches[0].match_kind}",
                bare_collision_match_count=bare_name_match_count,
                fallback_candidate_count=len(ranked_matches),
                selected_fallback_rank=0,
                item=ranked_matches[0].item,
            )
    return PromptLoraCatalogLookupResult(
        match_source="miss",
        bare_collision_match_count=bare_name_match_count,
    )


def _autocomplete_ranked_fallback(
    snapshot: PromptLoraCatalogSnapshot,
    prompt_name: str,
) -> PromptLoraCatalogLookupResult:
    """Return an autocomplete-equivalent fallback lookup result."""

    normalized_prompt_name = _prompt_lookup_key(prompt_name)
    exact_candidates = snapshot.autocomplete_exact_items.get(normalized_prompt_name, ())
    if exact_candidates:
        return _fallback_result(
            match_source="autocomplete_ranked_exact",
            items=exact_candidates,
        )
    path_candidates = snapshot.path_suffix_items.get(normalized_prompt_name, ())
    if path_candidates:
        return _fallback_result(
            match_source="autocomplete_ranked_path",
            items=path_candidates,
        )
    basename_key = normalize_lora_query(_basename_without_extension(prompt_name))
    basename_candidates = snapshot.autocomplete_exact_items.get(basename_key, ())
    if basename_candidates:
        return _fallback_result(
            match_source="autocomplete_ranked_basename",
            items=basename_candidates,
        )
    return PromptLoraCatalogLookupResult(match_source="miss")


def _fallback_result(
    *,
    match_source: str,
    items: tuple[PromptLoraCatalogItem, ...],
) -> PromptLoraCatalogLookupResult:
    """Return the first-ranked autocomplete-equivalent fallback item."""

    return PromptLoraCatalogLookupResult(
        match_source=match_source,
        bare_collision_match_count=len(items),
        fallback_candidate_count=len(items),
        selected_fallback_rank=0,
        item=items[0],
    )


def _autocomplete_exact_keys(item: PromptLoraCatalogItem) -> frozenset[str]:
    """Return exact query keys that should behave like LoRA autocomplete."""

    return frozenset(
        key
        for key in (
            normalize_lora_query(item.prompt_name),
            normalize_lora_query(strip_lora_extension(item.backend_value)),
            normalize_lora_query(item.display_name),
            normalize_lora_query(item.basename),
        )
        if key
    )


def _path_suffix_keys(item: PromptLoraCatalogItem) -> frozenset[str]:
    """Return normalized path suffix keys for stale restored path repair."""

    keys: set[str] = set()
    for value in (item.prompt_name, strip_lora_extension(item.backend_value)):
        normalized = _prompt_lookup_key(value)
        parts = tuple(part for part in normalized.split("/") if part)
        for index in range(1, len(parts)):
            keys.add("/".join(parts[index:]))
    return frozenset(keys)


def _ranked_items_for_query(
    query_text: str,
    items: tuple[PromptLoraCatalogItem, ...],
) -> tuple[PromptLoraCatalogItem, ...]:
    """Return items ordered by the same key as LoRA autocomplete."""

    ranked = ranked_lora_matches_for_query(query_text, items)
    if ranked:
        return tuple(match.item for match in ranked)
    return tuple(
        sorted(
            items,
            key=lambda item: (
                (item.display_name or item.basename).casefold(),
                item.relative_path.casefold(),
            ),
        )
    )


def _basename_without_extension(value: str) -> str:
    """Return the extensionless basename for one backend value."""

    normalized_value = value.replace("\\", "/")
    return strip_lora_extension(PurePosixPath(normalized_value).name)


def _collision_key_for_value(value: str) -> str:
    """Return the collision key used to detect bare-name ambiguity."""

    return _basename_without_extension(value).casefold()


def _prompt_lookup_key(value: str) -> str:
    """Return the normalized extensionless key used for prompt LoRA lookup."""

    return strip_lora_extension(value).replace("\\", "/").casefold()


def _backend_lookup_key(value: str) -> str:
    """Return the normalized backend-value key used for prompt LoRA lookup."""

    return value.replace("\\", "/").casefold()


def _with_known_extension(prompt_name: str) -> str:
    """Return prompt name with the default LoRA extension when it has none."""

    windows_suffix = PureWindowsPath(prompt_name).suffix
    posix_suffix = PurePosixPath(prompt_name).suffix
    if windows_suffix or posix_suffix:
        return prompt_name
    return f"{prompt_name}.safetensors"


__all__ = ["build_lora_catalog_snapshot", "find_lora_in_snapshot"]
