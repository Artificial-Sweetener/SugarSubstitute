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

"""Bound GUI-thread commits for prepared output images."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer

from substitute.application.workflows.output_canvas_state_service import (
    OutputImageRegistrationResult,
)
from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
    ProjectionReason,
)
from substitute.presentation.shell.output_image_commit_pipeline import (
    FailedOutputImagePreparation,
    PreparedOutputImage,
)
from substitute.presentation.ui_load_activity import (
    default_prompt_projection_ui_load_activity,
)


class PreparedOutputCommitQueue(QObject):
    """Commit prepared outputs in bounded GUI-thread batches."""

    def __init__(
        self,
        *,
        commit_prepared: Callable[
            [PreparedOutputImage], OutputImageRegistrationResult | None
        ],
        handle_failure: Callable[[FailedOutputImagePreparation], None],
        projection_scheduler: CanvasProjectionScheduler,
        parent: QObject | None = None,
        interval_ms: int = 0,
        batch_size: int = 1,
        output_activity_marker: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize FIFO commit queues and a GUI-thread drain timer."""

        super().__init__(parent)
        self._commit_prepared = commit_prepared
        self._handle_failure = handle_failure
        self._projection_scheduler = projection_scheduler
        self._output_activity_marker = (
            output_activity_marker or _default_output_activity_marker
        )
        self._prepared: deque[PreparedOutputImage] = deque()
        self._failed: deque[FailedOutputImagePreparation] = deque()
        self._batch_size = max(1, int(batch_size))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(0, int(interval_ms)))
        self._timer.timeout.connect(self.drain_once)

    def enqueue_prepared(self, output: PreparedOutputImage) -> None:
        """Queue one prepared output for GUI-thread commit."""

        self._prepared.append(output)
        self._schedule()

    def enqueue_failed(self, failure: FailedOutputImagePreparation) -> None:
        """Queue one failed preparation for GUI-thread error presentation."""

        self._failed.append(failure)
        self._schedule()

    def drain_once(self) -> None:
        """Commit one bounded batch and reschedule when work remains."""

        failed_pending_before = len(self._failed)
        prepared_pending_before = len(self._prepared)
        committed = 0
        while self._failed and committed < self._batch_size:
            failure = self._failed.popleft()
            self._handle_failure(failure)
            committed += 1
        while self._prepared and committed < self._batch_size:
            output = self._prepared.popleft()
            result = self._commit_prepared(output)
            if result is not None and result.projection_intent.should_schedule:
                self._projection_scheduler.request_projection(
                    result.projection_intent.workflow_id,
                    reason=ProjectionReason.GENERATED_OUTPUT,
                    registered_image_id=result.projection_intent.registered_image_id,
                )
            committed += 1
        if self._failed or self._prepared:
            self._schedule()
        if failed_pending_before or prepared_pending_before:
            self._output_activity_marker("output_commit_queue_drain")

    def pending_count(self) -> int:
        """Return total queued prepared and failed outputs."""

        return len(self._prepared) + len(self._failed)

    def _schedule(self) -> None:
        """Start the commit timer if it is idle."""

        if not self._timer.isActive():
            self._timer.start()


__all__ = ["PreparedOutputCommitQueue"]


def _default_output_activity_marker(reason: str) -> None:
    """Mark default presentation load after output commit work drains."""

    default_prompt_projection_ui_load_activity().mark_output_activity(reason=reason)
