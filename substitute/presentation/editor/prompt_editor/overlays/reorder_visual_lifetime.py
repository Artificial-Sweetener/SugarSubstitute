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

"""Bind floating reorder visuals to the overlay's native Qt lifetime."""

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget

from .reorder_overlay_visual_lifecycle import PromptReorderOverlayVisualLifecycleOwner


class PromptReorderVisualLifetime(QObject):
    """Translate overlay closure and destruction into owned visual transitions."""

    def __init__(
        self,
        overlay: QWidget,
        lifecycle: PromptReorderOverlayVisualLifecycleOwner,
        proxy: QWidget,
    ) -> None:
        """Keep external visual parenting separate from the overlay's lifetime."""
        super().__init__(overlay)
        self._lifecycle = lifecycle
        overlay.installEventFilter(self)
        overlay.destroyed.connect(proxy.deleteLater)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Settle closing visuals while keeping them alive for later Qt events."""
        if event.type() == QEvent.Type.Close:
            self._lifecycle.close()
        return super().eventFilter(watched, event)
