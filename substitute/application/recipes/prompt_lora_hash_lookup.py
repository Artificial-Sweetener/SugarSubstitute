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

"""Resolve recipe-serializable hashes for inline prompt LoRA tokens."""

from __future__ import annotations

from typing import Protocol, cast

from substitute.application.recipes.lora_prompt_names import normalized_prompt_lora_name
from substitute.application.recipes.model_hash_lookup import RecipeModelHashLookup

_LORA_MODEL_KIND = "loras"


class PromptLoraCatalogItemLike(Protocol):
    """Describe the prompt LoRA catalog fields needed for hash lookup."""

    @property
    def backend_value(self) -> str:
        """Return the Comfy backend model value for the prompt LoRA."""


class PromptLoraCatalogLookup(Protocol):
    """Describe prompt LoRA catalog lookup needed for recipe serialization."""

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItemLike | None:
        """Return the catalog item matching one prompt LoRA reference."""


class PromptLoraHashLookup(Protocol):
    """Provide cache-backed recipe hashes for inline prompt LoRA tokens."""

    def hash_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return an eligible SHA-256 for one prompt LoRA name."""

    def backend_value_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return the Comfy backend value for one prompt LoRA name when known."""


class CachedPromptLoraHashLookup:
    """Resolve inline prompt LoRA hashes through catalog and metadata caches."""

    def __init__(
        self,
        *,
        prompt_lora_catalog: PromptLoraCatalogLookup,
        model_hash_lookup: RecipeModelHashLookup,
    ) -> None:
        """Store the cache-only collaborators used during recipe serialization."""

        self._prompt_lora_catalog = prompt_lora_catalog
        self._model_hash_lookup = model_hash_lookup

    def hash_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return an eligible SHA-256 for one prompt LoRA name."""

        backend_value = self.backend_value_for_prompt_lora_name(prompt_name)
        if backend_value is None:
            return None
        sha256 = self._model_hash_lookup.hash_for_model_value(
            kind=_LORA_MODEL_KIND,
            value=backend_value,
        )
        return sha256.upper() if sha256 is not None else None

    def backend_value_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return the Comfy backend value for one prompt LoRA name when known."""

        lookup_lora = getattr(self._prompt_lora_catalog, "lookup_lora", None)
        can_report_absence = getattr(
            self._prompt_lora_catalog,
            "can_report_lora_absence",
            None,
        )
        if callable(lookup_lora) and callable(can_report_absence):
            if not can_report_absence():
                return None
            diagnostic = lookup_lora(prompt_name)
            if _ambiguous_candidate_count(diagnostic) > 0:
                return None
            catalog_item = _diagnostic_item(diagnostic)
            return None if catalog_item is None else catalog_item.backend_value
        catalog_item = self._prompt_lora_catalog.find_lora(prompt_name)
        if catalog_item is None:
            return None
        return catalog_item.backend_value

    def create_session(self) -> PromptLoraHashLookup:
        """Return a memoized lookup backed by one model-hash session when available."""

        create_model_hash_session = getattr(
            self._model_hash_lookup,
            "create_session",
            None,
        )
        model_hash_lookup = (
            create_model_hash_session()
            if callable(create_model_hash_session)
            else self._model_hash_lookup
        )
        return MemoizedPromptLoraHashLookup(
            CachedPromptLoraHashLookup(
                prompt_lora_catalog=self._prompt_lora_catalog,
                model_hash_lookup=model_hash_lookup,
            )
        )


class MemoizedPromptLoraHashLookup:
    """Memoize prompt LoRA hash lookup results within one serialization request."""

    def __init__(self, delegate: PromptLoraHashLookup) -> None:
        """Store the delegated lookup and run-scoped memo tables."""

        self._delegate = delegate
        self._sha_by_normalized_name: dict[str, str | None] = {}
        self._backend_value_by_normalized_name: dict[str, str | None] = {}

    def hash_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return an eligible SHA-256 for one prompt LoRA name."""

        normalized_name = normalized_prompt_lora_name(prompt_name)
        if normalized_name not in self._sha_by_normalized_name:
            sha256 = self._delegate.hash_for_prompt_lora_name(prompt_name)
            self._sha_by_normalized_name[normalized_name] = (
                sha256.upper() if sha256 is not None else None
            )
        return self._sha_by_normalized_name[normalized_name]

    def backend_value_for_prompt_lora_name(self, prompt_name: str) -> str | None:
        """Return the Comfy backend value for one prompt LoRA name when known."""

        normalized_name = normalized_prompt_lora_name(prompt_name)
        if normalized_name not in self._backend_value_by_normalized_name:
            self._backend_value_by_normalized_name[normalized_name] = (
                self._delegate.backend_value_for_prompt_lora_name(prompt_name)
            )
        return self._backend_value_by_normalized_name[normalized_name]


def _diagnostic_item(diagnostic: object) -> PromptLoraCatalogItemLike | None:
    """Return a catalog item from a structured prompt LoRA diagnostic object."""

    item = getattr(diagnostic, "item", None)
    if item is not None:
        return cast(PromptLoraCatalogItemLike, item)
    result = getattr(diagnostic, "result", None)
    if result is None or not hasattr(result, "backend_value"):
        return None
    return cast(PromptLoraCatalogItemLike, result)


def _ambiguous_candidate_count(diagnostic: object) -> int:
    """Return the ambiguity count from a structured prompt LoRA diagnostic object."""

    value = getattr(diagnostic, "ambiguous_candidate_count", 0)
    return value if isinstance(value, int) else 0


__all__ = [
    "CachedPromptLoraHashLookup",
    "MemoizedPromptLoraHashLookup",
    "PromptLoraHashLookup",
]
