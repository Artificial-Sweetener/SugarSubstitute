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

"""Resolve scheduled LoRA trigger-word candidates for prompt editor features."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal


from .prompt_autocomplete_query_service import autocomplete_replacement_text
from .prompt_document_projector import PromptDocumentProjector
from .prompt_lora_catalog_service import (
    PromptLoraCatalogItem,
    PromptLoraCatalogLookup,
)
from substitute.application.model_metadata import ModelCatalogItem


@dataclass(frozen=True, slots=True)
class PromptScheduledLora:
    """Describe one LoRA scheduled for prompt trigger-word use."""

    prompt_name: str
    backend_value: str
    display_name: str
    trained_words: tuple[str, ...]
    source: Literal["inline_prompt", "cube_field", "graph_effective"]


@dataclass(frozen=True, slots=True)
class PromptTriggerWordSuggestion:
    """Describe one LoRA trigger-word autocomplete or insertion candidate."""

    trigger_word: str
    lora_display_name: str
    lora_backend_value: str


@dataclass(frozen=True, slots=True)
class _PromptTriggerWordIndexRow:
    """Store one normalized trigger-word row for repeated prefix lookup."""

    normalized_word: str
    replacement_key: str
    suggestion: PromptTriggerWordSuggestion


@dataclass(frozen=True, slots=True)
class PromptTriggerWordIndex:
    """Cache scheduled LoRA trigger words for repeated autocomplete lookup."""

    rows: tuple[_PromptTriggerWordIndexRow, ...]

    @classmethod
    def build(
        cls,
        scheduled_loras: tuple[PromptScheduledLora, ...],
    ) -> "PromptTriggerWordIndex":
        """Build a reusable trigger-word lookup index from scheduled LoRAs."""

        rows: list[_PromptTriggerWordIndexRow] = []
        for scheduled_lora in scheduled_loras:
            for trained_word in _iter_autocomplete_trigger_words(
                scheduled_lora.trained_words
            ):
                if not trained_word.strip():
                    continue
                replacement_key = _normalize_replacement_comparison_text(trained_word)
                rows.append(
                    _PromptTriggerWordIndexRow(
                        normalized_word=_normalize_trigger_lookup_text(trained_word),
                        replacement_key=replacement_key,
                        suggestion=PromptTriggerWordSuggestion(
                            trigger_word=trained_word,
                            lora_display_name=scheduled_lora.display_name,
                            lora_backend_value=scheduled_lora.backend_value,
                        ),
                    )
                )
        return cls(rows=tuple(rows))

    def search(self, prefix: str) -> tuple[PromptTriggerWordSuggestion, ...]:
        """Return indexed trigger-word suggestions matching the typed prefix."""

        normalized_prefix = _normalize_trigger_lookup_text(prefix)
        if not normalized_prefix:
            return ()
        suggestions: list[PromptTriggerWordSuggestion] = []
        seen_replacements: set[str] = set()
        for row in self.rows:
            if not row.normalized_word.startswith(normalized_prefix):
                continue
            if row.replacement_key in seen_replacements:
                continue
            seen_replacements.add(row.replacement_key)
            suggestions.append(row.suggestion)
        return tuple(suggestions)


class PromptScheduledLoraService:
    """Resolve scheduled LoRAs and trigger words from prompt context inputs."""

    def inline_scheduled_loras(
        self,
        *,
        prompt_text: str,
        document_projector: PromptDocumentProjector,
        lora_catalog: PromptLoraCatalogLookup,
    ) -> tuple[PromptScheduledLora, ...]:
        """Return catalog-backed LoRAs scheduled directly in prompt syntax."""

        if "<lora:" not in prompt_text.casefold():
            return ()
        document_view = document_projector.build_document_view(prompt_text)
        scheduled: list[PromptScheduledLora] = []
        seen_keys: set[str] = set()
        missing_catalog_count = 0
        duplicate_count = 0
        for lora_span in document_view.lora_spans:
            catalog_item = lora_catalog.find_lora(lora_span.prompt_name)
            if catalog_item is None:
                missing_catalog_count += 1
                continue
            scheduled_lora = scheduled_lora_from_catalog_item(
                catalog_item,
                source="inline_prompt",
            )
            dedupe_key = _scheduled_lora_dedupe_key(scheduled_lora)
            if dedupe_key in seen_keys:
                duplicate_count += 1
                continue
            seen_keys.add(dedupe_key)
            scheduled.append(scheduled_lora)
        result = tuple(scheduled)
        return result

    def trigger_word_suggestions(
        self,
        *,
        scheduled_loras: tuple[PromptScheduledLora, ...],
        prefix: str,
    ) -> tuple[PromptTriggerWordSuggestion, ...]:
        """Return trigger words matching the supplied autocomplete prefix."""

        index = PromptTriggerWordIndex.build(scheduled_loras)
        suggestions = index.search(prefix)
        return suggestions

    def configured_trigger_words_for_insertion(
        self,
        scheduled_lora: PromptScheduledLora,
    ) -> str:
        """Return all provider-authored trigger words for explicit insertion."""

        return ", ".join(
            trained_word.strip()
            for trained_word in scheduled_lora.trained_words
            if trained_word.strip()
        )

    def merge_scheduled_loras(
        self,
        *scheduled_lora_groups: tuple[PromptScheduledLora, ...],
    ) -> tuple[PromptScheduledLora, ...]:
        """Merge scheduled LoRA groups while preserving first effective order."""

        merged: list[PromptScheduledLora] = []
        seen_keys: set[str] = set()
        for group in scheduled_lora_groups:
            for scheduled_lora in group:
                dedupe_key = _scheduled_lora_dedupe_key(scheduled_lora)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                merged.append(scheduled_lora)
        return tuple(merged)


def scheduled_lora_from_catalog_item(
    item: PromptLoraCatalogItem,
    *,
    source: Literal["inline_prompt", "cube_field", "graph_effective"],
) -> PromptScheduledLora:
    """Adapt one prompt LoRA catalog item into a scheduled LoRA record."""

    return PromptScheduledLora(
        prompt_name=item.prompt_name,
        backend_value=item.backend_value,
        display_name=_combined_lora_display_name(
            page_name=item.display_name,
            version_name=item.display_subtitle,
            fallback_name=item.basename,
        ),
        trained_words=tuple(item.trained_words),
        source=source,
    )


def scheduled_lora_from_model_catalog_item(
    item: ModelCatalogItem,
    *,
    source: Literal["inline_prompt", "cube_field", "graph_effective"],
) -> PromptScheduledLora:
    """Adapt one generic model catalog LoRA item into a scheduled LoRA record."""

    return PromptScheduledLora(
        prompt_name=_strip_supported_extension(item.backend_value),
        backend_value=item.backend_value,
        display_name=_combined_lora_display_name(
            page_name=item.display_name,
            version_name=item.display_subtitle,
            fallback_name=item.basename,
        ),
        trained_words=tuple(item.trained_words),
        source=source,
    )


def _combined_lora_display_name(
    *,
    page_name: str,
    version_name: str | None,
    fallback_name: str,
) -> str:
    """Return a compact text label that includes page and version names."""

    resolved_page_name = page_name.strip() or fallback_name.strip()
    resolved_version_name = "" if version_name is None else version_name.strip()
    if resolved_page_name and resolved_version_name:
        return f"{resolved_page_name} - {resolved_version_name}"
    if resolved_page_name:
        return resolved_page_name
    return resolved_version_name


def _scheduled_lora_dedupe_key(scheduled_lora: PromptScheduledLora) -> str:
    """Return the stable identity key for one scheduled LoRA."""

    if scheduled_lora.backend_value.strip():
        return scheduled_lora.backend_value.replace("\\", "/").casefold()
    return scheduled_lora.prompt_name.replace("\\", "/").casefold()


def _iter_autocomplete_trigger_words(
    trained_words: tuple[str, ...],
) -> Iterator[str]:
    """Yield comma-split trigger words for autocomplete lookup only."""

    for trained_word in trained_words:
        for part in trained_word.split(","):
            trigger_word = part.strip()
            if trigger_word:
                yield trigger_word


def _normalize_trigger_lookup_text(text: str) -> str:
    """Return prefix-lookup text with spaces and underscores equivalent."""

    return text.replace("_", " ").casefold()


def _normalize_replacement_comparison_text(text: str) -> str:
    """Return normalized replacement text used for autocomplete deduplication."""

    return _normalize_prompt_word_for_storage(autocomplete_replacement_text(text))


def _normalize_prompt_word_for_storage(text: str) -> str:
    """Return a comparison key for one stored or inserted prompt word."""

    return (
        text.replace("\\(", "(")
        .replace("\\)", ")")
        .replace("_", " ")
        .casefold()
        .strip()
    )


def _strip_supported_extension(value: str) -> str:
    """Strip a supported LoRA model extension from one backend value."""

    normalized = value.replace("\\", "/")
    for extension in (".safetensors", ".ckpt", ".pt"):
        if normalized.casefold().endswith(extension):
            return value[: -len(extension)]
    return value


__all__ = [
    "PromptScheduledLora",
    "PromptScheduledLoraService",
    "PromptTriggerWordIndex",
    "PromptTriggerWordSuggestion",
    "scheduled_lora_from_catalog_item",
    "scheduled_lora_from_model_catalog_item",
]
