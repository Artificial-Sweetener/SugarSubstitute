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

"""Contracts for LoRA picker metadata context-menu actions."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptLoraPickerPopup,
    PromptLoraWallView,
)

from .support import (
    _MetadataActionHandler,
    _actions,
    _item,
    _item_with_basename,
    ensure_qapp,
)


def test_lora_wall_metadata_menu_action_opens_catalog_url() -> None:
    """The LoRA wall should use the shared metadata CivitAI action."""

    ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    wall = PromptLoraWallView(
        thumbnail_cache=PromptLoraThumbnailCache(),
        open_url=open_url,
    )
    item = _item_with_basename(
        "CivitAI Midna",
        "midna",
        basename="Midna",
        model_page_url="https://civitai.com/models/100?modelVersionId=200",
    )
    wall.set_loras((item,))
    picker_item = wall.picker_items()[0]

    target = wall._metadata_context_menu_target(picker_item)

    assert target is not None
    actions = _actions(wall._metadata_context_menu.menu_items_for_target(target))
    assert len(actions) == 1
    action = actions[0]
    assert action.label == "Go to CivitAI page"
    action.callback()
    assert opened_urls == ["https://civitai.com/models/100?modelVersionId=200"]


def test_lora_wall_omits_metadata_menu_action_without_url() -> None:
    """The LoRA wall should not expose metadata actions for local-only items."""

    ensure_qapp()
    wall = PromptLoraWallView(
        thumbnail_cache=PromptLoraThumbnailCache(),
        open_url=lambda _url: True,
    )
    wall.set_loras((_item("Local Midna", "midna"),))
    target = wall._metadata_context_menu_target(wall.picker_items()[0])

    assert target is not None
    assert wall._metadata_context_menu.menu_items_for_target(target) == ()


def test_lora_picker_popup_civitai_action_uses_injected_opener() -> None:
    """The LoRA picker popup should pass CivitAI actions to the injected opener."""

    ensure_qapp()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record opened URLs without launching a browser."""

        opened_urls.append(url)
        return True

    item = _item_with_basename(
        "CivitAI Midna",
        "midna",
        basename="Midna",
        model_page_url="https://civitai.com/models/100?modelVersionId=200",
    )
    popup = PromptLoraPickerPopup(
        (item,),
        thumbnail_cache=PromptLoraThumbnailCache(),
        open_url=open_url,
    )
    target = popup._view._metadata_context_menu_target(popup._view.picker_items()[0])

    assert target is not None
    actions = _actions(popup._view._metadata_context_menu.menu_items_for_target(target))
    assert len(actions) == 1
    action = actions[0]
    action.callback()
    assert opened_urls == ["https://civitai.com/models/100?modelVersionId=200"]


def test_lora_picker_popup_refresh_action_targets_lora_metadata() -> None:
    """LoRA picker refresh actions should target the selected LoRA identity."""

    ensure_qapp()
    handler = _MetadataActionHandler()
    item = _item_with_basename("CivitAI Midna", "midna", basename="Midna")
    popup = PromptLoraPickerPopup(
        (item,),
        thumbnail_cache=PromptLoraThumbnailCache(),
        metadata_action_handler=handler,
    )
    target = popup._view._metadata_context_menu_target(popup._view.picker_items()[0])

    assert target is not None
    actions = _actions(popup._view._metadata_context_menu.menu_items_for_target(target))
    assert [action.label for action in actions] == [
        "Refresh CivitAI metadata",
        "Set thumbnail from canvas",
    ]
    actions[0].callback()
    assert len(handler.refresh_targets) == 1
    refresh_target = handler.refresh_targets[0]
    assert getattr(refresh_target, "model_kind") == "loras"
    assert getattr(refresh_target, "backend_value") == "Folder/Midna.safetensors"
