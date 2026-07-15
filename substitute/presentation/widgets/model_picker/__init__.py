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

"""Expose reusable metadata-backed model picker widgets."""

from __future__ import annotations

from substitute.presentation.widgets.model_picker.model_picker_geometry import (
    MODEL_PICKER_POPUP_HEIGHT,
    MODEL_PICKER_POPUP_MARGIN,
    MODEL_PICKER_POPUP_MIN_HEIGHT,
    MODEL_PICKER_POPUP_MIN_WIDTH,
    MODEL_PICKER_POPUP_WIDTH,
    ModelPickerPopupPlacement,
    ModelPickerPopupPlacementMode,
    model_picker_screen_available_geometry,
    resolve_model_picker_popup_placement,
)
from substitute.presentation.widgets.model_picker.model_picker_field import (
    ModelPickerField,
    ModelPickerThumbnailPreloadRoute,
)
from substitute.presentation.widgets.model_picker.model_picker_models import (
    ModelPickerItem,
    model_catalog_items_to_picker_items,
    model_picker_item_aspect_ratio,
    model_picker_items_from_catalog_items,
    model_picker_items_from_rich_choice_items,
    thumbnail_refs_from_model_variants,
)
from substitute.presentation.widgets.model_picker.model_picker_popup import (
    ModelPickerPopup,
)
from substitute.presentation.widgets.model_picker.model_picker_wall import (
    MODEL_PICKER_WALL_PROFILE,
    ModelPickerWallView,
    wall_items_for_model_picker_items,
)

__all__ = [
    "MODEL_PICKER_POPUP_HEIGHT",
    "MODEL_PICKER_POPUP_MARGIN",
    "MODEL_PICKER_POPUP_MIN_HEIGHT",
    "MODEL_PICKER_POPUP_MIN_WIDTH",
    "MODEL_PICKER_POPUP_WIDTH",
    "MODEL_PICKER_WALL_PROFILE",
    "ModelPickerItem",
    "ModelPickerField",
    "ModelPickerPopup",
    "ModelPickerPopupPlacement",
    "ModelPickerPopupPlacementMode",
    "ModelPickerThumbnailPreloadRoute",
    "ModelPickerWallView",
    "model_picker_screen_available_geometry",
    "model_catalog_items_to_picker_items",
    "model_picker_item_aspect_ratio",
    "model_picker_items_from_catalog_items",
    "model_picker_items_from_rich_choice_items",
    "resolve_model_picker_popup_placement",
    "thumbnail_refs_from_model_variants",
    "wall_items_for_model_picker_items",
]
