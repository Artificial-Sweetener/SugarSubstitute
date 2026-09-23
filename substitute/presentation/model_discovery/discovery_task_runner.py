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

"""Run model-discovery operations on one reusable controller-owned Qt thread."""

from __future__ import annotations

from collections.abc import Callable
import logging
from threading import Event
from typing import cast

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

_LOGGER = logging.getLogger(__name__)


class DiscoveryCancellation:
    """Expose independent cancellation for one queued discovery operation."""

    def __init__(self) -> None:
        """Create a thread-safe cancellation flag."""

        self._event = Event()

    def cancel(self) -> None:
        """Request that the current operation stop at its next boundary."""

        self._event.set()

    def is_cancelled(self) -> bool:
        """Report whether the owning modal or controller was closed."""

        return self._event.is_set()


class _DiscoveryTask(QObject):
    """Execute one requested operation without replacing the task thread."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    @Slot(object, str)
    def run(self, work: object, operation: str) -> None:
        """Publish the result or actionable failure before releasing the operation."""

        try:
            value = cast(Callable[[], object], work)()
        except Exception as error:
            _LOGGER.exception("Model suggestion operation failed: %s", operation)
            self.failed.emit(str(error) or type(error).__name__)
        else:
            self.succeeded.emit(value)
        finally:
            self.finished.emit()


class DiscoveryTaskRunner(QObject):
    """Retain one native thread across repeated discovery-modal presentations."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()
    _dispatch = Signal(object, str)

    def __init__(self, parent: QObject) -> None:
        """Connect task delivery and shutdown to one stable task thread."""

        super().__init__(parent)
        self._thread = QThread(self)
        self._task = _DiscoveryTask()
        self._task.moveToThread(self._thread)
        self._dispatch.connect(self._task.run, Qt.ConnectionType.QueuedConnection)
        self._task.succeeded.connect(self.succeeded)
        self._task.failed.connect(self.failed)
        self._task.finished.connect(self._release_operation)
        self._thread.finished.connect(self._task.deleteLater)
        self._cancellation = DiscoveryCancellation()
        self._active = False
        self._closed = False
        self._thread.start()

    @property
    def running(self) -> bool:
        """Report whether one operation is queued or executing."""

        return self._active

    def start(self, work: Callable[[], object], operation: str) -> bool:
        """Queue a single operation without creating another native thread."""

        if self._active or self._closed:
            return False
        self._cancellation = DiscoveryCancellation()
        self._active = True
        self._dispatch.emit(work, operation)
        return True

    def current_cancellation(self) -> DiscoveryCancellation:
        """Return the cancellation flag owned by the active operation."""

        return self._cancellation

    def cancel(self) -> None:
        """Request cancellation without poisoning later modal presentations."""

        self._cancellation.cancel()

    def close(self) -> None:
        """Stop the persistent task thread during controller shutdown."""

        if self._closed:
            return
        self._closed = True
        self.cancel()
        self._thread.quit()
        if not self._thread.wait(5000):
            _LOGGER.warning("Model suggestion task did not stop before shutdown.")

    @Slot()
    def _release_operation(self) -> None:
        """Release one operation after its result or failure has been delivered."""

        self._active = False
        self.finished.emit()
