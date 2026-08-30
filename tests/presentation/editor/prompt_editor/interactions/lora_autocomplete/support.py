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

"""Provide deterministic real-editor LoRA autocomplete collaborators."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.support.execution.runtime_support import (
    immediate_prompt_task_executor_factory,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)


class StaticPromptLoraCatalog:
    """Return deterministic LoRA catalog rows for real-editor interaction tests."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store the configured catalog rows."""

        self._items = items
        self.calls = 0

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured catalog rows."""

        self.calls += 1
        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return configured catalog rows without backend loading."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the catalog row matching one prompt name."""

        normalized_prompt_name = prompt_name.replace("\\", "/").casefold()
        for item in self._items:
            if item.prompt_name.replace("\\", "/").casefold() == normalized_prompt_name:
                return item
        return None


def create_lora_prompt_editor(
    *,
    parent: QWidget | None = None,
    loras: tuple[PromptLoraCatalogItem, ...],
) -> PromptEditor:
    """Create a prompt editor with LoRA syntax and catalog autocomplete enabled."""

    return PromptEditor(
        parent,
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({}),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        prompt_lora_catalog_service=StaticPromptLoraCatalog(loras),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
