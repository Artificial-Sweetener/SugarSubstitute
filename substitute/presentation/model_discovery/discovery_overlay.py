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

"""Cover the owning shell with a contained model-discovery dialog."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QDialog, QWidget
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.full_window_modal import (
    resolve_full_window_modal_owner,
)
from sugarsubstitute_shared.presentation.full_window_modal_titlebar_bridge import (
    FullWindowModalTitleBarBridge,
)

_PANEL_WIDTH = 1040
_PANEL_HEIGHT = 600
_EDGE_GAP = 24


class ModelDiscoveryOverlay(QWidget):
    """Own the full-shell wash and center one reusable child dialog within it."""

    def __init__(self, *, owner: QWidget) -> None:
        """Resolve the outer frame and track its geometry without a new window."""

        host = resolve_full_window_modal_owner(owner)
        super().__init__(host)
        self._host = host
        self._dialog: QDialog | None = None
        self.setObjectName("ModelDiscoveryOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#ModelDiscoveryOverlay {"
            "background-color: rgba(0, 0, 0, 160); border: none;}"
        )
        self._titlebar_bridge = FullWindowModalTitleBarBridge(
            owner=host, wash=self, parent=self
        )
        self.installEventFilter(self._titlebar_bridge)
        host.installEventFilter(self)
        self.setGeometry(host.rect())
        self.hide()

    @property
    def modal_owner(self) -> QWidget:
        """Return the full application frame covered by the wash."""

        return self._host

    def attach(self, dialog: QDialog) -> None:
        """Make the gallery a child panel rather than a native dialog window."""

        if dialog.parentWidget() is not self:
            raise ValueError("Model discovery dialog must belong to its wash.")
        dialog.setWindowFlags(Qt.WindowType.Widget)
        dialog.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._dialog = dialog
        self._apply_panel_theme()
        self._center_dialog()

    def present(self) -> None:
        """Wash the full shell before revealing the child gallery."""

        if self._dialog is None:
            raise RuntimeError("Model discovery has no attached dialog.")
        self._apply_panel_theme()
        self.setGeometry(self._host.rect())
        self._center_dialog()
        self.show()
        self.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Keep the wash and centered gallery aligned with shell resize."""

        if watched is self._host and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.WindowStateChange,
        }:
            self.setGeometry(self._host.rect())
            self._center_dialog()
            if self.isVisible():
                self.raise_()
        return bool(super().eventFilter(watched, event))

    def _apply_panel_theme(self) -> None:
        """Match the retained gallery panel to the active Fluent theme."""

        dialog = self._dialog
        if dialog is None:
            return
        panel_color = "#202024" if isDarkTheme() else "#ffffff"
        border_color = "#45454a" if isDarkTheme() else "#d4d4d8"
        dialog.setStyleSheet(
            f"QDialog#{dialog.objectName()} {{"
            f"background-color: {panel_color}; border: 1px solid {border_color};"
            "border-radius: 18px;}"
        )

    def _center_dialog(self) -> None:
        """Fit the dialog to the host while retaining its gallery size."""

        dialog = self._dialog
        if dialog is None:
            return
        preferred_height = dialog.property("preferredPanelHeight")
        panel_height = (
            preferred_height
            if isinstance(preferred_height, int) and preferred_height > 0
            else _PANEL_HEIGHT
        )
        width = min(_PANEL_WIDTH, max(1, self.width() - 2 * _EDGE_GAP))
        height = min(panel_height, max(1, self.height() - 2 * _EDGE_GAP))
        dialog.resize(width, height)
        dialog.move((self.width() - width) // 2, (self.height() - height) // 2)


__all__ = ["ModelDiscoveryOverlay"]
