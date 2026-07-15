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

"""Contract tests for scheduled LoRA trigger-word services."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptScheduledLora,
    PromptScheduledLoraService,
    PromptTriggerWordIndex,
)
from substitute.application.prompt_editor.prompt_document_projector import (
    PromptDocumentProjector,
)


class _StaticPromptLoraCatalog:
    """Return deterministic LoRA catalog rows for scheduled-LoRA service tests."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store fixed LoRA catalog rows."""

        self._items = items

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured LoRA rows."""

        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return configured LoRA rows without simulating backend loading."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the LoRA row matching one prompt-name reference."""

        normalized_prompt_name = prompt_name.replace("\\", "/").casefold()
        for item in self._items:
            if item.prompt_name.replace("\\", "/").casefold() == normalized_prompt_name:
                return item
        return None


def _lora_item(
    *,
    display_name: str = "CivitAI Midna",
    display_subtitle: str | None = None,
    prompt_name: str = r"characters\midna",
    backend_value: str | None = None,
    trained_words: tuple[str, ...] = ("imp princess", "twili"),
) -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog item."""

    effective_backend_value = (
        f"{prompt_name}.safetensors" if backend_value is None else backend_value
    )
    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=display_subtitle,
        prompt_name=prompt_name,
        backend_value=effective_backend_value,
        relative_path=effective_backend_value,
        folder=prompt_name.rsplit("\\", 1)[0] if "\\" in prompt_name else "",
        basename=prompt_name.rsplit("\\", 1)[-1],
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=trained_words,
        tags=("character",),
        model_page_url=None,
        collision_key=prompt_name.rsplit("\\", 1)[-1].casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, prompt_name, *trained_words)).casefold(),
    )


def test_inline_scheduled_loras_resolve_catalog_metadata() -> None:
    """Inline LoRA syntax should resolve to catalog-backed scheduled LoRA rows."""

    item = _lora_item(display_subtitle="Midna XL")
    service = PromptScheduledLoraService()

    scheduled = service.inline_scheduled_loras(
        prompt_text=r"<lora:characters\midna:1.0>, standing",
        document_projector=PromptDocumentProjector(),
        lora_catalog=_StaticPromptLoraCatalog((item,)),
    )

    assert scheduled == (
        PromptScheduledLora(
            prompt_name=r"characters\midna",
            backend_value=item.backend_value,
            display_name="CivitAI Midna - Midna XL",
            trained_words=("imp princess", "twili"),
            source="inline_prompt",
        ),
    )


def test_inline_scheduled_loras_ignore_uncataloged_loras() -> None:
    """Inline LoRAs without catalog metadata should not offer trigger words."""

    scheduled = PromptScheduledLoraService().inline_scheduled_loras(
        prompt_text=r"<lora:unknown:1.0>",
        document_projector=PromptDocumentProjector(),
        lora_catalog=_StaticPromptLoraCatalog(()),
    )

    assert scheduled == ()


def test_inline_scheduled_loras_dedupe_by_backend_value() -> None:
    """Repeated inline LoRA tokens should produce one effective scheduled row."""

    item = _lora_item()

    scheduled = PromptScheduledLoraService().inline_scheduled_loras(
        prompt_text=r"<lora:characters\midna:1.0>, <lora:characters\midna:0.5>",
        document_projector=PromptDocumentProjector(),
        lora_catalog=_StaticPromptLoraCatalog((item,)),
    )

    assert len(scheduled) == 1
    assert scheduled[0].backend_value == item.backend_value


def test_trigger_word_suggestions_skip_empty_words_and_dedupe_candidates() -> None:
    """Trigger suggestion generation should emit deterministic unique rows."""

    scheduled = (
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Midna XL",
            trained_words=("imp princess", "imp_princess", "", "twili"),
            source="inline_prompt",
        ),
    )

    suggestions = PromptScheduledLoraService().trigger_word_suggestions(
        scheduled_loras=scheduled,
        prefix="imp_",
    )

    assert [(row.trigger_word, row.lora_display_name) for row in suggestions] == [
        ("imp princess", "Midna XL")
    ]


def test_trigger_word_suggestions_prefer_first_lora_for_duplicate_trigger() -> None:
    """Duplicate trigger words across LoRAs should keep the first effective LoRA."""

    first = PromptScheduledLora(
        prompt_name="first",
        backend_value="first.safetensors",
        display_name="First LoRA",
        trained_words=("sparkle",),
        source="cube_field",
    )
    second = PromptScheduledLora(
        prompt_name="second",
        backend_value="second.safetensors",
        display_name="Second LoRA",
        trained_words=("sparkle",),
        source="graph_effective",
    )

    suggestions = PromptScheduledLoraService().trigger_word_suggestions(
        scheduled_loras=(first, second),
        prefix="sp",
    )

    assert len(suggestions) == 1
    assert suggestions[0].lora_display_name == "First LoRA"


def test_trigger_word_suggestions_split_comma_separated_civit_words() -> None:
    """Autocomplete should suggest comma-separated CivitAI trained words separately."""

    scheduled = (
        PromptScheduledLora(
            prompt_name="ranni",
            backend_value="ranni.safetensors",
            display_name="Ranni XL",
            trained_words=("ranni elden ring, witch hat, blue skin",),
            source="inline_prompt",
        ),
    )

    suggestions = PromptScheduledLoraService().trigger_word_suggestions(
        scheduled_loras=scheduled,
        prefix="wi",
    )

    assert [(row.trigger_word, row.lora_display_name) for row in suggestions] == [
        ("witch hat", "Ranni XL")
    ]


def test_trigger_word_suggestions_ignore_empty_comma_parts() -> None:
    """Autocomplete comma splitting should skip blank CivitAI trigger parts."""

    scheduled = (
        PromptScheduledLora(
            prompt_name="ranni",
            backend_value="ranni.safetensors",
            display_name="Ranni XL",
            trained_words=("ranni,, , witch hat",),
            source="inline_prompt",
        ),
    )

    suggestions = PromptScheduledLoraService().trigger_word_suggestions(
        scheduled_loras=scheduled,
        prefix="w",
    )

    assert [(row.trigger_word, row.lora_display_name) for row in suggestions] == [
        ("witch hat", "Ranni XL")
    ]


def test_trigger_word_suggestions_dedupe_split_parts_by_replacement() -> None:
    """Split autocomplete trigger parts should still dedupe by replacement text."""

    scheduled = (
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Midna XL",
            trained_words=("imp princess, imp_princess",),
            source="inline_prompt",
        ),
    )

    suggestions = PromptScheduledLoraService().trigger_word_suggestions(
        scheduled_loras=scheduled,
        prefix="imp",
    )

    assert [(row.trigger_word, row.lora_display_name) for row in suggestions] == [
        ("imp princess", "Midna XL")
    ]


def test_trigger_word_index_matches_service_ordering_and_dedupe() -> None:
    """Cached trigger-word lookup should match direct service suggestions."""

    scheduled = (
        PromptScheduledLora(
            prompt_name="midna",
            backend_value="midna.safetensors",
            display_name="Midna XL",
            trained_words=("imp princess, imp_princess", "twili"),
            source="inline_prompt",
        ),
        PromptScheduledLora(
            prompt_name="ranni",
            backend_value="ranni.safetensors",
            display_name="Ranni XL",
            trained_words=("imp crown", "imp princess"),
            source="graph_effective",
        ),
    )
    service_results = PromptScheduledLoraService().trigger_word_suggestions(
        scheduled_loras=scheduled,
        prefix="imp_",
    )
    indexed_results = PromptTriggerWordIndex.build(scheduled).search("imp_")

    assert indexed_results == service_results
    assert [(row.trigger_word, row.lora_display_name) for row in indexed_results] == [
        ("imp princess", "Midna XL"),
        ("imp crown", "Ranni XL"),
    ]


def test_trigger_word_index_dedupes_after_prefix_filtering() -> None:
    """Indexed lookup should preserve service dedupe timing for escaped words."""

    scheduled = (
        PromptScheduledLora(
            prompt_name="cat",
            backend_value="cat.safetensors",
            display_name="Cat XL",
            trained_words=(r"cat \(animal\)", "cat (animal)"),
            source="inline_prompt",
        ),
    )

    indexed_results = PromptTriggerWordIndex.build(scheduled).search("cat (")

    assert [(row.trigger_word, row.lora_display_name) for row in indexed_results] == [
        ("cat (animal)", "Cat XL"),
    ]


def test_configured_trigger_words_for_insertion_preserves_provider_strings() -> None:
    """Trigger insertion should keep CivitAI-authored strings intact."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="ranni",
        backend_value="ranni.safetensors",
        display_name="Ranni XL",
        trained_words=("ranni elden ring, witch hat, blue skin",),
        source="inline_prompt",
    )

    insertion_text = (
        PromptScheduledLoraService().configured_trigger_words_for_insertion(
            scheduled_lora
        )
    )

    assert insertion_text == "ranni elden ring, witch hat, blue skin"


def test_configured_trigger_words_for_insertion_joins_provider_tuple_entries() -> None:
    """Multiple provider trained-word entries should be joined for insertion."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="ranni",
        backend_value="ranni.safetensors",
        display_name="Ranni XL",
        trained_words=("ranni elden ring, witch hat", "blue skin"),
        source="inline_prompt",
    )

    insertion_text = (
        PromptScheduledLoraService().configured_trigger_words_for_insertion(
            scheduled_lora
        )
    )

    assert insertion_text == "ranni elden ring, witch hat, blue skin"


def test_configured_trigger_words_for_insertion_skips_blank_provider_entries() -> None:
    """Blank provider entries should not create empty comma slots on insertion."""

    scheduled_lora = PromptScheduledLora(
        prompt_name="ranni",
        backend_value="ranni.safetensors",
        display_name="Ranni XL",
        trained_words=("", "  ", "blue skin"),
        source="inline_prompt",
    )

    insertion_text = (
        PromptScheduledLoraService().configured_trigger_words_for_insertion(
            scheduled_lora
        )
    )

    assert insertion_text == "blue skin"
