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

"""Bridge execution task outcomes into Qt signal delivery."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar, cast

from PySide6.QtCore import QObject, Qt, Signal

from substitute.application.execution import TaskHandle, TaskOutcome

TResult = TypeVar("TResult")


class QtTaskOutcomeSignalBridge(QObject, Generic[TResult]):
    """Emit task outcomes through a Qt queued signal."""

    outcome_ready = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        """Create an unbound outcome bridge."""

        super().__init__(parent)

    def bind(
        self,
        handle: TaskHandle[TResult],
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Connect a callback and emit when the supplied handle completes."""

        _require_non_blank(reason, field_name="reason")
        self.outcome_ready.connect(
            lambda outcome: callback(cast(TaskOutcome[TResult], outcome)),
            Qt.ConnectionType.QueuedConnection,
        )
        handle.add_done_callback(
            lambda outcome: self.outcome_ready.emit(outcome),
            reason=reason,
        )


def _require_non_blank(value: str, *, field_name: str) -> None:
    """Reject blank bridge labels."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


__all__ = [
    "QtTaskOutcomeSignalBridge",
]
