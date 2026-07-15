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

"""Schedule and coalesce output canvas projection work."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from PySide6.QtCore import QObject, QTimer

from substitute.presentation.ui_load_activity import (
    default_prompt_projection_ui_load_activity,
)

_DEFAULT_INTERVAL_MS = 16
_DEFAULT_ACTIVE_PROMPT_INTERVAL_MS = 33


class ProjectionReason(str, Enum):
    """Describe why an output canvas projection was requested."""

    GENERATED_OUTPUT = "generated_output"
    USER_SELECTED_OUTPUT = "user_selected_output"
    WORKFLOW_ACTIVATED = "workflow_activated"
    SCENE_CHANGED = "scene_changed"
    SOURCE_CHANGED = "source_changed"


@dataclass(frozen=True, slots=True)
class _PendingProjection:
    """Store one coalesced projection request until the flush timer fires."""

    reason: ProjectionReason
    registered_image_id: UUID | None


class CanvasProjectionScheduler(QObject):
    """Coalesce background projection work while preserving user intent."""

    def __init__(
        self,
        *,
        project_workflow: Callable[[str, UUID | None], None],
        active_workflow_id: Callable[[], str],
        output_canvas_visible: Callable[[], bool],
        parent: QObject | None = None,
        interval_ms: int = _DEFAULT_INTERVAL_MS,
        idle_interval_ms: int | None = None,
        active_prompt_interval_ms: int = _DEFAULT_ACTIVE_PROMPT_INTERVAL_MS,
        prompt_interaction_active: Callable[[], bool] | None = None,
        prompt_interaction_elapsed_ms: Callable[[], float | None] | None = None,
        output_activity_marker: Callable[[str], None] | None = None,
    ) -> None:
        """Capture projection callbacks and initialize the GUI-thread timer."""

        super().__init__(parent)
        self._project_workflow = project_workflow
        self._active_workflow_id = active_workflow_id
        self._output_canvas_visible = output_canvas_visible
        self._prompt_interaction_active = (
            prompt_interaction_active or _prompt_interaction_inactive
        )
        self._prompt_interaction_elapsed_ms = (
            prompt_interaction_elapsed_ms or _prompt_interaction_elapsed_unknown
        )
        self._output_activity_marker = (
            output_activity_marker or _default_output_activity_marker
        )
        self._idle_interval_ms = max(
            0,
            int(interval_ms if idle_interval_ms is None else idle_interval_ms),
        )
        self._active_prompt_interval_ms = max(0, int(active_prompt_interval_ms))
        self._pending_generated: dict[str, UUID | None] = {}
        self._pending_deferred: dict[str, _PendingProjection] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._idle_interval_ms)
        self._timer.timeout.connect(self.flush)

    def request_projection(
        self,
        workflow_id: str,
        *,
        reason: ProjectionReason,
        registered_image_id: UUID | None = None,
    ) -> None:
        """Request projection for one workflow according to priority policy."""

        if reason is ProjectionReason.USER_SELECTED_OUTPUT:
            self._pending_generated.pop(workflow_id, None)
            self._pending_deferred.pop(workflow_id, None)
            self._project_workflow(workflow_id, registered_image_id)
            self._mark_output_activity(f"canvas_projection_{reason.value}")
            return

        if reason is ProjectionReason.GENERATED_OUTPUT:
            self._pending_generated[workflow_id] = registered_image_id
        else:
            self._pending_deferred[workflow_id] = _PendingProjection(
                reason=reason,
                registered_image_id=registered_image_id,
            )
        if self._can_project_pending(workflow_id):
            self._schedule_flush()

    def flush(self) -> None:
        """Project the active coalesced request when policy allows it."""

        active_workflow_id = self._active_workflow_id()
        if not self._can_project_pending(active_workflow_id):
            return
        has_pending = active_workflow_id in self._pending_generated
        deferred_projection = self._pending_deferred.pop(active_workflow_id, None)
        registered_image_id = self._pending_generated.pop(active_workflow_id, None)
        if active_workflow_id and has_pending:
            self._project_workflow(active_workflow_id, registered_image_id)
            self._mark_output_activity("generated_canvas_projection_flush")
        elif active_workflow_id and deferred_projection is not None:
            registered_image_id = deferred_projection.registered_image_id
            self._project_workflow(active_workflow_id, registered_image_id)
            self._mark_output_activity(
                f"canvas_projection_{deferred_projection.reason.value}_flush"
            )

    def flush_pending_for_workflow(self, workflow_id: str) -> None:
        """Force any pending projection for one workflow."""

        has_generated = workflow_id in self._pending_generated
        deferred_projection = self._pending_deferred.pop(workflow_id, None)
        if not has_generated and deferred_projection is None:
            return
        if has_generated:
            registered_image_id = self._pending_generated.pop(workflow_id)
            mark_reason = "generated_canvas_projection_flush"
        else:
            assert deferred_projection is not None
            registered_image_id = deferred_projection.registered_image_id
            mark_reason = f"canvas_projection_{deferred_projection.reason.value}_flush"
        self._project_workflow(workflow_id, registered_image_id)
        self._mark_output_activity(mark_reason)

    def discard_workflow(self, workflow_id: str) -> None:
        """Discard all pending projection work owned by one workflow."""

        self._pending_generated.pop(workflow_id, None)
        self._pending_deferred.pop(workflow_id, None)

    def rename_workflow(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Re-key pending projection work after a workflow ID changes."""

        if old_workflow_id == new_workflow_id:
            return
        if old_workflow_id in self._pending_generated:
            self._pending_generated[new_workflow_id] = self._pending_generated.pop(
                old_workflow_id
            )
        if old_workflow_id in self._pending_deferred:
            self._pending_deferred[new_workflow_id] = self._pending_deferred.pop(
                old_workflow_id
            )

    def _schedule_flush(self) -> None:
        """Start or tighten the projection timer for current prompt interaction."""

        interval_ms = self._current_interval_ms()
        self._timer.setInterval(interval_ms)
        if not self._timer.isActive():
            self._timer.start()
            return
        remaining_ms = self._timer.remainingTime()
        if remaining_ms < 0 or remaining_ms <= interval_ms:
            return
        self._timer.stop()
        self._timer.start(interval_ms)

    def _can_project_pending(self, workflow_id: str) -> bool:
        """Return whether coalesced projection should run now."""

        return bool(
            workflow_id
            and workflow_id == self._active_workflow_id()
            and self._output_canvas_visible()
        )

    def _current_interval_ms(self) -> int:
        """Return the projection interval for current prompt-interaction activity."""

        if self._is_prompt_interaction_active():
            return self._active_prompt_interval_ms
        return self._idle_interval_ms

    def _is_prompt_interaction_active(self) -> bool:
        """Call the prompt activity predicate defensively for scheduling."""

        return bool(self._prompt_interaction_active())

    def _mark_output_activity(self, reason: str) -> None:
        """Record completed canvas projection work for prompt scheduling."""

        self._output_activity_marker(reason)


def _prompt_interaction_inactive() -> bool:
    """Return the default prompt-interaction inactive state."""

    return False


def _prompt_interaction_elapsed_unknown() -> float | None:
    """Return no elapsed prompt-interaction timing when no tracker is installed."""

    return None


def _default_output_activity_marker(reason: str) -> None:
    """Mark default presentation load after canvas projection work lands."""

    default_prompt_projection_ui_load_activity().mark_output_activity(reason=reason)


__all__ = [
    "CanvasProjectionScheduler",
    "ProjectionReason",
]
