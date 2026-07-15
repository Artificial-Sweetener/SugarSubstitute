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

"""Warm QPane SAM dependencies during launch splash time."""

from __future__ import annotations

from collections.abc import Callable
from os import environ
from time import perf_counter

from substitute.application.execution import (
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.shared.logging.logger import get_logger, log_warning
from substitute.shared.qpane_sam_warmup_state import (
    QPaneSamWarmupSnapshot,
    qpane_sam_warmup_snapshot,
    reset_qpane_sam_warmup_snapshot_for_tests,
    set_qpane_sam_warmup_snapshot,
)
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("app.bootstrap.qpane_sam_startup_warmup")
_DISABLE_ENV_VAR = "SUBSTITUTE_DISABLE_QPANE_SAM_WARMUP"


class QPaneSamStartupWarmupHandle:
    """Run non-Qt QPane SAM dependency imports without blocking startup."""

    def __init__(
        self,
        *,
        submitter: TaskSubmitter,
        close_submitter: Callable[[], None] | None = None,
        ensure_dependencies: Callable[[], None] | None = None,
        disable_env_var: str = _DISABLE_ENV_VAR,
    ) -> None:
        """Store warmup dependencies.

        The default warmup imports MobileSAM/Torch through QPane's non-widget SAM
        service. It must not create QObjects, QWidgets, or QPixmaps.
        """

        self._submitter = submitter
        self._close_submitter = close_submitter or (lambda: None)
        self._uses_default_dependencies = ensure_dependencies is None
        self._ensure_dependencies = (
            ensure_dependencies or _ensure_qpane_sam_dependencies
        )
        self._disable_env_var = disable_env_var
        self._scope = TaskScope(
            submitter=self._submitter,
            scope_id=f"qpane_sam_startup_warmup_{id(self):x}",
        )
        self._handle: TaskHandle[None] | None = None

    def start(self) -> None:
        """Schedule the dependency warmup once."""

        if self._uses_default_dependencies and _warmup_disabled(self._disable_env_var):
            set_qpane_sam_warmup_snapshot(QPaneSamWarmupSnapshot(state="disabled"))
            trace_mark(
                "qpane_sam_warmup.disabled",
                env_var=self._disable_env_var,
            )
            return
        if self._handle is not None:
            trace_mark("qpane_sam_warmup.schedule_skipped", reason="already_started")
            return
        set_qpane_sam_warmup_snapshot(QPaneSamWarmupSnapshot(state="scheduled"))
        trace_mark("qpane_sam_warmup.scheduled")
        request: TaskRequest[None] = TaskRequest(
            identity=TaskIdentity(
                request_id=1,
                domain="qpane_sam_startup_warmup",
            ),
            context=ExecutionContext(
                operation="qpane_sam_startup_warmup",
                reason="startup_dependency_warmup",
                lane="startup",
            ),
            work=lambda _token: self._run(),
        )
        self._handle = self._scope.submit(request)

    def shutdown(self) -> None:
        """Request warmup executor shutdown without waiting for imports."""

        trace_mark("qpane_sam_warmup.shutdown_requested")
        self._scope.close(reason="qpane_sam_warmup_shutdown")
        self._close_submitter()

    def _run(self) -> None:
        """Import QPane SAM dependencies and record the result."""

        started_at = perf_counter()
        set_qpane_sam_warmup_snapshot(QPaneSamWarmupSnapshot(state="running"))
        trace_mark("qpane_sam_warmup.started")
        try:
            with trace_span("qpane_sam_warmup.ensure_dependencies"):
                self._ensure_dependencies()
        except Exception as error:  # noqa: BLE001 - startup warmup is best-effort.
            elapsed_ms = (perf_counter() - started_at) * 1000.0
            set_qpane_sam_warmup_snapshot(
                QPaneSamWarmupSnapshot(
                    state="failed",
                    elapsed_ms=elapsed_ms,
                    error=repr(error),
                )
            )
            trace_mark(
                "qpane_sam_warmup.failed",
                elapsed_ms=round(elapsed_ms, 3),
                error=repr(error),
            )
            log_warning(
                _LOGGER,
                "QPane SAM dependency warmup failed",
                elapsed_ms=f"{elapsed_ms:.3f}",
                error=repr(error),
            )
            return
        elapsed_ms = (perf_counter() - started_at) * 1000.0
        set_qpane_sam_warmup_snapshot(
            QPaneSamWarmupSnapshot(
                state="completed",
                elapsed_ms=elapsed_ms,
            )
        )
        trace_mark(
            "qpane_sam_warmup.completed",
            elapsed_ms=round(elapsed_ms, 3),
        )


def _ensure_qpane_sam_dependencies() -> None:
    """Import QPane's SAM dependency service and ensure its Python deps."""

    from qpane.sam.service import ensure_dependencies

    ensure_dependencies()


def _warmup_disabled(env_var: str) -> bool:
    """Return whether environment configuration disables default warmup."""

    value = environ.get(env_var, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "QPaneSamStartupWarmupHandle",
    "QPaneSamWarmupSnapshot",
    "qpane_sam_warmup_snapshot",
    "reset_qpane_sam_warmup_snapshot_for_tests",
]
