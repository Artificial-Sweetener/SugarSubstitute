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

"""Provide representative autocomplete data shared by surface contracts."""

from __future__ import annotations

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
)


def sample_suggestions() -> tuple[PromptAutocompleteSuggestion, ...]:
    """Return stable suggestions used across autocomplete surface tests."""

    return (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
        PromptAutocompleteSuggestion("1girls", 3_424),
    )


def sample_lora(
    *,
    display_name: str = "CivitAI Midna",
    basename: str = "raw_midna",
    prompt_name: str = r"illustrious\characters\raw_midna",
) -> PromptLoraCatalogItem:
    """Return one stable LoRA catalog item for autocomplete tests."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=prompt_name.rsplit("\\", 1)[0] if "\\" in prompt_name else "",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=("character",),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, basename, prompt_name)).casefold(),
    )
