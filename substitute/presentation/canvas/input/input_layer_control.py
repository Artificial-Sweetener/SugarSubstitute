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

"""Compose the lower-corner Input mask-layer control."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon, TransparentToolButton  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.localization import (
    set_localized_accessible_name,
    set_localized_tooltip,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
    CANVAS_CHROME_SURFACE_BORDER_WIDTH,
    CANVAS_CHROME_SURFACE_PADDING,
)
from substitute.presentation.canvas.shared.canvas_control_frame import (
    CanvasControlFrame,
)
from substitute.presentation.canvas.shared.floating_canvas_surface import (
    floating_canvas_surface_stylesheet,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh

from .input_layer_settings import InputMaskLayerSettings
from .input_mask_layer_button import InputMaskLayerButton
from .input_tool_options_contracts import InputToolOptionsDocumentPort


class InputLayerControl(CanvasControlFrame):
    """Own mask-circle projection and one active layer settings surface."""

    geometryChanged = Signal()
    coverageEditRequested = Signal(object)

    def __init__(
        self,
        document: InputToolOptionsDocumentPort,
        parent: QWidget,
    ) -> None:
        """Build an initially collapsed control bound to current mask layers."""
        super().__init__(parent)
        self.setObjectName("InputLayerControl")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._document = document
        self._buttons: list[InputMaskLayerButton] = []
        self._settings_mask_id: UUID | None = None
        self._suppressed = False
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self._apply_intrinsic_geometry)

        self.settings = InputMaskLayerSettings(self)
        self.settings.hide()
        self.settings.closeRequested.connect(self.close_settings)
        self.settings.coverageEditRequested.connect(self._request_coverage_edit)
        self.close_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.close_button.setObjectName("InputLayerSettingsCloseButton")
        self.close_button.setFixedSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        set_localized_tooltip(self.close_button, "Close")
        set_localized_accessible_name(self.close_button, "Close")
        self.close_button.clicked.connect(self.close_settings)
        self.close_button.hide()

        self._button_layout = QHBoxLayout()
        self._button_layout.setContentsMargins(0, 0, 0, 0)
        self._button_layout.setSpacing(CANVAS_CHROME_GAP // 2)
        self._button_layout.addStretch(1)

        settings_row = QHBoxLayout()
        settings_row.setContentsMargins(0, 0, 0, 0)
        settings_row.setSpacing(0)
        settings_row.addWidget(self.settings)
        settings_row.addWidget(
            self.close_button,
            alignment=Qt.AlignmentFlag.AlignTop,
        )

        content_inset = (
            CANVAS_CHROME_SURFACE_PADDING - CANVAS_CHROME_SURFACE_BORDER_WIDTH
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            content_inset,
            content_inset,
            content_inset,
            content_inset,
        )
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.addLayout(settings_row)
        layout.addLayout(self._button_layout)

        document.toolContextChanged.connect(self.refresh)
        document.maskContentChanged.connect(self.refresh)
        self._apply_theme_style()
        connect_theme_refresh(self, self._apply_theme_style)
        self.refresh()

    def refresh(self, *_args: object) -> None:
        """Rebuild circle projection from authoritative current-composition masks."""
        layers = self._document.mask_layers()
        active_mask_id = self._document.active_mask_id()
        for button in self._buttons:
            self._button_layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()
        insert_at = max(0, self._button_layout.count() - 1)
        for layer in layers:
            color = QColor(layer.color) if layer.color is not None else QColor("white")
            button = InputMaskLayerButton(
                layer.mask_id,
                color,
                active=layer.mask_id == active_mask_id,
                parent=self,
            )
            button.activated.connect(self.open_settings)
            self._button_layout.insertWidget(insert_at, button)
            insert_at += 1
            self._buttons.append(button)
        if self._settings_mask_id is not None:
            selected = next(
                (layer for layer in layers if layer.mask_id == self._settings_mask_id),
                None,
            )
            if selected is None:
                self.settings.set_layer(None)
                self.close_settings()
            else:
                self.settings.set_layer(selected)
        self.setVisible(bool(layers) and not self._suppressed)
        self._synchronize_geometry()

    def set_suppressed(self, suppressed: bool) -> None:
        """Hide layer chrome while an exclusive canvas control owns input."""
        suppressed = bool(suppressed)
        if suppressed == self._suppressed:
            return
        self._suppressed = suppressed
        if suppressed:
            self.close_settings()
            self.hide()
            return
        self.refresh()

    def open_settings(self, mask_id: object) -> None:
        """Activate one mask circle and expose settings for that same layer."""
        if not isinstance(mask_id, UUID):
            return
        self._document.set_active_mask_id(mask_id)
        layer = next(
            (item for item in self._document.mask_layers() if item.mask_id == mask_id),
            None,
        )
        if layer is None:
            return
        self._settings_mask_id = mask_id
        self.settings.set_layer(layer)
        self.settings.show()
        self.close_button.show()
        self._synchronize_geometry()

    def close_settings(self) -> None:
        """Hide layer properties without changing the selected mask."""
        self._settings_mask_id = None
        self.settings.hide()
        self.close_button.hide()
        self._synchronize_geometry()

    def _request_coverage_edit(self, mask_id: object) -> None:
        """Close layer properties and relay one valid coverage-edit request."""
        if not isinstance(mask_id, UUID):
            return
        self.close_settings()
        self.coverageEditRequested.emit(mask_id)

    def _synchronize_geometry(self) -> None:
        """Apply current geometry and coalesce its post-layout correction."""
        self._apply_intrinsic_geometry()
        self._geometry_timer.start(0)

    def _apply_intrinsic_geometry(self) -> None:
        """Publish settled intrinsic size for lower-corner anchoring."""
        layout = self.layout()
        if layout is not None:
            layout.activate()
        self.adjustSize()
        self.updateGeometry()
        self.geometryChanged.emit()

    def _apply_theme_style(self, *_args: object) -> None:
        """Apply the canonical floating canvas surface material."""
        self.setStyleSheet(
            floating_canvas_surface_stylesheet("QFrame#InputLayerControl")
        )


__all__ = ["InputLayerControl"]
