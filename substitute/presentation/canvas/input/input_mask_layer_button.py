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

"""Render one circular mask-layer affordance."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QToolButton, QWidget

from sugarsubstitute_shared.presentation.localization import (
    set_localized_accessible_name,
    set_localized_tooltip,
)

_BUTTON_SIZE = 36


class InputMaskLayerButton(QToolButton):
    """Expose one mask identity as a compact colored circle."""

    activated = Signal(object)

    def __init__(
        self,
        mask_id: UUID,
        color: QColor,
        *,
        active: bool,
        parent: QWidget,
    ) -> None:
        """Bind immutable layer identity and presentation color."""
        super().__init__(parent)
        self.mask_id = mask_id
        self.setObjectName("InputMaskLayerButton")
        self.setFixedSize(_BUTTON_SIZE, _BUTTON_SIZE)
        set_localized_tooltip(self, "Mask layer")
        set_localized_accessible_name(self, "Mask layer")
        border = "3px solid palette(highlight)" if active else "2px solid palette(mid)"
        self.setStyleSheet(
            "QToolButton#InputMaskLayerButton {"
            f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});"
            f"border: {border};"
            f"border-radius: {_BUTTON_SIZE // 2}px;"
            "}"
        )
        self.clicked.connect(lambda: self.activated.emit(self.mask_id))


__all__ = ["InputMaskLayerButton"]
