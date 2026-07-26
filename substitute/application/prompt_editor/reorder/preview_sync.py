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

"""Own reorder preview sync revisions and publication eligibility."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewSyncContext:
    """Carry immutable facts needed for one preview sync decision."""

    gesture_id: int | None
    event_id: int | None
    pointer_active: bool
    dragged_segment_index: int | None
    base_drag_layout_ready: bool
    requires_immediate_drag_geometry: bool
    requires_initial_landing_shadow: bool


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewSyncState:
    """Expose preview-sync bookkeeping for diagnostics and focused tests."""

    revision: int
    pending_revision: int | None
    pending_reason: str | None
    active_reason: str | None
    last_applied_revision: int
    scheduler_active: bool


class PromptReorderPreviewScheduleMode(Enum):
    """Classify whether one requested sync must run immediately."""

    DEFERRED = auto()
    IMMEDIATE = auto()


class PromptReorderPreviewFlushDecision(Enum):
    """Classify one attempt to publish pending preview work."""

    NO_PENDING = auto()
    STALE = auto()
    RUN = auto()


class PromptReorderPreviewSyncPolicy:
    """Own pending, active, and last-published preview revision truth."""

    def __init__(self) -> None:
        """Initialize empty preview sync state."""

        self._revision = 0
        self._pending_revision: int | None = None
        self._pending_reason: str | None = None
        self._pending_context: PromptReorderPreviewSyncContext | None = None
        self._active_reason: str | None = None
        self._last_applied_revision = 0
        self._flush_revision: int | None = None
        self._flush_reason: str | None = None
        self._flush_context: PromptReorderPreviewSyncContext | None = None

    @property
    def active_reason(self) -> str | None:
        """Return the reason for work currently approved to publish."""

        return self._active_reason

    @property
    def pending_revision(self) -> int | None:
        """Return the newest revision waiting for publication."""

        return self._pending_revision

    @property
    def current_revision(self) -> int:
        """Return the monotonically increasing requested revision."""

        return self._revision

    @property
    def flush_revision(self) -> int | None:
        """Return the revision selected by the latest flush decision."""

        return self._flush_revision

    @property
    def flush_reason(self) -> str | None:
        """Return the pending reason selected by the latest flush decision."""

        return self._flush_reason

    @property
    def flush_context(self) -> PromptReorderPreviewSyncContext | None:
        """Return the context selected by the latest flush decision."""

        return self._flush_context

    @property
    def last_applied_revision(self) -> int:
        """Return the newest revision that completed publication."""

        return self._last_applied_revision

    def request(
        self,
        *,
        reason: str,
        context: PromptReorderPreviewSyncContext,
    ) -> PromptReorderPreviewScheduleMode:
        """Replace pending work with one newer revision."""

        self._revision += 1
        self._pending_revision = self._revision
        self._pending_reason = reason
        self._pending_context = context
        if context.requires_immediate_drag_geometry:
            return PromptReorderPreviewScheduleMode.IMMEDIATE
        return PromptReorderPreviewScheduleMode.DEFERRED

    def begin_flush(
        self,
        *,
        context: PromptReorderPreviewSyncContext | None = None,
    ) -> PromptReorderPreviewFlushDecision:
        """Consume pending work and decide whether its revision may publish."""

        pending_revision = self._pending_revision
        self._flush_revision = pending_revision
        self._flush_reason = self._pending_reason
        self._flush_context = context or self._pending_context
        self._pending_revision = None
        self._pending_reason = None
        self._pending_context = None
        if pending_revision is None:
            return PromptReorderPreviewFlushDecision.NO_PENDING
        if pending_revision <= self._last_applied_revision:
            return PromptReorderPreviewFlushDecision.STALE
        self._active_reason = self._flush_reason
        return PromptReorderPreviewFlushDecision.RUN

    def complete_flush(self, *, published: bool) -> None:
        """Finish one approved publication and advance truth only on success."""

        if published and self._flush_revision is not None:
            self._last_applied_revision = self._flush_revision
        self._active_reason = None

    def clear(self) -> None:
        """Forget pending and active preview sync state."""

        self._pending_revision = None
        self._pending_reason = None
        self._pending_context = None
        self._active_reason = None
        self._flush_revision = None
        self._flush_reason = None
        self._flush_context = None

    def replace_state(
        self,
        *,
        pending_revision: int | None,
        pending_reason: str | None,
        last_applied_revision: int | None,
    ) -> None:
        """Replace revision state for deterministic recovery and tests."""

        self._pending_revision = pending_revision
        self._pending_reason = pending_reason
        self._pending_context = None
        if last_applied_revision is not None:
            self._last_applied_revision = last_applied_revision

    def snapshot(self, *, scheduler_active: bool) -> PromptReorderPreviewSyncState:
        """Return one immutable diagnostic view of sync state."""

        return PromptReorderPreviewSyncState(
            revision=self._revision,
            pending_revision=self._pending_revision,
            pending_reason=self._pending_reason,
            active_reason=self._active_reason,
            last_applied_revision=self._last_applied_revision,
            scheduler_active=scheduler_active,
        )


__all__ = [
    "PromptReorderPreviewFlushDecision",
    "PromptReorderPreviewScheduleMode",
    "PromptReorderPreviewSyncContext",
    "PromptReorderPreviewSyncPolicy",
    "PromptReorderPreviewSyncState",
]
