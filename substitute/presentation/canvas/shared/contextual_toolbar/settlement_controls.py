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

"""Present the canonical Contextual Toolbar approve-and-cancel controls."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon,
    PrimaryToolButton,
    TransparentToolButton,
)

from sugarsubstitute_shared.localization import ApplicationMessage
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    set_localized_accessible_name,
    set_localized_tooltip,
)
from substitute.presentation.canvas.shared.canvas_chrome_metrics import (
    CANVAS_CHROME_CONTROL_HEIGHT,
    CANVAS_CHROME_GAP,
)


class ContextualToolbarSettlementControls(QWidget):
    """Own the standard check-left and cancel-right settlement pattern."""

    applyRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build icon-only controls with localized accessible semantics."""

        super().__init__(parent)
        self.apply_button = PrimaryToolButton(FluentIcon.ACCEPT, self)
        self.cancel_button = TransparentToolButton(FluentIcon.CLOSE, self)
        self.apply_button.setFixedSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        self.cancel_button.setFixedSize(
            CANVAS_CHROME_CONTROL_HEIGHT,
            CANVAS_CHROME_CONTROL_HEIGHT,
        )
        _bind_semantics(self.apply_button, app_text("Apply"))
        _bind_semantics(self.cancel_button, app_text("Cancel"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(CANVAS_CHROME_GAP, 0, 0, 0)
        layout.setSpacing(CANVAS_CHROME_GAP // 2)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.cancel_button)

        self.apply_button.clicked.connect(self.applyRequested.emit)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)


def _bind_semantics(button: QWidget, message: ApplicationMessage) -> None:
    """Bind one icon-only button to localized tooltip and accessibility copy."""

    set_localized_tooltip(button, message.source_text, *message.arguments)
    set_localized_accessible_name(button, message.source_text, *message.arguments)


__all__ = ["ContextualToolbarSettlementControls"]
