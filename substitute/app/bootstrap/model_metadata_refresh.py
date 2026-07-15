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

"""Run startup model metadata refresh work outside the Qt event loop."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time
from typing import Protocol

from substitute.application.execution import (
    CancellationSource,
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.model_metadata import (
    ModelMetadataProgressSink,
    RefreshCancellationToken,
)
from substitute.app.bootstrap.startup_policy import (
    OPTIONAL_METADATA_REFRESH_BUDGET_SECONDS,
)
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("app.bootstrap.model_metadata_refresh")
DEFAULT_STARTUP_METADATA_REFRESH_BUDGET_SECONDS = (
    OPTIONAL_METADATA_REFRESH_BUDGET_SECONDS
)


class StartupModelMetadataRefreshService(Protocol):
    """Run one model metadata refresh from startup coordination."""

    def refresh(
        self,
        progress: ModelMetadataProgressSink,
        *,
        cancellation_token: RefreshCancellationToken | None = None,
    ) -> object:
        """Refresh model metadata using startup progress and cancellation hooks."""


class ModelMetadataRefreshServiceFactory(Protocol):
    """Build the refresh service after Comfy becomes reachable."""

    def __call__(self) -> StartupModelMetadataRefreshService:
        """Return a fully composed model metadata refresh service."""


class StartupRefreshCancellationToken:
    """Expose startup refresh cancellation state to metadata services."""

    def __init__(self) -> None:
        """Initialize an uncancelled startup refresh source."""

        self._source = CancellationSource(generation=1)

    def cancel(self) -> None:
        """Request refresh cancellation."""

        trace_mark("model_metadata_refresh.cancellation_token.cancel")
        self._source.cancel(reason="startup_model_metadata_refresh_cancelled")

    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""

        return self._source.is_cancelled


@dataclass
class StartupModelMetadataRefreshHandle:
    """Track one background startup metadata refresh."""

    service_factory: ModelMetadataRefreshServiceFactory
    progress_sink: ModelMetadataProgressSink
    submitter: TaskSubmitter
    startup_budget_seconds: float = DEFAULT_STARTUP_METADATA_REFRESH_BUDGET_SECONDS
    close_submitter: Callable[[], None] | None = None
    monotonic: Callable[[], float] = time.monotonic
    finished_callback: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        """Initialize runtime state for the background refresh."""

        self._cancellation_token = StartupRefreshCancellationToken()
        self._scope = TaskScope(
            submitter=self.submitter,
            scope_id="startup_model_metadata_refresh",
        )
        self._handle: TaskHandle[None] | None = None
        self._deadline: float | None = None
        self._shutdown_requested = False

    def start(self) -> None:
        """Start refresh work once."""

        trace_mark(
            "model_metadata_refresh_handle.start_requested",
            already_started=self._handle is not None,
            startup_budget_seconds=self.startup_budget_seconds,
        )
        if self._handle is not None:
            return
        self._deadline = self.monotonic() + self.startup_budget_seconds
        self._handle = self._scope.submit(
            TaskRequest(
                identity=TaskIdentity(
                    request_id=1,
                    domain="model_metadata",
                    parts=(("operation_key", "startup_refresh"),),
                ),
                context=ExecutionContext(
                    operation="startup_model_metadata_refresh",
                    reason="startup",
                    lane="model_metadata",
                    safe_fields=(
                        ("operation_key", "startup_refresh"),
                        ("request_id", 1),
                    ),
                ),
                work=lambda _token: self._run_refresh(),
            )
        )

    def ready_to_release_splash(self) -> bool:
        """Return whether startup can close splash and show the shell."""

        if self._handle is None or self._deadline is None:
            return False
        return self._handle.is_finished or self.monotonic() >= self._deadline

    def cancel(self) -> None:
        """Request cancellation for refresh work that has not yet finished."""

        trace_mark("model_metadata_refresh_handle.cancel")
        self._cancellation_token.cancel()
        self._scope.cancel_all(reason="startup_model_metadata_refresh_cancelled")

    def shutdown(self) -> None:
        """Release execution resources without blocking application shutdown."""

        trace_mark("model_metadata_refresh_handle.shutdown_requested")
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._scope.close(reason="startup_model_metadata_refresh_shutdown")
        if self.close_submitter is not None:
            self.close_submitter()
            self.close_submitter = None

    def _run_refresh(self) -> None:
        """Run the refresh service and convert unexpected failures to log output."""

        try:
            trace_mark("model_metadata_refresh.task.start")
            with trace_span("model_metadata_refresh.service_factory"):
                service = self.service_factory()
            with trace_span("model_metadata_refresh.service_refresh"):
                service.refresh(
                    self.progress_sink,
                    cancellation_token=self._cancellation_token,
                )
            trace_mark("model_metadata_refresh.task.end")
        except Exception:
            trace_mark("model_metadata_refresh.task.error")
            log_exception(_LOGGER, "Startup model metadata refresh failed")
            self.progress_sink.emit_line(
                "Model metadata: refresh failed; using cached metadata where present."
            )
        finally:
            if self.finished_callback is not None:
                trace_mark("model_metadata_refresh.task.finished_callback")
                self.finished_callback()


__all__ = [
    "DEFAULT_STARTUP_METADATA_REFRESH_BUDGET_SECONDS",
    "StartupModelMetadataRefreshService",
    "StartupModelMetadataRefreshHandle",
    "StartupRefreshCancellationToken",
]
