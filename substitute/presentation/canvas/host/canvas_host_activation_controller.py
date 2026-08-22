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

"""Own attached canvas selection and optional keyboard-focus transfer."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.canvas.host.canvas_host_state import CanvasHostState


class CanvasHostActivationController:
    """Apply one explicit activation contract to authoritative host state."""

    def __init__(
        self,
        *,
        state: CanvasHostState,
        synchronize_presentation: Callable[[], None],
        canvas_activated: Callable[[str], None],
    ) -> None:
        """Store the host state and projections affected by activation."""

        self._state = state
        self._synchronize_presentation = synchronize_presentation
        self._canvas_activated = canvas_activated
        self._focus_handoff: _CanvasFocusHandoff | None = None

    def activate(self, route_key: str, *, keyboard_focus: bool) -> bool:
        """Select an attached canvas and optionally transfer keyboard focus."""

        self._cancel_focus_handoff()
        entry = self._state.entry(route_key)
        if entry is None or not entry.selectable:
            return False
        self._state.select(route_key)
        self._synchronize_presentation()
        self._canvas_activated(route_key)
        if keyboard_focus:
            handoff = _CanvasFocusHandoff(
                state=self._state,
                route_key=route_key,
                widget=entry.page.widget,
                finished=self._clear_focus_handoff,
            )
            self._focus_handoff = handoff
            handoff.start()
        return True

    def _cancel_focus_handoff(self) -> None:
        """Release any older keyboard-focus intent before a new activation."""

        handoff = self._focus_handoff
        if handoff is not None:
            handoff.stop()

    def _clear_focus_handoff(self, handoff: _CanvasFocusHandoff) -> None:
        """Forget a completed handoff without disturbing a newer one."""

        if self._focus_handoff is handoff:
            self._focus_handoff = None


class _CanvasFocusHandoff(QObject):
    """Preserve explicit canvas focus until later user intent supersedes it."""

    _USER_INTENT_EVENTS = frozenset(
        {
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.TabletPress,
            QEvent.Type.TouchBegin,
            QEvent.Type.Wheel,
        }
    )

    def __init__(
        self,
        *,
        state: CanvasHostState,
        route_key: str,
        widget: QWidget,
        finished: Callable[[_CanvasFocusHandoff], None],
    ) -> None:
        """Store the authoritative route and target for one focus intent."""

        application = QApplication.instance()
        super().__init__(application)
        self._application = application
        self._state = state
        self._route_key = route_key
        self._widget = widget
        self._finished = finished
        self._active = False
        self._restore_queued = False
        widget.destroyed.connect(self._target_destroyed)

    def start(self) -> None:
        """Begin guarding focus through deferred same-intent projections."""

        if self._active:
            return
        self._active = True
        application = self._application
        if application is not None:
            application.installEventFilter(self)
        self._restore_focus()

    def stop(self) -> None:
        """Release this handoff after superseding user or lifecycle intent."""

        if not self._active:
            return
        self._active = False
        application = self._application
        if application is not None:
            application.removeEventFilter(self)
        self._finished(self)
        self.deleteLater()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Restore stolen focus while leaving every event undisrupted."""

        event_type = event.type()
        if event_type in self._USER_INTENT_EVENTS:
            self.stop()
            return False
        if event_type == QEvent.Type.ApplicationDeactivate:
            self.stop()
            return False
        if event_type == QEvent.Type.FocusOut and isinstance(watched, QWidget):
            if self._belongs_to_target(watched):
                self._queue_focus_restore()
            return False
        if event_type != QEvent.Type.FocusIn or not isinstance(watched, QWidget):
            return False
        if self._belongs_to_target(watched):
            return False
        if watched.window() is not self._widget.window():
            self.stop()
            return False
        self._queue_focus_restore()
        return False

    def _queue_focus_restore(self) -> None:
        """Coalesce competing projections into one queued restoration."""

        if self._restore_queued:
            return
        self._restore_queued = True
        QTimer.singleShot(0, self._restore_focus)

    def _restore_focus(self) -> None:
        """Reassert focus while this route still owns the handoff."""

        self._restore_queued = False
        if not self._active:
            return
        if self._state.active_route_key != self._route_key:
            self.stop()
            return
        focus_widget = QApplication.focusWidget()
        if focus_widget is not None and self._belongs_to_target(focus_widget):
            return
        self._widget.setFocus(Qt.FocusReason.OtherFocusReason)

    def _belongs_to_target(self, widget: QWidget) -> bool:
        """Return whether focus already belongs to the target subtree."""

        return widget is self._widget or self._widget.isAncestorOf(widget)

    def _target_destroyed(self, _object: QObject | None = None) -> None:
        """Release the application filter when its target is destroyed."""

        self.stop()


__all__ = ["CanvasHostActivationController"]
