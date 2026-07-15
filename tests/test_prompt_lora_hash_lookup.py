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

"""Tests for cache-only inline prompt LoRA hash lookup."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptLoraCatalogItem,
    PromptLoraCatalogLookupResult,
)
from substitute.application.recipes import (
    CachedPromptLoraHashLookup,
    MemoizedPromptLoraHashLookup,
)


class _PromptLoraCatalog:
    """Return deterministic prompt LoRA catalog rows."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store prompt LoRA rows."""

        self._items = items
        self.calls: list[str] = []

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured prompt LoRA rows."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return a prompt LoRA row by prompt name."""

        self.calls.append(prompt_name)
        for item in self._items:
            if item.prompt_name == prompt_name:
                return item
        return None


class _AuthoritativePromptLoraCatalog(_PromptLoraCatalog):
    """Return structured prompt LoRA lookups with a configurable authority flag."""

    def __init__(
        self,
        items: tuple[PromptLoraCatalogItem, ...],
        *,
        authoritative: bool,
    ) -> None:
        """Store prompt LoRA rows and the active authority state."""

        super().__init__(items)
        self._authoritative = authoritative

    def can_report_lora_absence(self) -> bool:
        """Return whether this fake catalog can prove LoRA resolution state."""

        return self._authoritative

    def lookup_lora(self, prompt_name: str) -> PromptLoraCatalogLookupResult:
        """Return a structured lookup result for one prompt LoRA name."""

        item = self.find_lora(prompt_name)
        return PromptLoraCatalogLookupResult(
            match_source="prompt_name" if item is not None else "miss",
            item=item,
        )


class _ModelHashLookup:
    """Return deterministic model hashes by kind and backend value."""

    def __init__(self, hashes: dict[tuple[str, str], str]) -> None:
        """Store configured hash rows."""

        self._hashes = hashes
        self.calls: list[tuple[str, str]] = []

    def hash_for_model_value(self, *, kind: str, value: str) -> str | None:
        """Return a configured hash for one model value."""

        self.calls.append((kind, value))
        return self._hashes.get((kind, value))


def test_prompt_lora_hash_lookup_resolves_catalog_backend_value() -> None:
    """Prompt LoRA lookup should use catalog backend values for hash lookup."""

    sha256 = "a" * 64
    catalog = _PromptLoraCatalog((_item(),))
    model_hash_lookup = _ModelHashLookup(
        {("loras", "characters/midna.safetensors"): sha256}
    )
    lookup = CachedPromptLoraHashLookup(
        prompt_lora_catalog=catalog,
        model_hash_lookup=model_hash_lookup,
    )

    assert lookup.hash_for_prompt_lora_name("characters/midna") == sha256.upper()
    assert catalog.calls == ["characters/midna"]
    assert model_hash_lookup.calls == [("loras", "characters/midna.safetensors")]
    assert (
        lookup.backend_value_for_prompt_lora_name("characters/midna")
        == "characters/midna.safetensors"
    )


def test_prompt_lora_hash_lookup_returns_none_for_unknown_prompt_name() -> None:
    """Unknown prompt LoRA names should not query model hashes."""

    catalog = _PromptLoraCatalog(())
    model_hash_lookup = _ModelHashLookup({})
    lookup = CachedPromptLoraHashLookup(
        prompt_lora_catalog=catalog,
        model_hash_lookup=model_hash_lookup,
    )

    assert lookup.hash_for_prompt_lora_name("missing") is None
    assert model_hash_lookup.calls == []


def test_prompt_lora_hash_lookup_requires_authority_for_structured_catalogs() -> None:
    """Structured LoRA catalog lookups should not canonicalize pending rows."""

    catalog = _AuthoritativePromptLoraCatalog((_item(),), authoritative=False)
    model_hash_lookup = _ModelHashLookup(
        {("loras", "characters/midna.safetensors"): "A" * 64}
    )
    lookup = CachedPromptLoraHashLookup(
        prompt_lora_catalog=catalog,
        model_hash_lookup=model_hash_lookup,
    )

    assert lookup.backend_value_for_prompt_lora_name("characters/midna") is None
    assert lookup.hash_for_prompt_lora_name("characters/midna") is None
    assert model_hash_lookup.calls == []


def test_prompt_lora_hash_lookup_returns_none_for_ineligible_model_hash() -> None:
    """Known prompt LoRAs without eligible model hashes should return none."""

    catalog = _PromptLoraCatalog((_item(),))
    model_hash_lookup = _ModelHashLookup({})
    lookup = CachedPromptLoraHashLookup(
        prompt_lora_catalog=catalog,
        model_hash_lookup=model_hash_lookup,
    )

    assert lookup.hash_for_prompt_lora_name("characters/midna") is None
    assert model_hash_lookup.calls == [("loras", "characters/midna.safetensors")]


def test_memoized_prompt_lora_hash_lookup_deduplicates_normalized_names() -> None:
    """Run-scoped prompt LoRA memoization should cache hits and misses."""

    catalog = _PromptLoraCatalog((_item(),))
    model_hash_lookup = _ModelHashLookup(
        {("loras", "characters/midna.safetensors"): "A" * 64}
    )
    delegate = CachedPromptLoraHashLookup(
        prompt_lora_catalog=catalog,
        model_hash_lookup=model_hash_lookup,
    )
    lookup = MemoizedPromptLoraHashLookup(delegate)

    assert lookup.hash_for_prompt_lora_name("characters/midna") == "A" * 64
    assert lookup.hash_for_prompt_lora_name(r"characters\midna.safetensors") == "A" * 64
    assert lookup.hash_for_prompt_lora_name("missing") is None
    assert lookup.hash_for_prompt_lora_name("missing.safetensors") is None
    assert catalog.calls == ["characters/midna", "missing"]
    assert model_hash_lookup.calls == [("loras", "characters/midna.safetensors")]


def _item() -> PromptLoraCatalogItem:
    """Return one deterministic prompt LoRA catalog item."""

    return PromptLoraCatalogItem(
        display_name="Midna",
        display_subtitle=None,
        prompt_name="characters/midna",
        backend_value="characters/midna.safetensors",
        relative_path="characters/midna.safetensors",
        folder="characters",
        basename="midna",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=("imp princess",),
        tags=(),
        model_page_url=None,
        collision_key="midna",
        collision_count=1,
        has_collision=False,
        search_text="midna",
    )
