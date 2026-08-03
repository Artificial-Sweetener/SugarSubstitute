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

"""Provide the shared thumbnail-picker base used by image and mask pickers."""

from __future__ import annotations

import os
from typing import Callable

from sugarsubstitute_shared.localization import ApplicationText, app_text
from substitute.presentation.localization import LocalizedPushButton

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

try:
    from qfluentwidgets.common.font import setFont  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - test-stub fallback only

    def setFont(_widget: object, _font_size: int = 14, _weight: int = 50) -> None:
        """Provide a no-op font helper when qfluentwidgets font utilities are unavailable."""


from substitute.presentation.shell.chrome_style import connect_theme_refresh
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    ensure_fluent_tooltip_filter,
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.windows_long_paths import qt_filesystem_path

from .thumbnail_preview_surface import ThumbnailPreviewSurface

try:
    from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - lightweight test stubs

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True


class ThumbnailPickerBase(QWidget):
    """Render the shared thumbnail, caption, button, and placeholder behavior."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        thumbnail_size: int = 352,
        corner_radius: int = 8,
        default_folder: str = "",
        placeholder_image: str | None = None,
        button_padding: int = 24,
        browse_button_text: ApplicationText = app_text("Browse Files"),
    ) -> None:
        """Initialize the shared thumbnail-picker widget structure."""

        super().__init__(parent)
        self.setMouseTracking(True)

        self.thumbnail_size = thumbnail_size
        self.corner_radius = corner_radius
        self.default_folder = default_folder
        self.shadow_space = 12
        self.button_padding = button_padding
        self._current_file_path: str | None = None
        self._placeholder_image_path: str | None = None
        self._caption_tooltip_filter: FluentToolTipFilter | None = None
        self._live_preview: QWidget | None = None

        self.preview_surface = ThumbnailPreviewSurface(
            thumbnail_width=thumbnail_size,
            corner_radius=corner_radius,
            parent=self,
        )
        self.preview_surface.clicked.connect(self.handle_thumbnail_click)
        self.thumbnail = self.preview_surface.static_label

        self.caption = QLabel(self)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setFont(self.caption, 13)
        self.caption.setText("")
        self.caption.hide()
        self._caption_tooltip_filter = ensure_fluent_tooltip_filter(
            self.caption,
            self.caption,
            show_delay_ms=600,
            cursor_anchor=True,
        )

        self.button = LocalizedPushButton(browse_button_text, self)

        self._preview_layout = QVBoxLayout(self)
        self._preview_layout.setSpacing(6)
        self._preview_layout.addWidget(
            self.preview_surface,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.thumb_caption_spacer = QSpacerItem(
            0,
            -8,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._preview_layout.addSpacerItem(self.thumb_caption_spacer)
        self._preview_layout.addWidget(
            self.caption,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.addSpacerItem(
            QSpacerItem(
                0,
                0,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Minimum,
            )
        )
        h_layout.addWidget(self.button)
        h_layout.addSpacerItem(
            QSpacerItem(
                self.button_padding,
                0,
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Minimum,
            )
        )

        self._preview_layout.addLayout(h_layout)
        self.setLayout(self._preview_layout)

        self.setMinimumWidth(thumbnail_size + self.shadow_space + 32)
        self.setStyleSheet("background: transparent;")
        self._apply_theme_styles()
        connect_theme_refresh(self, self._apply_theme_styles)

        if placeholder_image is not None:
            self.set_placeholder_image(placeholder_image)
        else:
            self.thumbnail.clear()
            self.caption.setText("")

    def handle_thumbnail_click(self) -> None:
        """Handle a thumbnail click in the concrete picker."""

    def set_default_folder(self, folder_path: str) -> None:
        """Set the default directory used by file dialogs."""

        self.default_folder = folder_path

    def set_placeholder_image(self, image_path: str) -> None:
        """Display the configured placeholder image and clear selected-path state."""

        self._remove_live_preview()
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self._apply_display_pixmap(pixmap, caption_text="", tooltip_text="")
            self._placeholder_image_path = image_path
            self._current_file_path = None
            layout = self.layout()
            if layout is not None:
                layout.activate()
            return

        self.preview_surface.clear_static_content()
        self.caption.setText("")
        self.caption.setFixedWidth(self.thumbnail_size - 4)
        self.caption.hide()
        self._placeholder_image_path = None
        self._current_file_path = None

    def _restore_placeholder_or_clear(self) -> None:
        """Restore the placeholder image or clear the thumbnail when no placeholder exists."""

        if self._placeholder_image_path:
            self.set_placeholder_image(self._placeholder_image_path)
            return

        self.preview_surface.clear_static_content()
        self.caption.setText("")
        self.caption.setFixedWidth(self.thumbnail_size - 8)
        set_fluent_tooltip_text(self.caption, "")
        self.caption.hide()
        self._current_file_path = None

    def _set_selected_file(
        self,
        file_path: str,
        pixmap_loader: Callable[[str], QPixmap],
    ) -> None:
        """Update file state without replacing an authoritative live presentation."""

        if self._live_preview is not None:
            self._current_file_path = file_path or None
            self._apply_selected_file_caption(
                file_path,
                width=self.preview_surface.width(),
            )
            return
        self._remove_live_preview()
        pixmap = pixmap_loader(qt_filesystem_path(file_path))
        if pixmap.isNull():
            self._restore_placeholder_or_clear()
            return

        self._apply_display_pixmap(
            pixmap,
            caption_text=self._elided_file_caption(file_path),
            tooltip_text=file_path,
        )
        self._current_file_path = file_path
        layout = self.layout()
        if layout is not None:
            layout.activate()

    def set_live_preview(self, preview: QWidget) -> None:
        """Replace the file thumbnail with one responsive live preview widget."""
        if not isinstance(preview, QWidget):
            raise TypeError("preview must be a QWidget")
        self._remove_live_preview()
        self._live_preview = preview
        self.preview_surface.set_live_content(preview)
        self._preview_layout.activate()

    def live_preview(self) -> QWidget | None:
        """Return the currently mounted live preview widget."""
        return self._live_preview

    def _remove_live_preview(self) -> None:
        """Retire the current viewport before restoring file-thumbnail display."""
        preview = self._live_preview
        if preview is None:
            return
        self._live_preview = None
        self.preview_surface.remove_live_content()
        preview.close()
        preview.deleteLater()

    def _apply_display_pixmap(
        self,
        pixmap: QPixmap,
        *,
        caption_text: str,
        tooltip_text: str,
    ) -> None:
        """Apply the current rounded pixmap, caption, and tooltip text."""

        content_size = self.preview_surface.set_static_pixmap(pixmap)
        self.caption.setFixedWidth(content_size.width())
        self.caption.setText(caption_text)
        set_fluent_tooltip_text(self.caption, tooltip_text)
        self.caption.setVisible(bool(caption_text))

    def _apply_selected_file_caption(self, file_path: str, *, width: int) -> None:
        """Update file labeling while the live document remains authoritative."""

        self.caption.setFixedWidth(max(1, width))
        self.caption.setText(self._elided_file_caption(file_path))
        set_fluent_tooltip_text(self.caption, file_path)
        self.caption.setVisible(bool(file_path))

    def _elided_file_caption(self, file_path: str) -> str:
        """Return the historical bracketed filename within picker width."""

        filename = os.path.basename(file_path)
        return self.caption.fontMetrics().elidedText(
            f"[{filename}]",
            Qt.TextElideMode.ElideMiddle,
            self.thumbnail_size,
        )

    def current_file_path(self) -> str | None:
        """Return the current selected file path."""

        return self._current_file_path

    def _apply_theme_styles(self) -> None:
        """Reapply caption text color after theme changes."""

        self.caption.setStyleSheet(
            "color: #ffffff;" if isDarkTheme() else "color: #1d2329;"
        )
