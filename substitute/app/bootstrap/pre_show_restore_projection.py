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

"""Coordinate pre-show restored editor projection before shell reveal."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.app.bootstrap.startup_trace import trace_mark

PRE_SHOW_RESTORE_PROJECTION_TIMEOUT_MS = 10_000


class PreShowRestoreProjectionStarter(Protocol):
    """Start hidden restored editor projection before the shell is shown."""

    def __call__(
        self,
        artifact: object | None,
        *,
        fallback_workflow_id: str,
        on_complete: Callable[[], None],
    ) -> bool:
        """Start projection and return whether completion will be reported."""


@dataclass
class PreShowRestoreProjectionState:
    """Track one pre-show restore projection gate."""

    pending: bool = False
    completion_handled: bool = False


def start_pre_show_restore_projection_if_available(
    *,
    state: PreShowRestoreProjectionState,
    hidden_restore_runtime_prepared: bool,
    start_projection: PreShowRestoreProjectionStarter | None,
    provisional_restore_projection: object | None,
    fallback_workflow_id: str,
    startup_cancelled: Callable[[], bool],
    reveal_main_window: Callable[[], None],
    scheduler: Callable[[int, Callable[[], None]], None],
    trace_fields: Callable[[], Mapping[str, object]],
    timeout_ms: int = PRE_SHOW_RESTORE_PROJECTION_TIMEOUT_MS,
) -> bool:
    """Start pre-show restore projection and return whether reveal is deferred."""

    if not hidden_restore_runtime_prepared or start_projection is None:
        trace_mark(
            "main_shell.pre_show_restore_projection.skip",
            reason=(
                "runtime_not_prepared"
                if not hidden_restore_runtime_prepared
                else "start_callable_missing"
            ),
            cache_artifact_present=provisional_restore_projection is not None,
            restored_active_workflow_id=fallback_workflow_id,
            **dict(trace_fields()),
        )
        return False

    state.pending = True
    state.completion_handled = False
    trace_mark(
        "main_shell.pre_show_restore_projection.start",
        projection_source=_projection_source(provisional_restore_projection),
        restored_active_workflow_id=fallback_workflow_id,
        **dict(trace_fields()),
    )

    def finish_projection(*, reason: str) -> None:
        """Reveal the shell after hidden projection completes or times out."""

        if state.completion_handled:
            trace_mark(
                "main_shell.pre_show_restore_projection.late_completion",
                reason=reason,
                **dict(trace_fields()),
            )
            return
        state.completion_handled = True
        if startup_cancelled():
            trace_mark(
                "main_shell.pre_show_restore_projection.cancelled",
                reason=reason,
                **dict(trace_fields()),
            )
            state.pending = False
            return
        state.pending = False
        trace_mark(
            "main_shell.pre_show_restore_projection.complete",
            reason=reason,
            **dict(trace_fields()),
        )
        reveal_main_window()

    def timeout_projection() -> None:
        """Fail open if hidden editor projection does not report completion."""

        trace_mark(
            "main_shell.pre_show_restore_projection.timeout",
            timeout_ms=timeout_ms,
            **dict(trace_fields()),
        )
        finish_projection(reason="timeout")

    started = bool(
        start_projection(
            provisional_restore_projection,
            fallback_workflow_id=fallback_workflow_id,
            on_complete=lambda: finish_projection(reason="surface_complete"),
        )
    )
    if started:
        trace_mark(
            "main_shell.pre_show_restore_projection.timeout",
            delay_ms=timeout_ms,
        )
        scheduler(timeout_ms, timeout_projection)
        trace_mark(
            "main_shell.pre_show_restore_projection.waiting",
            timeout_ms=timeout_ms,
            **dict(trace_fields()),
        )
        return True

    state.pending = False
    trace_mark(
        "main_shell.pre_show_restore_projection.skip",
        reason="start_returned_false",
        projection_source=_projection_source(provisional_restore_projection),
        restored_active_workflow_id=fallback_workflow_id,
        **dict(trace_fields()),
    )
    return state.completion_handled


def _projection_source(provisional_restore_projection: object | None) -> str:
    """Return the prompt-safe projection source label."""

    if provisional_restore_projection is not None:
        return "cache"
    return "live_restored_workflow"


__all__ = [
    "PRE_SHOW_RESTORE_PROJECTION_TIMEOUT_MS",
    "PreShowRestoreProjectionStarter",
    "PreShowRestoreProjectionState",
    "start_pre_show_restore_projection_if_available",
]
