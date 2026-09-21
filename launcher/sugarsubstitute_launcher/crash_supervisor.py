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
import logging
from pathlib import Path
import platform
import sys
import time
from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.completed_run_artifacts import (
    CompletedRunArtifacts,
)
from launcher.sugarsubstitute_launcher.crash_incident_resolution import (
    newest_run_minidump,
    resolve_process_incident,
)
from launcher.sugarsubstitute_launcher.launcher_ui_process import present_crash_report
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from launcher.sugarsubstitute_launcher.supervised_termination import (
    SupervisedTermination,
)
from launcher.sugarsubstitute_launcher.application.repair.payload_version import (
    RepairPayloadVersionError,
    inspect_app_payload_version,
)
from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext
from sugarsubstitute_shared.crash_reporting.redaction import CrashReportRedactor


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
ReporterStarter = Callable[[InstallLayout, str, Mapping[str, str]], None]
NativeRuntimeResolver = Callable[[InstallLayout], tuple[Path, Path]]


@dataclass(frozen=True, slots=True)
class PreparedCrashRun:
    """Bind one child environment to its supervisor-owned crash contract."""

    context: CrashRunContext
    environment: Mapping[str, str]
    started_at_ns: int
    application_version: str | None = None
    platform: str = "unknown"
    python_version: str = "unknown"
    launch_arguments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClassifiedProcessExit:
    """Carry the crash owner's terminal decision without reconstructing its evidence."""

    return_code: int
    incident_id: str | None = None


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
        self._reporter_starter = reporter_starter or present_crash_report
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

        prepared = self.prepare(
            layout=layout,
            environment=environment,
            command=command,
        )
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
        ).return_code

    def prepare(
        self,
        *,
        layout: InstallLayout,
        environment: Mapping[str, str],
        command: Sequence[str] = (),
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
            application_version=_installed_application_version(layout),
            platform=platform.platform(),
            python_version=sys.version,
            launch_arguments=CrashReportRedactor(
                home=Path.home(),
                install_root=layout.root,
            ).arguments(command),
        )

    def supervise_process(
        self,
        *,
        layout: InstallLayout,
        process: SupervisedProcess,
        prepared: PreparedCrashRun,
        present_report: bool = True,
        termination: SupervisedTermination = SupervisedTermination(),
    ) -> ClassifiedProcessExit:
        """Return the authoritative termination classification after diagnostic cleanup."""

        if termination.detail:
            termination = replace(
                termination,
                detail=CrashReportRedactor(
                    home=Path.home(),
                    install_root=layout.root,
                ).text(termination.detail),
            )
        return_code = process.wait()
        context = prepared.context
        exit_evidence = context.inspect_exit_evidence()
        minidump = newest_run_minidump(
            context.crashpad_database,
            prepared.started_at_ns,
        )
        if termination.is_user_cancellation or (
            exit_evidence.validates_clean_exit and return_code == 0
        ):
            CompletedRunArtifacts(context).discard(minidump=minidump)
            if termination.is_user_cancellation:
                _LOGGER.info(
                    "Application startup cancelled by the user",
                    extra={
                        "run_id": context.run_id,
                        "process_id": process.pid,
                        "exit_code": return_code,
                    },
                )
            return ClassifiedProcessExit(return_code)

        incident = resolve_process_incident(
            layout=layout,
            context=context,
            process_id=process.pid,
            return_code=return_code,
            minidump=minidump,
            application_version=prepared.application_version,
            platform_name=prepared.platform,
            python_version=prepared.python_version,
            launch_arguments=prepared.launch_arguments,
            termination=termination,
            exit_evidence=exit_evidence,
        )
        if present_report:
            try:
                self._reporter_starter(
                    layout,
                    incident.incident_id,
                    prepared.environment,
                )
            except OSError:
                _LOGGER.exception(
                    "Crash reporter could not be started; incident remains pending.",
                    extra={"incident_id": incident.incident_id},
                )
        else:
            _LOGGER.info(
                "Deferred crash report while launcher presents startup recovery | "
                "incident_id=%s",
                incident.incident_id,
            )
        return ClassifiedProcessExit(return_code, incident.incident_id)


def _start_application_process(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[SupervisedProcess, Path]:
    """Start an application through the launcher's existing process owner."""

    return spawn_supervised_process(
        command, environment=environment, allow_handoff=True
    )


def _installed_native_runtime(layout: InstallLayout) -> tuple[Path, Path]:
    """Return the native runtime bundled beside the installed launcher."""

    return layout.crashpad_handler_path, layout.crashpad_client_library_path


def _installed_application_version(layout: InstallLayout) -> str | None:
    """Read application version metadata without importing application code."""

    try:
        return inspect_app_payload_version(layout.app_dir)
    except RepairPayloadVersionError:
        return None


__all__ = [
    "ApplicationCrashSupervisor",
    "ClassifiedProcessExit",
    "PreparedCrashRun",
    "SupervisedProcess",
]
