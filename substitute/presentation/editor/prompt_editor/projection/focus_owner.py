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

"""Own mounted projection focus-host lifecycle and focus queries."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget


class PromptProjectionFocusOwner(QObject):
    """Coordinate surface focus presentation with an optional shell focus host."""

    def __init__(
        self,
        *,
        surface: QWidget,
        prepare_source_line_chrome: Callable[[], None],
        schedule_caret_blink: Callable[[bool], None],
        parent: QObject,
    ) -> None:
        """Bind focus lifecycle effects to the mounted projection surface."""

        super().__init__(parent)
        self._surface = surface
        self._prepare_source_line_chrome = prepare_source_line_chrome
        self._schedule_caret_blink = schedule_caret_blink
        self._focus_host: QWidget | None = None

    @property
    def focus_host(self) -> QWidget | None:
        """Return the shell widget currently supplying focus state."""

        return self._focus_host

    def attach(self, focus_host: QWidget) -> None:
        """Observe one shell widget as the authoritative focus host."""

        if self._focus_host is focus_host:
            return
        if self._focus_host is not None:
            self._focus_host.removeEventFilter(self)
        self._focus_host = focus_host
        focus_host.installEventFilter(self)
        self._schedule_caret_blink(False)

    def ensure_pointer_focus(self) -> None:
        """Restore pointer interaction focus to the mounted focus owner."""

        focus_owner = self._focus_host or self._surface
        if not focus_owner.hasFocus():
            focus_owner.setFocus(Qt.FocusReason.MouseFocusReason)

    def focus_owner_has_focus(self) -> bool:
        """Return whether source-line focus presentation should be active."""

        return (self._focus_host or self._surface).hasFocus()

    def caret_focus_owner_has_focus(self) -> bool:
        """Return whether the surface or its shell parent owns caret focus."""

        focus_owner = self._focus_host or self._surface.parentWidget() or self._surface
        return focus_owner.hasFocus()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Synchronize caret presentation with focus-host lifecycle events."""

        if watched is not self._focus_host:
            return False
        event_type = event.type()
        if event_type == QEvent.Type.FocusIn:
            self._refresh_focus_presentation(reset_cycle=True)
        elif event_type in {QEvent.Type.FocusOut, QEvent.Type.Hide, QEvent.Type.Show}:
            self._refresh_focus_presentation(reset_cycle=False)
        return False

    def _refresh_focus_presentation(self, *, reset_cycle: bool) -> None:
        """Refresh source chrome and resolve caret blinking after focus changes."""

        self._prepare_source_line_chrome()
        self._schedule_caret_blink(reset_cycle)


__all__ = ["PromptProjectionFocusOwner"]
