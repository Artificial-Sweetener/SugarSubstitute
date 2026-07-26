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

"""Own latest-wins reorder preview wake-up policy without Qt."""

from __future__ import annotations

from enum import Enum, auto


class PromptReorderPreviewRequestDecision(Enum):
    """Classify one preview wake-up request without allocating a result."""

    REQUESTED = auto()
    POINTER_DEFERRED = auto()
    COALESCED = auto()
    COALESCED_POINTER_DEFERRED = auto()
    COALESCED_STALE = auto()
    COALESCED_STALE_POINTER_DEFERRED = auto()


class PromptReorderPreviewTimerDecision(Enum):
    """Describe the only actions a timer adapter may take on wake-up."""

    NO_PENDING = auto()
    RESCHEDULE_STALE = auto()
    RESCHEDULE_POINTER = auto()
    RUN = auto()
    RUN_AFTER_STARVATION = auto()


_COALESCED_REQUESTS = frozenset(
    {
        PromptReorderPreviewRequestDecision.COALESCED,
        PromptReorderPreviewRequestDecision.COALESCED_POINTER_DEFERRED,
        PromptReorderPreviewRequestDecision.COALESCED_STALE,
        PromptReorderPreviewRequestDecision.COALESCED_STALE_POINTER_DEFERRED,
    }
)
_STALE_COALESCED_REQUESTS = frozenset(
    {
        PromptReorderPreviewRequestDecision.COALESCED_STALE,
        PromptReorderPreviewRequestDecision.COALESCED_STALE_POINTER_DEFERRED,
    }
)
_POINTER_DEFERRED_REQUESTS = frozenset(
    {
        PromptReorderPreviewRequestDecision.POINTER_DEFERRED,
        PromptReorderPreviewRequestDecision.COALESCED_POINTER_DEFERRED,
        PromptReorderPreviewRequestDecision.COALESCED_STALE_POINTER_DEFERRED,
    }
)


class PromptReorderPreviewSchedulePolicy:
    """Own preview freshness, pointer deferral, and starvation decisions."""

    def __init__(self, *, pointer_defer_cap_ms: float) -> None:
        """Initialize an empty latest-wins preview schedule."""

        self._pointer_defer_cap_ms = pointer_defer_cap_ms
        self._latest_requested_revision: int | None = None
        self._scheduled_revision: int | None = None
        self._pending_since: float | None = None
        self._scheduled_pointer_revision: int | None = None
        self._replaced_revision: int | None = None

    @property
    def latest_requested_revision(self) -> int | None:
        """Return the newest revision requested by the interaction owner."""

        return self._latest_requested_revision

    @property
    def scheduled_revision(self) -> int | None:
        """Return the revision currently eligible for the next wake-up."""

        return self._scheduled_revision

    @property
    def scheduled_pointer_revision(self) -> int | None:
        """Return the pointer revision captured for the scheduled work."""

        return self._scheduled_pointer_revision

    @property
    def replaced_revision(self) -> int | None:
        """Return the revision replaced by the most recent request."""

        return self._replaced_revision

    def request(
        self,
        *,
        revision: int,
        pointer_active: bool,
        pointer_revision: int | None,
        timer_active: bool,
        now: float,
    ) -> PromptReorderPreviewRequestDecision:
        """Adopt one request and classify coalescing without running work."""

        previous_scheduled_revision = self._scheduled_revision
        if self._pending_since is None:
            self._pending_since = now
        self._latest_requested_revision = revision
        self._scheduled_revision = revision
        self._scheduled_pointer_revision = pointer_revision
        self._replaced_revision = previous_scheduled_revision if timer_active else None
        stale_replaced = (
            timer_active
            and previous_scheduled_revision is not None
            and previous_scheduled_revision < revision
        )
        if stale_replaced:
            if pointer_active:
                return (
                    PromptReorderPreviewRequestDecision.COALESCED_STALE_POINTER_DEFERRED
                )
            return PromptReorderPreviewRequestDecision.COALESCED_STALE
        if timer_active:
            if pointer_active:
                return PromptReorderPreviewRequestDecision.COALESCED_POINTER_DEFERRED
            return PromptReorderPreviewRequestDecision.COALESCED
        if pointer_active:
            return PromptReorderPreviewRequestDecision.POINTER_DEFERRED
        return PromptReorderPreviewRequestDecision.REQUESTED

    def timer_decision(
        self,
        *,
        pointer_revision: int | None,
        now: float,
    ) -> PromptReorderPreviewTimerDecision:
        """Choose whether one wake-up runs, reschedules, or rejects work."""

        scheduled_revision = self._scheduled_revision
        latest_revision = self._latest_requested_revision
        if scheduled_revision is None or latest_revision is None:
            return PromptReorderPreviewTimerDecision.NO_PENDING
        if scheduled_revision < latest_revision:
            self._scheduled_revision = latest_revision
            self._scheduled_pointer_revision = pointer_revision
            return PromptReorderPreviewTimerDecision.RESCHEDULE_STALE
        pointer_moved = (
            self._scheduled_pointer_revision is not None
            and pointer_revision is not None
            and pointer_revision > self._scheduled_pointer_revision
        )
        if not pointer_moved:
            return PromptReorderPreviewTimerDecision.RUN
        if self.pending_age_ms(now=now) < self._pointer_defer_cap_ms:
            self._scheduled_pointer_revision = pointer_revision
            return PromptReorderPreviewTimerDecision.RESCHEDULE_POINTER
        return PromptReorderPreviewTimerDecision.RUN_AFTER_STARVATION

    def pending_age_ms(self, *, now: float) -> float:
        """Return the age of the current coalesced request in milliseconds."""

        if self._pending_since is None:
            return 0.0
        return (now - self._pending_since) * 1000.0

    def clear(self) -> None:
        """Forget all pending wake-up policy state."""

        self._latest_requested_revision = None
        self._scheduled_revision = None
        self._pending_since = None
        self._scheduled_pointer_revision = None
        self._replaced_revision = None


def preview_request_was_coalesced(
    decision: PromptReorderPreviewRequestDecision,
) -> bool:
    """Return whether a request replaced an already scheduled revision."""

    return decision in _COALESCED_REQUESTS


def preview_request_rejected_stale_revision(
    decision: PromptReorderPreviewRequestDecision,
) -> bool:
    """Return whether coalescing discarded an older revision."""

    return decision in _STALE_COALESCED_REQUESTS


def preview_request_deferred_for_pointer(
    decision: PromptReorderPreviewRequestDecision,
) -> bool:
    """Return whether a request arrived during active pointer work."""

    return decision in _POINTER_DEFERRED_REQUESTS


__all__ = [
    "PromptReorderPreviewRequestDecision",
    "PromptReorderPreviewSchedulePolicy",
    "PromptReorderPreviewTimerDecision",
    "preview_request_deferred_for_pointer",
    "preview_request_rejected_stale_revision",
    "preview_request_was_coalesced",
]
