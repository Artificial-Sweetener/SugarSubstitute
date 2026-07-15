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

"""Debounce execution requests on a Qt owner thread."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, QTimer, Slot
from shiboken6 import isValid


@dataclass(frozen=True, slots=True)
class _PendingDebounceCallback:
    """Carry one debounced callback and diagnostic reason."""

    callback: Callable[[], None]
    reason: str

    def __post_init__(self) -> None:
        """Reject blank debounce reasons."""

        _require_non_blank(self.reason, field_name="reason")


class QtDebouncer(QObject):
    """Coalesce repeated requests through a single owned Qt timer."""

    def __init__(
        self,
        *,
        interval_ms: int,
        parent: QObject | None = None,
    ) -> None:
        """Create a single-shot debouncer on the current Qt thread."""

        super().__init__(parent)
        _require_non_negative(interval_ms, field_name="interval_ms")
        self._owner_thread = QThread.currentThread()
        self._destroyed = False
        self._pending: _PendingDebounceCallback | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._deliver_due_callback)
        self.destroyed.connect(self._mark_destroyed)
        if parent is not None:
            parent.destroyed.connect(self._mark_destroyed)

    @property
    def is_pending(self) -> bool:
        """Return whether a callback is waiting for timer delivery."""

        return self._pending is not None and self._timer_is_active()

    def request(self, callback: Callable[[], None], *, reason: str) -> None:
        """Schedule the latest callback for debounced delivery."""

        self._ensure_owner_thread()
        self._pending = _PendingDebounceCallback(callback=callback, reason=reason)
        if not self._timer_is_operational():
            self._pending = None
            return
        self._timer.start()

    def flush(self, *, reason: str) -> bool:
        """Run the latest pending callback immediately."""

        self._ensure_owner_thread()
        _require_non_blank(reason, field_name="reason")
        pending = self._take_pending_callback()
        if pending is None:
            return False
        pending.callback()
        return True

    def cancel(self, *, reason: str) -> bool:
        """Drop the latest pending callback without running it."""

        self._ensure_owner_thread()
        _require_non_blank(reason, field_name="reason")
        pending = self._pending
        self._pending = None
        if self._timer_is_operational():
            self._timer.stop()
        return pending is not None

    @Slot()
    def _deliver_due_callback(self) -> None:
        """Deliver the latest callback when the timer fires."""

        pending = self._take_pending_callback()
        if pending is not None:
            pending.callback()

    @Slot()
    def _mark_destroyed(self) -> None:
        """Remember that Qt has begun destroying this debouncer."""

        self._destroyed = True
        self._pending = None

    def _take_pending_callback(self) -> _PendingDebounceCallback | None:
        """Clear and return the latest pending callback."""

        pending = self._pending
        self._pending = None
        if self._timer_is_operational():
            self._timer.stop()
        return pending

    def _timer_is_active(self) -> bool:
        """Return timer activity without surfacing deleted-wrapper errors."""

        if not self._timer_is_operational():
            return False
        try:
            return bool(self._timer.isActive())
        except RuntimeError:
            return False

    def _timer_is_operational(self) -> bool:
        """Return whether the owned Qt timer can still be used."""

        if self._destroyed:
            return False
        try:
            return bool(isValid(self._timer)) and bool(isValid(self))
        except RuntimeError:
            return False
        except TypeError:
            return True

    def _ensure_owner_thread(self) -> None:
        """Reject timer operations from non-owner threads."""

        if QThread.currentThread() is not self._owner_thread:
            raise RuntimeError("QtDebouncer must be used from its owner thread.")


def _require_non_negative(value: int, *, field_name: str) -> None:
    """Reject negative debounce intervals."""

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank debounce labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "QtDebouncer",
]
