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

"""Contracts for LoRA picker thumbnail and path projection."""

from __future__ import annotations


from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraThumbnailVariant,
)
from substitute.domain.model_metadata import (
    BANNER_THUMBNAIL_ROLE,
    STANDARD_THUMBNAIL_ROLE,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    lora_item_aspect_ratio,
    wall_items_for_loras,
)

from .support import _item_with_basename


def test_lora_wall_uses_only_standard_thumbnail_variants() -> None:
    """The picker wall should not use banner variants for tile thumbnails."""

    item = _item_with_basename(
        "CivitAI Midna",
        "midna",
        basename="Midna",
        thumbnail_variants=(
            PromptLoraThumbnailVariant(
                size=128,
                storage_key="midna:standard:128",
                width=85,
                height=128,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=43520,
                role=STANDARD_THUMBNAIL_ROLE,
            ),
            PromptLoraThumbnailVariant(
                size=768,
                storage_key="midna:banner:768x160",
                width=768,
                height=160,
                content_format="sqthumb-qimage-argb32-premultiplied",
                byte_size=491520,
                role=BANNER_THUMBNAIL_ROLE,
            ),
        ),
    )

    wall_item = wall_items_for_loras((item,))[0]

    assert [variant.role for variant in wall_item.thumbnail_variants] == [
        STANDARD_THUMBNAIL_ROLE
    ]
    assert wall_item.thumbnail_variants[0].storage_key == "midna:standard:128"
    assert lora_item_aspect_ratio(item) == 85 / 128


def test_lora_wall_items_carry_relative_path_tooltips() -> None:
    """The LoRA wall should expose model relative paths as tile tooltips."""

    item = _item_with_basename(
        "CivitAI Midna",
        "midna",
        basename="Midna",
    )

    wall_item = wall_items_for_loras((item,))[0]

    assert wall_item.tooltip == "Folder/Midna.safetensors"
