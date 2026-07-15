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

"""Schedule execution-driven GUI work on a Qt owner thread."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar, cast

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from shiboken6 import isValid

TItem = TypeVar("TItem")


@dataclass(frozen=True, slots=True)
class _ScheduledCallback:
    """Carry one delayed callback request through queued signal delivery."""

    delay_ms: int
    callback: Callable[[], None]
    reason: str

    def __post_init__(self) -> None:
        """Validate scheduler request fields."""

        _require_non_negative(self.delay_ms, field_name="delay_ms")
        _require_non_blank(self.reason, field_name="reason")


class QtUiScheduler(QObject):
    """Schedule UI callbacks through a Qt owner-thread entrypoint."""

    _schedule_requested = Signal(object)

    def __init__(self, receiver: QObject, parent: QObject | None = None) -> None:
        """Create a scheduler tied to a receiver lifetime."""

        super().__init__(parent or receiver)
        self._receiver = receiver
        self._destroyed = False
        self._schedule_requested.connect(
            self._schedule_on_owner_thread,
            Qt.ConnectionType.QueuedConnection,
        )
        self.destroyed.connect(self._mark_destroyed)
        receiver.destroyed.connect(self._mark_destroyed)

    def schedule(
        self,
        delay_ms: int,
        callback: Callable[[], None],
        *,
        reason: str,
    ) -> None:
        """Queue one delayed callback request for owner-thread scheduling."""

        scheduled = _ScheduledCallback(
            delay_ms=delay_ms,
            callback=callback,
            reason=reason,
        )
        if self._receiver_is_operational():
            self._schedule_requested.emit(scheduled)

    def schedule_chunked(
        self,
        items: Iterable[TItem],
        process_item: Callable[[TItem], None],
        *,
        chunk_size: int,
        delay_ms: int = 0,
        reason: str,
    ) -> None:
        """Process items in owner-thread chunks with a fixed item budget."""

        _require_positive(chunk_size, field_name="chunk_size")
        iterator = iter(items)

        def run_next_chunk() -> None:
            """Process one chunk and reschedule when work remains."""

            if not self._receiver_is_operational():
                return
            processed = 0
            while processed < chunk_size:
                try:
                    item = next(iterator)
                except StopIteration:
                    return
                process_item(item)
                processed += 1
            self.schedule(delay_ms, run_next_chunk, reason=reason)

        self.schedule(delay_ms, run_next_chunk, reason=reason)

    @Slot(object)
    def _schedule_on_owner_thread(self, scheduled: object) -> None:
        """Create the Qt timer from the receiver's owner thread."""

        if not self._receiver_is_operational():
            return
        typed_scheduled = cast(_ScheduledCallback, scheduled)
        QTimer.singleShot(typed_scheduled.delay_ms, typed_scheduled.callback)

    @Slot()
    def _mark_destroyed(self) -> None:
        """Remember that Qt has begun destroying this scheduler."""

        self._destroyed = True

    def _receiver_is_operational(self) -> bool:
        """Return whether scheduled callbacks can still target the receiver."""

        if self._destroyed:
            return False
        try:
            return bool(isValid(self._receiver)) and bool(isValid(self))
        except RuntimeError:
            return False
        except TypeError:
            return True


def _require_positive(value: int, *, field_name: str) -> None:
    """Reject non-positive chunk budgets."""

    if value <= 0:
        raise ValueError(f"{field_name} must be positive.")


def _require_non_negative(value: int, *, field_name: str) -> None:
    """Reject negative delay values."""

    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank scheduler labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "QtUiScheduler",
]
