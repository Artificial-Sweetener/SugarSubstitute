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

"""Tests for shared LoRA schedule text construction."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    DEFAULT_LORA_SCHEDULE_WEIGHT,
    PromptLoraCatalogItem,
    PromptLoraScheduleService,
)


def test_lora_schedule_text_uses_literal_default_weight() -> None:
    """New LoRA schedules should use the shared literal default weight."""

    item = _lora_item(prompt_name=r"illustrious\characters\Midna")

    text = PromptLoraScheduleService().schedule_text(item)

    assert DEFAULT_LORA_SCHEDULE_WEIGHT == "1.00"
    assert text == r"<lora:illustrious\characters\Midna:1.00>"


def test_lora_schedule_text_preserves_supplied_weight_text() -> None:
    """Autocomplete should be able to preserve the user's typed weight text."""

    item = _lora_item(prompt_name=r"illustrious\characters\Midna")

    text = PromptLoraScheduleService().schedule_text(item, weight_text="1.2")

    assert text == r"<lora:illustrious\characters\Midna:1.2>"


def test_lora_schedule_text_uses_default_for_blank_weight() -> None:
    """Blank explicit weights should fall back to the shared default."""

    item = _lora_item(prompt_name=r"illustrious\characters\Midna")

    text = PromptLoraScheduleService().schedule_text(item, weight_text="  ")

    assert text == r"<lora:illustrious\characters\Midna:1.00>"


def test_lora_schedule_text_uses_prompt_name_not_display_fields() -> None:
    """Schedule text should use the scheduler-safe prompt name only."""

    item = _lora_item(
        display_name="Friendly Midna",
        basename="raw_midna",
        prompt_name=r"illustrious\characters\safe_midna",
    )

    selection = PromptLoraScheduleService().schedule_selection(item)

    assert selection.item is item
    assert selection.weight_text == "1.00"
    assert (
        selection.replacement_text == r"<lora:illustrious\characters\safe_midna:1.00>"
    )
    assert "Friendly Midna" not in selection.replacement_text
    assert "raw_midna" not in selection.replacement_text


def _lora_item(
    *,
    display_name: str = "Midna",
    basename: str = "Midna",
    prompt_name: str = r"illustrious\characters\Midna",
) -> PromptLoraCatalogItem:
    """Return one LoRA catalog item for schedule service tests."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=r"illustrious\characters",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, basename, prompt_name)).casefold(),
    )
