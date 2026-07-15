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

"""Rank LoRA autocomplete candidates for prompt schedule tokens."""

from __future__ import annotations

from dataclasses import dataclass


from .prompt_lora_catalog_service import PromptLoraCatalogItem
from .prompt_lora_ranking import (
    query_has_path_separator,
    ranked_lora_matches_for_query,
)
from .prompt_lora_schedule_service import PromptLoraScheduleService


@dataclass(frozen=True, slots=True)
class PromptLoraAutocompleteQuery:
    """Describe an active LoRA schedule completion range."""

    query_text: str
    token_start: int
    token_end: int
    name_start: int
    name_end: int
    replacement_start: int
    replacement_end: int
    typed_weight_text: str | None
    has_closing_bracket: bool


@dataclass(frozen=True, slots=True)
class PromptLoraAutocompleteCandidate:
    """Describe one ranked LoRA completion result."""

    item: PromptLoraCatalogItem
    score: int
    display_text: str
    display_completion_suffix: str
    replacement_text: str
    match_kind: str


class PromptLoraAutocompleteService:
    """Rank LoRA catalog rows and build scheduler-safe replacement tokens."""

    def __init__(
        self,
        schedule_service: PromptLoraScheduleService | None = None,
    ) -> None:
        """Store the shared schedule text builder used by autocomplete results."""

        self._schedule_service = schedule_service or PromptLoraScheduleService()

    def rank_candidates(
        self,
        query: PromptLoraAutocompleteQuery,
        catalog_items: tuple[PromptLoraCatalogItem, ...],
    ) -> tuple[PromptLoraAutocompleteCandidate, ...]:
        """Return LoRA candidates ordered for one active prompt query."""

        ranked: list[PromptLoraAutocompleteCandidate] = []
        for match in ranked_lora_matches_for_query(query.query_text, catalog_items):
            item = match.item
            display_text = item.display_name or item.basename
            ranked.append(
                PromptLoraAutocompleteCandidate(
                    item=item,
                    score=match.score,
                    display_text=display_text,
                    display_completion_suffix=_display_completion_suffix(
                        query.query_text,
                        display_text=display_text,
                        prompt_name=item.prompt_name,
                    ),
                    replacement_text=self._schedule_service.schedule_text(
                        item,
                        weight_text=query.typed_weight_text,
                    ),
                    match_kind=match.match_kind,
                )
            )

        candidates = tuple(
            sorted(
                ranked,
                key=lambda candidate: (
                    candidate.score,
                    candidate.display_text.casefold(),
                    candidate.item.relative_path.casefold(),
                ),
            )
        )
        return candidates


def _display_completion_suffix(
    query_text: str,
    *,
    display_text: str,
    prompt_name: str,
) -> str:
    """Return display-only ghost suffix text for one selected LoRA."""

    if not query_text:
        return display_text
    display_suffix = _completion_suffix(display_text, query_text)
    if display_suffix:
        return display_suffix
    if query_has_path_separator(query_text):
        return _completion_suffix(prompt_name, query_text)
    return ""


def _completion_suffix(candidate_text: str, typed_prefix: str) -> str:
    """Return the remaining suffix when typed text is a compatible prefix."""

    if len(typed_prefix) > len(candidate_text):
        return ""

    for typed_character, candidate_character in zip(typed_prefix, candidate_text):
        if not _characters_match(typed_character, candidate_character):
            return ""
    return candidate_text[len(typed_prefix) :]


def _characters_match(typed_character: str, candidate_character: str) -> bool:
    """Return whether two completion characters match for ghost text."""

    typed = _normalize_separator_character(typed_character).casefold()
    candidate = _normalize_separator_character(candidate_character).casefold()
    if typed == candidate:
        return True
    return {typed, candidate} == {"_", " "}


def _normalize_separator_character(value: str) -> str:
    """Normalize path separators for one character comparison."""

    if value == "\\":
        return "/"
    return value


__all__ = [
    "PromptLoraAutocompleteCandidate",
    "PromptLoraAutocompleteQuery",
    "PromptLoraAutocompleteService",
]
