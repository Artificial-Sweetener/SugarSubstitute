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

"""Dispatch Comfy listener terminal callbacks with structured diagnostics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.errors import ErrorReport
from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerCompleted,
    ListenerFailure,
    ListenerStartRequest,
)
from substitute.infrastructure.comfy.websocket_listener_engine import (
    ListenerEngineInterrupted,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("infrastructure.comfy.listener_callback_dispatcher")


class ListenerTimingEmitter(Protocol):
    """Describe the timing emitter behavior needed during terminal dispatch."""

    def emit_once(self, *, count_active_nodes: bool) -> None:
        """Emit timing once and decide whether active nodes count as completed."""


def _never_disconnect(_error: BaseException) -> bool:
    """Treat an error as a non-disconnect when no detector is supplied."""

    return False


@dataclass(frozen=True)
class ListenerCallbackDispatcher:
    """Own listener terminal callback construction and failure diagnostics."""

    request: ListenerStartRequest
    callbacks: ListenerCallbacks
    is_disconnect_error: Callable[[BaseException], bool] = _never_disconnect

    def emit_failure(
        self,
        error: BaseException,
        *,
        timing_emitter: ListenerTimingEmitter | None,
    ) -> None:
        """Emit failure timing, log the error, and deliver a failure DTO."""

        self._emit_failure_timing(timing_emitter)
        self._log_failure(error)
        self.callbacks.on_failed(
            ListenerFailure(
                workflow_id=self.request.workflow_id,
                generation_run_id=self.request.generation_run_id,
                prompt_id=self.request.prompt_id,
                error=str(error),
                detail=_error_detail(error),
                error_report=_error_report(error),
            )
        )

    def emit_completed(self) -> None:
        """Deliver the listener-completed callback for the current request."""

        self.callbacks.on_completed(
            ListenerCompleted(
                workflow_id=self.request.workflow_id,
                generation_run_id=self.request.generation_run_id,
                prompt_id=self.request.prompt_id,
            )
        )

    def _emit_failure_timing(
        self,
        timing_emitter: ListenerTimingEmitter | None,
    ) -> None:
        """Emit failure timing without letting timing callback errors mask failure."""

        if timing_emitter is None:
            return
        try:
            timing_emitter.emit_once(count_active_nodes=False)
        except Exception as timing_error:
            log_exception(
                _LOGGER,
                "Failed to emit generation execution timing",
                workflow_id=self.request.workflow_id,
                prompt_id=self.request.prompt_id,
                error=timing_error,
            )

    def _log_failure(self, error: BaseException) -> None:
        """Log listener failure with disconnect-specific severity."""

        if isinstance(error, ListenerEngineInterrupted):
            log_info(
                _LOGGER,
                "Comfy generation interrupted",
                workflow_id=self.request.workflow_id,
                generation_run_id=self.request.generation_run_id,
                prompt_id=self.request.prompt_id,
                reason="generation_interrupted",
            )
            return
        if self.is_disconnect_error(error):
            log_warning(
                _LOGGER,
                "Comfy websocket listener disconnected before prompt completion",
                workflow_id=self.request.workflow_id,
                generation_run_id=self.request.generation_run_id,
                prompt_id=self.request.prompt_id,
                error=error,
                reason="websocket_disconnected",
            )
            return
        log_exception(
            _LOGGER,
            "Websocket listener failed",
            workflow_id=self.request.workflow_id,
            generation_run_id=self.request.generation_run_id,
            prompt_id=self.request.prompt_id,
            error=error,
        )


def _error_detail(error: BaseException) -> str | None:
    """Return typed listener failure detail carried by execution errors."""

    detail = getattr(error, "detail", None)
    return detail if isinstance(detail, str) else None


def _error_report(error: BaseException) -> ErrorReport | None:
    """Return typed listener failure report carried by execution errors."""

    raw_report = getattr(error, "error_report", None)
    return raw_report if isinstance(raw_report, ErrorReport) else None


__all__ = [
    "ListenerCallbackDispatcher",
    "ListenerTimingEmitter",
]
