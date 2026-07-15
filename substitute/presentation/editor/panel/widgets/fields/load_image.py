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

"""Provide the image-specific thumbnail picker wrapper."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFileDialog, QWidget

from .thumbnail_picker_base import ThumbnailPickerBase


class ImagePicker(ThumbnailPickerBase):
    """Render the shared thumbnail picker for image-file selection."""

    imageSelected = Signal(str)
    imageClicked = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        thumbnail_size: int = 352,
        corner_radius: int = 8,
        default_folder: str = "",
        placeholder_image: str | None = None,
        button_padding: int = 24,
    ) -> None:
        """Initialize the image picker with shared thumbnail behavior."""

        super().__init__(
            parent=parent,
            thumbnail_size=thumbnail_size,
            corner_radius=corner_radius,
            default_folder=default_folder,
            placeholder_image=placeholder_image,
            button_padding=button_padding,
            browse_button_text="Browse Files",
        )
        self.button.clicked.connect(self.pick_image)

    def handle_thumbnail_click(self) -> None:
        """Emit the current file path when the thumbnail is clicked."""

        if self._current_file_path:
            self.imageClicked.emit(self._current_file_path)

    def pick_image(self) -> None:
        """Open the image picker dialog and update the selected thumbnail."""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Image",
            self.default_folder,
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if file_path:
            self.set_thumbnail(file_path)
            self.imageSelected.emit(file_path)
        elif self._placeholder_image_path:
            self.set_placeholder_image(self._placeholder_image_path)

    def set_thumbnail(self, file_path: str) -> None:
        """Display the selected image file or restore the placeholder state."""

        self._set_selected_file(file_path, QPixmap)
