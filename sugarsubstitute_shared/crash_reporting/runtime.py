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

"""Install process-wide Python crash hooks before application bootstrap."""

from __future__ import annotations

import atexit
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
import faulthandler
import os
from pathlib import Path
import platform
import sys
import threading
import traceback
from types import TracebackType
from typing import Protocol, TextIO

from sugarsubstitute_shared.crash_reporting.model import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashKind,
)
from sugarsubstitute_shared.crash_reporting.native import CrashpadNativeClient
from sugarsubstitute_shared.crash_reporting.protocol import (
    CleanExitOutcome,
    CrashRunContext,
)
from sugarsubstitute_shared.crash_reporting.redaction import CrashReportRedactor
from sugarsubstitute_shared.crash_reporting.store import CrashIncidentStore


_PYTHON_FAULT_LOG_NAME = "python-fault.log"
_FATAL_EXIT_CODE = 70
_ACTIVE_RUNTIME: ProcessCrashRuntime | None = None


class UnraisableHookArguments(Protocol):
    """Describe the stable fields passed to ``sys.unraisablehook``."""

    @property
    def exc_type(self) -> type[BaseException] | None:
        """Return the unraisable exception type."""

    @property
    def exc_value(self) -> BaseException | None:
        """Return the unraisable exception value."""

    @property
    def exc_traceback(self) -> TracebackType | None:
        """Return the unraisable traceback."""

    @property
    def err_msg(self) -> str | None:
        """Return the interpreter-provided failure context."""


class ProcessCrashRuntime:
    """Own process-wide hooks and durable evidence for one supervised run."""

    def __init__(
        self,
        *,
        context: CrashRunContext,
        application_version: str | None,
        launch_arguments: Sequence[str],
        install_root: Path,
        terminate: Callable[[int], None] = os._exit,
        native_client: CrashpadNativeClient | None = None,
    ) -> None:
        """Prepare crash recording without changing global hooks."""

        self._context = context
        self._store = CrashIncidentStore(context.incident_root)
        self._application_version = application_version
        self._redactor = CrashReportRedactor(
            home=Path.home(),
            install_root=install_root,
        )
        self._launch_arguments = self._redactor.arguments(launch_arguments)
        self._terminate = terminate
        self._native_client = native_client or CrashpadNativeClient()
        self._clean_outcome: CleanExitOutcome | None = None
        self._fault_file: TextIO | None = None
        self._installed = False
        self._original_sys_hook = sys.excepthook
        self._original_thread_hook = threading.excepthook
        self._original_unraisable_hook = sys.unraisablehook

    @property
    def context(self) -> CrashRunContext:
        """Return this process's authenticated supervisor contract."""

        return self._context

    @property
    def clean_exit_outcome(self) -> CleanExitOutcome | None:
        """Return the controlled terminal outcome already requested."""

        return self._clean_outcome

    def install(self) -> None:
        """Install every Python-level crash boundary exactly once."""

        if self._installed:
            return
        self._installed = True
        self._enable_fault_handler()
        sys.excepthook = self._handle_main_exception
        threading.excepthook = self._handle_thread_exception
        sys.unraisablehook = self._handle_unraisable
        self._enable_native_handler()
        atexit.register(self._complete_clean_exit)
        self._context.clear_secret_environment()

    def request_clean_exit(self, outcome: CleanExitOutcome) -> None:
        """Record intended termination after application cleanup succeeds."""

        if self._clean_outcome is not None and self._clean_outcome is not outcome:
            raise RuntimeError(
                "A clean exit outcome cannot change after it is declared."
            )
        self._context.write_exit_intent(outcome, process_id=os.getpid())
        self._clean_outcome = outcome

    def record_qt_exception(self, error: BaseException) -> None:
        """Persist an exception escaping Qt event dispatch, then terminate safely."""

        self._record_exception(
            kind=CrashKind.PYTHON_UNHANDLED,
            boundary=CrashBoundary.QT_EVENT,
            error_type=type(error),
            error_value=error,
            error_traceback=error.__traceback__,
            thread_name=threading.current_thread().name,
        )
        self._dump_all_threads()
        self._terminate(_FATAL_EXIT_CODE)

    def record_python_exception(
        self,
        error: BaseException,
        *,
        kind: CrashKind,
        boundary: CrashBoundary,
        thread_name: str | None = None,
    ) -> None:
        """Persist a Python exception observed by an explicit owned boundary."""

        self._record_exception(
            kind=kind,
            boundary=boundary,
            error_type=type(error),
            error_value=error,
            error_traceback=error.__traceback__,
            thread_name=thread_name or threading.current_thread().name,
        )

    def record_qt_fatal_message(self, message: str) -> None:
        """Persist the last Qt fatal breadcrumb before Qt aborts the process."""

        self._record(
            kind=CrashKind.QT_FATAL,
            boundary=CrashBoundary.QT_MESSAGE,
            summary="Qt reported a fatal application error.",
            exception_type="QtFatalMsg",
            exception_message=message,
            trace=(),
            thread_name=threading.current_thread().name,
        )
        self._dump_all_threads()

    def record_execution_exception(self, error: BaseException) -> None:
        """Persist an exception escaping a managed job, then fail the process."""

        self._record_exception(
            kind=CrashKind.PYTHON_UNHANDLED,
            boundary=CrashBoundary.EXECUTION_JOB,
            error_type=type(error),
            error_value=error,
            error_traceback=error.__traceback__,
            thread_name=threading.current_thread().name,
        )
        self._dump_all_threads()
        self._terminate(_FATAL_EXIT_CODE)

    def _handle_main_exception(
        self,
        error_type: type[BaseException],
        error_value: BaseException,
        error_traceback: TracebackType | None,
    ) -> None:
        """Persist an exception that reached the interpreter's main boundary."""

        self._record_exception(
            kind=CrashKind.PYTHON_UNHANDLED,
            boundary=CrashBoundary.PROCESS_MAIN,
            error_type=error_type,
            error_value=error_value,
            error_traceback=error_traceback,
            thread_name=threading.current_thread().name,
        )
        self._dump_all_threads()
        self._original_sys_hook(error_type, error_value, error_traceback)

    def _handle_thread_exception(self, arguments: threading.ExceptHookArgs) -> None:
        """Fail fast after an exception escapes an owned Python thread."""

        error_value = arguments.exc_value or RuntimeError(
            "A Python thread ended with an unknown exception."
        )
        self._record_exception(
            kind=CrashKind.THREAD_UNHANDLED,
            boundary=CrashBoundary.PYTHON_THREAD,
            error_type=arguments.exc_type,
            error_value=error_value,
            error_traceback=arguments.exc_traceback,
            thread_name=arguments.thread.name if arguments.thread is not None else None,
        )
        self._dump_all_threads()
        self._original_thread_hook(arguments)
        self._terminate(_FATAL_EXIT_CODE)

    def _handle_unraisable(self, arguments: UnraisableHookArguments) -> None:
        """Fail fast when Python cannot propagate an owned exception normally."""

        error_value = arguments.exc_value or RuntimeError(
            arguments.err_msg or "Python reported an unraisable exception."
        )
        self._record_exception(
            kind=CrashKind.UNRAISABLE,
            boundary=CrashBoundary.PROCESS_MAIN,
            error_type=arguments.exc_type or type(error_value),
            error_value=error_value,
            error_traceback=arguments.exc_traceback,
            thread_name=threading.current_thread().name,
        )
        self._dump_all_threads()
        self._original_unraisable_hook(arguments)  # type: ignore[arg-type]
        self._terminate(_FATAL_EXIT_CODE)

    def _record_exception(
        self,
        *,
        kind: CrashKind,
        boundary: CrashBoundary,
        error_type: type[BaseException],
        error_value: BaseException,
        error_traceback: TracebackType | None,
        thread_name: str | None,
    ) -> None:
        """Normalize one Python exception into the durable incident contract."""

        rendered_traceback = tuple(
            self._redactor.text(line.rstrip("\n"))
            for line in traceback.format_exception(
                error_type,
                error_value,
                error_traceback,
            )
            if line
        )
        self._record(
            kind=kind,
            boundary=boundary,
            summary="SugarSubstitute encountered an unexpected internal error.",
            exception_type=error_type.__name__,
            exception_message=self._redactor.text(str(error_value)),
            trace=rendered_traceback,
            thread_name=thread_name,
        )

    def _record(
        self,
        *,
        kind: CrashKind,
        boundary: CrashBoundary,
        summary: str,
        exception_type: str | None,
        exception_message: str | None,
        trace: tuple[str, ...],
        thread_name: str | None,
    ) -> None:
        """Replace this run's incident with the richest current evidence."""

        incident = CrashIncident(
            incident_id=self._context.run_id,
            run_id=self._context.run_id,
            occurred_at_utc=datetime.now(timezone.utc).isoformat(),
            kind=kind,
            boundary=boundary,
            attribution=CrashAttribution.CONFIRMED,
            summary=summary,
            process_id=os.getpid(),
            exception_type=exception_type,
            exception_message=exception_message,
            traceback=trace,
            thread_name=thread_name,
            application_version=self._application_version,
            platform=platform.platform(),
            python_version=sys.version,
            launch_arguments=self._launch_arguments,
            attachments=(_PYTHON_FAULT_LOG_NAME,),
        )
        self._store.record(incident)

    def _enable_fault_handler(self) -> None:
        """Keep a pre-opened all-thread fault target available to signal handlers."""

        fault_path = self._store.attachment_path(
            self._context.run_id,
            _PYTHON_FAULT_LOG_NAME,
        )
        fault_path.parent.mkdir(parents=True, exist_ok=True)
        fault_file = fault_path.open("a", encoding="utf-8", buffering=1)
        self._fault_file = fault_file
        faulthandler.enable(file=fault_file, all_threads=True)

    def _enable_native_handler(self) -> None:
        """Register native exception capture when the run provides Crashpad."""

        if self._context.crashpad_handler is None:
            return
        fault_path = self._store.attachment_path(
            self._context.run_id,
            _PYTHON_FAULT_LOG_NAME,
        )
        self._native_client.start(
            context=self._context,
            application_version=self._application_version or "unknown",
            attachment_path=fault_path,
        )

    def _dump_all_threads(self) -> None:
        """Append every available Python thread stack to the fault attachment."""

        fault_file = self._fault_file
        if fault_file is None:
            return
        try:
            faulthandler.dump_traceback(file=fault_file, all_threads=True)
        except (OSError, RuntimeError):
            return

    def _complete_clean_exit(self) -> None:
        """Write final completion only for a previously declared clean outcome."""

        if self._clean_outcome is None:
            return
        self._context.write_exit_receipt(
            self._clean_outcome,
            process_id=os.getpid(),
        )


def install_process_crash_runtime(
    *,
    context: CrashRunContext,
    application_version: str | None,
    launch_arguments: Sequence[str],
    install_root: Path,
    native_client: CrashpadNativeClient | None = None,
) -> ProcessCrashRuntime:
    """Install and return the single crash runtime owned by this process."""

    global _ACTIVE_RUNTIME
    if _ACTIVE_RUNTIME is not None:
        if _ACTIVE_RUNTIME.context != context:
            raise RuntimeError(
                "A different crash run is already active in this process."
            )
        return _ACTIVE_RUNTIME
    runtime = ProcessCrashRuntime(
        context=context,
        application_version=application_version,
        launch_arguments=launch_arguments,
        install_root=install_root,
        native_client=native_client,
    )
    runtime.install()
    _ACTIVE_RUNTIME = runtime
    return runtime


def active_process_crash_runtime() -> ProcessCrashRuntime | None:
    """Return the installed process crash runtime when supervision is active."""

    return _ACTIVE_RUNTIME


def report_active_execution_exception(error: BaseException) -> bool:
    """Fail through the active crash runtime when a managed job escapes."""

    runtime = active_process_crash_runtime()
    if runtime is None:
        return False
    runtime.record_execution_exception(error)
    return True


__all__ = [
    "ProcessCrashRuntime",
    "active_process_crash_runtime",
    "install_process_crash_runtime",
    "report_active_execution_exception",
]
