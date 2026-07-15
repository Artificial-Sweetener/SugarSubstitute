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

"""Publish execution callbacks through Qt owner-thread signal delivery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QObject, Qt, Signal, Slot
from shiboken6 import isValid


@dataclass(frozen=True, slots=True)
class _QtPublication:
    """Carry one reason-tagged callback through Qt queued delivery."""

    callback: Callable[[], None]
    reason: str

    def __post_init__(self) -> None:
        """Reject blank publication reasons."""

        _require_non_blank(self.reason, field_name="reason")


class QtOwnerThreadDispatcher(QObject):
    """Dispatch execution callbacks onto a Qt object's owner thread."""

    _publication_requested = Signal(object)

    def __init__(
        self,
        receiver: QObject | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create a dispatcher tied to a receiver lifetime."""

        super().__init__(parent or receiver)
        self._receiver = receiver or self
        self._destroyed = False
        self._publication_requested.connect(
            self._deliver_publication,
            Qt.ConnectionType.QueuedConnection,
        )
        self.destroyed.connect(self._mark_destroyed)
        if receiver is not None:
            receiver.destroyed.connect(self._mark_destroyed)

    @property
    def is_destroyed(self) -> bool:
        """Return whether the dispatcher or receiver has begun destruction."""

        return self._destroyed or not self._receiver_is_valid()

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Queue one callback for owner-thread delivery."""

        publication = _QtPublication(callback=callback, reason=reason)
        if self.is_destroyed:
            return
        self._publication_requested.emit(publication)

    @Slot(object)
    def _deliver_publication(self, publication: object) -> None:
        """Invoke one queued publication if the receiver is still alive."""

        if self.is_destroyed:
            return
        typed_publication = cast(_QtPublication, publication)
        typed_publication.callback()

    @Slot()
    def _mark_destroyed(self) -> None:
        """Remember that Qt has begun destroying the receiver boundary."""

        self._destroyed = True

    def _receiver_is_valid(self) -> bool:
        """Return whether the wrapped Qt receiver can still accept callbacks."""

        try:
            return bool(isValid(self._receiver)) and bool(isValid(self))
        except RuntimeError:
            return False
        except TypeError:
            return True


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank publication labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "QtOwnerThreadDispatcher",
]
