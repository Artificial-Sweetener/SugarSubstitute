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

"""Own replaceable Contextual Toolbar page lifetime and intrinsic sizing."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import QApplication, QWidget

from .page import ContextualToolbarPage
from .content_motion import ContextualToolbarContentMotion

ContextualToolbarPageFactory = Callable[[QWidget], ContextualToolbarPage]


class ContextualToolbarContentHost(QWidget):
    """Mount one current page while its persistent surface morphs between pages."""

    geometryChanged = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Create an empty content host with one focused motion owner."""
        super().__init__(parent)
        self._content_id: str | None = None
        self._page: ContextualToolbarPage | None = None
        self._animated_size = QSize()
        self._focus_target: ContextualToolbarPage | None = None
        self._motion = ContextualToolbarContentMotion(
            host=self,
            current_size=lambda: QSize(self._animated_size),
            apply_size=self._apply_animated_size,
            mount_page=self._mount_page,
            release_page=self._release_page,
        )

    @property
    def page(self) -> ContextualToolbarPage | None:
        """Return the currently mounted page for focused interaction tests."""
        return self._page

    def sizeHint(self) -> QSize:  # noqa: N802
        """Return the current interpolated page geometry."""
        return QSize(self._animated_size)

    def set_content(
        self,
        content_id: str,
        factory: ContextualToolbarPageFactory,
    ) -> ContextualToolbarPage:
        """Morph to one stable content identity and return its live page."""
        if content_id == self._content_id and self._page is not None:
            return self._page
        outgoing = self._page
        focused = QApplication.focusWidget()
        transfer_focus = bool(
            self._focus_target is not None
            or (
                outgoing is not None
                and focused is not None
                and outgoing.isAncestorOf(focused)
            )
        )
        page = factory(self)
        self._content_id = content_id
        self._page = page
        page.geometryChanged.connect(self._page_geometry_changed)
        page.setGeometry(self.rect())
        if transfer_focus:
            self._focus_target = page
        if outgoing is None:
            self._motion.present(page)
        else:
            self._motion.replace(page)
        return page

    def clear(self) -> None:
        """Dispose mounted and transitioning content deterministically."""
        self._page = None
        self._content_id = None
        self._focus_target = None
        self._motion.clear()

    def settle_content_motion(self) -> None:
        """Settle content effects before the ancestor toolbar surface fades."""

        self._motion.settle(self._page)

    def resizeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Keep current and outgoing pages coincident during a crossfade."""
        super().resizeEvent(event)  # type: ignore[arg-type]
        for page in self.findChildren(ContextualToolbarPage):
            page.setGeometry(self.rect())

    def _page_geometry_changed(self) -> None:
        """Retarget current page geometry without replacing its identity."""
        page = self._page
        if page is not None:
            self._motion.retarget_current_size(page)

    def _apply_animated_size(self, size: QSize) -> None:
        """Publish one live geometry sample without forcing a layout loop."""
        normalized = QSize(max(0, size.width()), max(0, size.height()))
        if normalized == self._animated_size:
            return
        self._animated_size = normalized
        self.setMinimumSize(normalized)
        self.setMaximumSize(normalized)
        self.updateGeometry()
        self.geometryChanged.emit()

    @staticmethod
    def _release_page(page: ContextualToolbarPage) -> None:
        """Release one superseded page after it can no longer receive input."""
        page.setEnabled(False)
        page.hide()
        page.close()
        page.deleteLater()

    def _mount_page(self, page: ContextualToolbarPage) -> None:
        """Mount one page at the host-owned origin and transfer pending focus."""

        page.setGeometry(self.rect())
        page.raise_()
        page.show()
        if page is self._focus_target:
            self._focus_target = None
            self._focus_first_control(page)

    @staticmethod
    def _focus_first_control(page: ContextualToolbarPage) -> None:
        """Transfer focus to the first keyboard-capable control on a new page."""
        control = next(
            (
                child
                for child in page.findChildren(QWidget)
                if child.focusPolicy() is not Qt.FocusPolicy.NoFocus
                and child.isEnabled()
            ),
            None,
        )
        if control is not None:
            control.setFocus()


__all__ = ["ContextualToolbarContentHost", "ContextualToolbarPageFactory"]
