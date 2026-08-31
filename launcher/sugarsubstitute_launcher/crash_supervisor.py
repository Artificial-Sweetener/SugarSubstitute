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

"""Supervise one application process until a proven clean exit or crash report."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime, timezone
import logging
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import spawn_detached_process
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashIncidentStore,
    CrashKind,
)
from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext


_LOGGER = logging.getLogger(__name__)


class SupervisedProcess(Protocol):
    """Expose the process lifetime operations required by supervision."""

    @property
    def pid(self) -> int:
        """Return the operating-system process identifier."""

    def wait(self, timeout: float | None = None) -> int:
        """Wait for termination and return the process exit status."""


ProcessStarter = Callable[
    [Sequence[str], Mapping[str, str]],
    tuple[SupervisedProcess, Path],
]
ReporterStarter = Callable[[InstallLayout, str], None]
NativeRuntimeResolver = Callable[[InstallLayout], tuple[Path, Path]]


@dataclass(frozen=True, slots=True)
class PreparedCrashRun:
    """Bind one child environment to its supervisor-owned crash contract."""

    context: CrashRunContext
    environment: Mapping[str, str]
    started_at_ns: int


class ApplicationCrashSupervisor:
    """Retain application ownership until its terminal state is classified."""

    def __init__(
        self,
        *,
        process_starter: ProcessStarter | None = None,
        reporter_starter: ReporterStarter | None = None,
        native_runtime_resolver: NativeRuntimeResolver | None = None,
        time_ns: Callable[[], int] = time.time_ns,
    ) -> None:
        """Store process, reporter, and clock boundaries for deterministic proof."""

        self._process_starter = process_starter or _start_application_process
        self._reporter_starter = reporter_starter or _start_crash_reporter
        self._native_runtime_resolver = (
            native_runtime_resolver or _installed_native_runtime
        )
        self._time_ns = time_ns

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
        on_started: Callable[[SupervisedProcess], None] | None = None,
    ) -> int:
        """Run one application and surface every termination lacking clean proof."""

        prepared = self.prepare(layout=layout, environment=environment)
        process, _startup_log = self._process_starter(
            command,
            prepared.environment,
        )
        if on_started is not None:
            on_started(process)
        return self.supervise_process(
            layout=layout,
            process=process,
            prepared=prepared,
        )

    def prepare(
        self,
        *,
        layout: InstallLayout,
        environment: Mapping[str, str],
    ) -> PreparedCrashRun:
        """Create the crash contract before another owner starts the app."""

        handler, client_library = self._native_runtime_resolver(layout)
        context = CrashRunContext.create(
            layout.appdata_dir / "diagnostics",
            crashpad_handler=handler,
            crashpad_client_library=client_library,
        )
        return PreparedCrashRun(
            context=context,
            environment=context.environment(environment),
            started_at_ns=self._time_ns(),
        )

    def supervise_process(
        self,
        *,
        layout: InstallLayout,
        process: SupervisedProcess,
        prepared: PreparedCrashRun,
    ) -> int:
        """Classify a process started by a readiness or update owner."""

        return_code = process.wait()
        context = prepared.context
        minidump = _newest_minidump(
            context.crashpad_database,
            prepared.started_at_ns,
        )
        if context.validates_clean_exit() and minidump is None:
            _discard_clean_run_artifacts(context)
            return return_code

        incident = self._resolve_incident(
            context=context,
            process_id=process.pid,
            return_code=return_code,
            minidump=minidump,
        )
        try:
            self._reporter_starter(layout, incident.incident_id)
        except OSError:
            _LOGGER.exception(
                "Crash reporter could not be started; incident remains pending.",
                extra={"incident_id": incident.incident_id},
            )
        return return_code

    @staticmethod
    def _resolve_incident(
        *,
        context: CrashRunContext,
        process_id: int,
        return_code: int,
        minidump: Path | None,
    ) -> CrashIncident:
        """Enrich in-process evidence or synthesize an accurate termination report."""

        store = CrashIncidentStore(context.incident_root)
        retained_dump: Path | None = None
        if minidump is not None:
            try:
                retained_dump = store.retain_attachment(context.run_id, minidump)
            except OSError:
                _LOGGER.exception(
                    "Crashpad minidump could not be retained with its incident.",
                    extra={"run_id": context.run_id},
                )
        existing = next(
            (item for item in store.pending() if item.run_id == context.run_id),
            None,
        )
        if existing is not None:
            existing_attachments = existing.attachments
            if (
                retained_dump is not None
                and retained_dump.name not in existing_attachments
            ):
                existing_attachments = (*existing_attachments, retained_dump.name)
            incident = replace(
                existing,
                exit_code=return_code,
                attachments=existing_attachments,
            )
            store.record(incident)
            return incident

        synthesized_attachments: list[str] = []
        fault_log = store.attachment_path(context.run_id, "python-fault.log")
        if fault_log.is_file():
            synthesized_attachments.append(fault_log.name)
        if retained_dump is not None:
            synthesized_attachments.append(retained_dump.name)
        kind, boundary, attribution, summary = _synthesized_termination(
            minidump=minidump,
            fault_log=fault_log,
            return_code=return_code,
        )
        incident = CrashIncident(
            incident_id=context.run_id,
            run_id=context.run_id,
            occurred_at_utc=datetime.now(timezone.utc).isoformat(),
            kind=kind,
            boundary=boundary,
            attribution=attribution,
            summary=summary,
            process_id=process_id,
            exit_code=return_code,
            attachments=tuple(synthesized_attachments),
        )
        store.record(incident)
        return incident


def _synthesized_termination(
    *,
    minidump: Path | None,
    fault_log: Path,
    return_code: int,
) -> tuple[CrashKind, CrashBoundary, CrashAttribution, str]:
    """Classify durable termination evidence without guessing from generic exits."""

    aborted = _fault_log_reports_abort(fault_log) or return_code == -signal.SIGABRT
    if aborted:
        return (
            CrashKind.ABORT,
            CrashBoundary.NATIVE_HANDLER
            if minidump is not None
            else CrashBoundary.SUPERVISOR,
            CrashAttribution.CONFIRMED,
            "SugarSubstitute aborted after a fatal runtime failure.",
        )
    if minidump is not None:
        return (
            CrashKind.NATIVE,
            CrashBoundary.NATIVE_HANDLER,
            CrashAttribution.CONFIRMED,
            "Crashpad captured a native SugarSubstitute crash.",
        )
    return (
        CrashKind.ABNORMAL_EXIT,
        CrashBoundary.SUPERVISOR,
        CrashAttribution.UNCLEAN_TERMINATION,
        "SugarSubstitute terminated without a clean shutdown receipt.",
    )


def _fault_log_reports_abort(path: Path) -> bool:
    """Return whether bounded fatal evidence explicitly identifies an abort."""

    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - (1024 * 1024)))
            tail = stream.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    return "Fatal Python error: Aborted" in tail


def _start_application_process(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[SupervisedProcess, Path]:
    """Start an application through the launcher's existing process owner."""

    return spawn_detached_process(command, environment=environment)


def _installed_native_runtime(layout: InstallLayout) -> tuple[Path, Path]:
    """Return the native runtime bundled beside the installed launcher."""

    return layout.crashpad_handler_path, layout.crashpad_client_library_path


def _start_crash_reporter(layout: InstallLayout, incident_id: str) -> None:
    """Start the stable launcher in dedicated crash-report mode."""

    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NO_WINDOW
    subprocess.Popen(  # noqa: S603
        [
            str(layout.executable_path),
            f"--install-root={layout.root}",
            f"--show-crash-report={incident_id}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
        startupinfo=startupinfo,
        shell=False,
    )


def _newest_minidump(database: Path, started_at_ns: int) -> Path | None:
    """Return the newest Crashpad dump created during this supervised run."""

    if not database.is_dir():
        return None
    candidates: list[tuple[int, Path]] = []
    for path in database.rglob("*.dmp"):
        try:
            modified_ns = path.stat().st_mtime_ns
        except OSError:
            continue
        if modified_ns >= started_at_ns:
            candidates.append((modified_ns, path))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def _discard_clean_run_artifacts(context: CrashRunContext) -> None:
    """Remove only known per-run files after authenticated clean termination."""

    for path in (context.exit_intent_path, context.exit_receipt_path):
        path.unlink(missing_ok=True)
    lifecycle_directory = context.exit_intent_path.parent
    try:
        lifecycle_directory.rmdir()
    except OSError:
        pass
    incident_directory = context.incident_root / context.run_id
    fault_log = incident_directory / "python-fault.log"
    fault_log.unlink(missing_ok=True)
    try:
        incident_directory.rmdir()
    except OSError:
        pass


__all__ = [
    "ApplicationCrashSupervisor",
    "PreparedCrashRun",
    "SupervisedProcess",
]
