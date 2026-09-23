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

"""Contracts for LoRA picker wall row projection and activation."""

from __future__ import annotations

from dataclasses import replace

from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptLoraPickerPopup,
    wall_items_for_loras,
)

from .support import _item, _item_with_basename, ensure_qapp
from tests.presentation.model_updates.support import update_proposal


def test_lora_picker_wall_uses_display_name_title_and_subtitle() -> None:
    """The wall title and subtitle should come from catalog display fields."""

    ensure_qapp()
    popup = PromptLoraPickerPopup(
        (
            _item_with_basename(
                "CivitAI Midna",
                "midna",
                basename="Midna",
                display_subtitle="v2.0",
            ),
        ),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )

    assert popup._view.items()[0].title == "CivitAI Midna"
    assert popup._view.items()[0].subtitle == "v2.0"


def test_lora_picker_wall_omits_missing_display_subtitle() -> None:
    """The wall should keep subtitle empty when the catalog has no subtitle."""

    wall_item = wall_items_for_loras((_item("Local Midna", "midna"),))[0]

    assert wall_item.title == "Local Midna"
    assert wall_item.subtitle is None


def test_lora_picker_popup_emits_catalog_item_from_shared_wall() -> None:
    """The picker should activate the catalog payload rendered by the shared wall."""

    ensure_qapp()
    item = _item("Mineru", "mineru")
    popup = PromptLoraPickerPopup(
        (item,),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    activated: list[object] = []
    popup.loraActivated.connect(activated.append)

    assert popup._view.activate_current() is True

    assert activated == [item]


def test_lora_picker_popup_set_loras_updates_rows_without_resetting_search() -> None:
    """Live LoRA metadata refresh should update an open popup in place."""

    ensure_qapp()
    popup = PromptLoraPickerPopup(
        (_item("Midna", "midna"),),
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    popup.set_search_text("mineru")

    popup.set_loras((_item("Mineru", "mineru"),))

    current_item = popup.current_item()
    assert popup.search_text() == "mineru"
    assert current_item is not None
    assert current_item.title == "Mineru"


def test_prompt_lora_picker_shows_and_opens_exact_update_family() -> None:
    """Prompt LoRA tiles share the same exact-hash badge as node model pickers."""

    ensure_qapp()
    sha256 = "a" * 64
    updates = ModelUpdatePickerBridge()
    item = replace(_item("Mineru", "mineru"), sha256=sha256)
    popup = PromptLoraPickerPopup(
        (item,),
        thumbnail_cache=PromptLoraThumbnailCache(),
        model_updates=updates,
    )
    requested: list[str] = []
    updates.familyRequested.connect(requested.append)

    assert popup._view.items()[0].corner_badge_icon is None
    updates.replace((update_proposal(sha256),))
    assert popup._view.items()[0].corner_badge_icon is not None
    popup._view.itemBadgeActivated.emit(popup._view.picker_items()[0])
    assert requested == [sha256]
