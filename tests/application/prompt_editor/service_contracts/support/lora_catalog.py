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

"""Provide deterministic LoRA catalog boundaries for service contracts."""

from __future__ import annotations


from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)


class _StaticPromptWildcardCatalogGateway:
    """Return deterministic wildcard resolution rows for prompt syntax-service tests."""

    def __init__(
        self,
        resolutions_by_reference: dict[
            tuple[str, str, str | None],
            PromptWildcardResolution,
        ],
    ) -> None:
        """Store fixed wildcard resolution rows keyed by reference shape."""

        self._resolutions_by_reference = dict(resolutions_by_reference)
        self.calls: list[tuple[PromptWildcardReference, ...]] = []
        self.cache_revision = 0

    def bump_revision(self) -> None:
        """Advance the fake catalog revision used by syntax cache tests."""

        self.cache_revision += 1

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Record one batched lookup and return deterministic resolution data."""

        self.calls.append(references)
        return tuple(
            self._resolutions_by_reference.get(
                (
                    reference.identifier,
                    reference.wildcard_form,
                    reference.csv_column,
                ),
                PromptWildcardResolution(
                    identifier=reference.identifier,
                    wildcard_form=reference.wildcard_form,
                    csv_column=reference.csv_column,
                    exists=False,
                ),
            )
            for reference in references
        )

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard autocomplete suggestions."""

        _ = (prefix, limit)
        return ()


class _StaticPromptLoraCatalogService:
    """Return deterministic LoRA catalog rows for prompt syntax-service tests."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store fixed LoRA catalog rows."""

        self._items = items
        self.calls = 0
        self.cache_revision = 0

    def bump_revision(self) -> None:
        """Advance the fake catalog revision used by syntax cache tests."""

        self.cache_revision += 1

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Record one catalog lookup and return fixed LoRA rows."""

        self.calls += 1
        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return fixed LoRA rows without recording a render-plan lookup."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Record one catalog lookup and return the matching LoRA row."""

        self.calls += 1
        normalized_prompt_name = _test_lora_lookup_key(prompt_name)
        bare_matches: list[PromptLoraCatalogItem] = []
        for item in self._items:
            if _test_lora_lookup_key(item.prompt_name) == normalized_prompt_name:
                return item
            if _test_lora_lookup_key(item.backend_value) == normalized_prompt_name:
                return item
            if "\\" not in prompt_name and "/" not in prompt_name:
                if item.collision_key == _test_lora_basename_key(prompt_name):
                    bare_matches.append(item)
        if len(bare_matches) == 1:
            return bare_matches[0]
        return None


class _FailingPromptLoraCatalogService:
    """Raise from LoRA lookup to exercise fallback renderer behavior."""

    cache_revision = "failing"

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return no picker rows for tests that do not exercise picker lookup."""

        return ()

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return no cached rows for failing lookup tests."""

        return ()

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Fail one catalog lookup with the requested prompt name in context."""

        raise RuntimeError(f"catalog unavailable for {prompt_name}")


class _BootstrapPromptLoraCatalogService(_StaticPromptLoraCatalogService):
    """Return non-authoritative LoRA misses for startup bootstrap tests."""

    def can_report_lora_absence(self) -> bool:
        """Return that catalog misses are not authoritative yet."""

        return False


def _lora_item(
    *,
    display_name: str,
    basename: str,
    prompt_name: str,
    collision_count: int = 1,
    model_page_url: str | None = None,
    display_subtitle: str | None = None,
) -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog item for application tests."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=display_subtitle,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=prompt_name.rsplit("\\", 1)[0] if "\\" in prompt_name else "",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=("trained token",),
        tags=("character",),
        model_page_url=model_page_url,
        collision_key=basename.casefold(),
        collision_count=collision_count,
        has_collision=collision_count > 1,
        search_text=" ".join((display_name, basename, prompt_name)).casefold(),
    )


def _test_lora_lookup_key(value: str) -> str:
    """Return an extensionless lookup key for test LoRA catalog rows."""

    normalized = value.replace("\\", "/").casefold()
    if normalized.endswith(".safetensors"):
        return normalized[: -len(".safetensors")]
    return normalized


def _test_lora_basename_key(value: str) -> str:
    """Return the extensionless basename lookup key for test LoRA rows."""

    return _test_lora_lookup_key(value).rsplit("/", maxsplit=1)[-1]
