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

"""Own application-wide modal masking independently from dialog content."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import MessageBoxBase  # type: ignore[import-untyped]
from shiboken6 import isValid

from sugarsubstitute_shared.presentation.localization import set_localized_text
from substitute.presentation.dialogs.full_window_modal_titlebar_bridge import (
    FullWindowModalTitleBarBridge,
)

_FALLBACK_OWNER: QWidget | None = None
_FALLBACK_SIZE = (1200, 800)


class FullWindowModalBase(MessageBoxBase):  # type: ignore[misc]
    """Cover the complete outer application frame for one Fluent modal."""

    def __init__(self, parent: object | None = None) -> None:
        """Resolve the outer frame before QFluent creates its mask geometry."""

        owner = resolve_full_window_modal_owner(parent)
        self._modal_owner = owner
        super().__init__(owner)
        self.setModal(True)
        set_localized_text(self.yesButton, "OK")
        set_localized_text(self.cancelButton, "Cancel")
        self._titlebar_bridge = FullWindowModalTitleBarBridge(
            owner=owner,
            wash=self.windowMask,
            parent=self,
        )
        self.windowMask.installEventFilter(self._titlebar_bridge)
        owner.installEventFilter(self)
        self._sync_owner_geometry()

    @property
    def modal_owner(self) -> QWidget:
        """Return the outer widget whose complete surface this modal blocks."""

        return self._modal_owner

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Keep mask geometry and stacking synchronized with the outer frame."""

        if watched is self._modal_owner and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.WindowStateChange,
            QEvent.Type.ZOrderChange,
        }:
            self._sync_owner_geometry()
        return bool(super().eventFilter(watched, event))

    def showEvent(self, event: QShowEvent) -> None:
        """Synchronize full-frame coverage immediately before the fade-in."""

        self._sync_owner_geometry()
        super().showEvent(event)
        self.raise_()

    def _sync_owner_geometry(self) -> None:
        """Match the modal and its wash to the owner's complete client area."""

        owner = self._modal_owner
        if not isValid(owner):
            return
        self.setGeometry(owner.rect())
        self.windowMask.setGeometry(self.rect())
        if self.isVisible():
            self.raise_()


def resolve_full_window_modal_owner(parent: object | None) -> QWidget:
    """Resolve the outermost valid widget or a stable test/startup fallback."""

    candidate = parent if isinstance(parent, QWidget) and isValid(parent) else None
    if candidate is None:
        active_window = QApplication.activeWindow()
        candidate = active_window if isinstance(active_window, QWidget) else None
    if candidate is not None:
        while (ancestor := candidate.parentWidget()) is not None:
            candidate = ancestor
        return candidate
    return _fallback_owner()


def _fallback_owner() -> QWidget:
    """Return a persistent owner when no application frame exists yet."""

    global _FALLBACK_OWNER
    if _FALLBACK_OWNER is None or not isValid(_FALLBACK_OWNER):
        _FALLBACK_OWNER = QWidget()
        _FALLBACK_OWNER.resize(*_FALLBACK_SIZE)
    return _FALLBACK_OWNER


__all__ = ["FullWindowModalBase", "resolve_full_window_modal_owner"]
