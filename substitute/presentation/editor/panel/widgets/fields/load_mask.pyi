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

from __future__ import annotations

from typing import Any
from PySide6.QtWidgets import QWidget

from .thumbnail_picker_base import ThumbnailPickerBase

class MaskPicker(ThumbnailPickerBase):
    maskSelected: Any
    clicked: Any
    visualOpacityChanged: Any
    visualOpacityCommitted: Any
    opacity_control: Any

    def __init__(
        self,
        cube_alias: str,
        node_name: str,
        parent: QWidget | None = ...,
        thumbnail_size: int = ...,
        corner_radius: int = ...,
        default_folder: str = ...,
        placeholder_image: str | None = ...,
        button_padding: int = ...,
    ) -> None: ...
    def handle_thumbnail_click(self) -> None: ...
    def pick_mask(self) -> None: ...
    def set_mask_path(self, mask_path: str) -> None: ...
    def refresh_mask_path(self, mask_path: str) -> None: ...
    def set_visual_opacity(self, opacity: float) -> None: ...
    @staticmethod
    def _load_mask_pixmap_from_file_bytes(mask_path: str) -> Any: ...
