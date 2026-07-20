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

"""Provide the mask-specific thumbnail picker wrapper."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFileDialog, QWidget

from sugarsubstitute_shared.presentation.localization import translate_application_text

from substitute.shared.logging.logger import get_logger, log_warning

from .thumbnail_picker_base import ThumbnailPickerBase

_LOGGER = get_logger("presentation.editor.panel.widgets.fields.load_mask")


class MaskPicker(ThumbnailPickerBase):
    """Render the shared thumbnail picker for mask-file selection."""

    maskSelected = Signal(str, str, str)
    clicked = Signal(str, str)

    def __init__(
        self,
        cube_alias: str,
        node_name: str,
        parent: QWidget | None = None,
        thumbnail_size: int = 352,
        corner_radius: int = 8,
        default_folder: str = "",
        placeholder_image: str | None = None,
        button_padding: int = 24,
    ) -> None:
        """Initialize the mask picker with cube and node routing metadata."""

        super().__init__(
            parent=parent,
            thumbnail_size=thumbnail_size,
            corner_radius=corner_radius,
            default_folder=default_folder,
            placeholder_image=placeholder_image,
            button_padding=button_padding,
        )
        self.cube_alias = cube_alias
        self.node_name = node_name
        self.button.clicked.connect(self.pick_mask)

    def handle_thumbnail_click(self) -> None:
        """Emit the cube/node payload when the thumbnail is clicked."""

        self.clicked.emit(self.cube_alias, self.node_name)

    def pick_mask(self) -> None:
        """Open the mask picker dialog and update the selected thumbnail."""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            translate_application_text("Choose Mask"),
            self.default_folder,
            translate_application_text("Images (*.png *.jpg *.jpeg *.bmp *.gif)"),
        )
        if file_path:
            self.set_mask_path(file_path)
            self.maskSelected.emit(self.cube_alias, self.node_name, file_path)
        elif self._placeholder_image_path:
            self.set_placeholder_image(self._placeholder_image_path)

    def set_mask_path(self, file_path: str) -> None:
        """Display the selected mask file or restore the placeholder state."""

        self._set_selected_file(file_path, lambda path: QPixmap.fromImage(QImage(path)))

    def refresh_mask_path(self, file_path: str) -> None:
        """Reload the selected mask from fresh bytes after same-path autosaves."""

        self._set_selected_file(file_path, self._load_mask_pixmap_from_file_bytes)

    @staticmethod
    def _load_mask_pixmap_from_file_bytes(file_path: str) -> QPixmap:
        """Return a pixmap loaded from current file bytes, bypassing path caches."""

        path = Path(file_path)
        try:
            image_bytes = path.read_bytes()
        except OSError as error:
            log_warning(
                _LOGGER,
                "Failed to read mask thumbnail bytes",
                exists=path.exists(),
                error_type=type(error).__name__,
            )
            return QPixmap()

        image = QImage()
        if not image.loadFromData(image_bytes):
            log_warning(
                _LOGGER,
                "Failed to decode mask thumbnail bytes",
                exists=path.exists(),
                byte_count=len(image_bytes),
            )
            return QPixmap()
        return QPixmap.fromImage(image)
