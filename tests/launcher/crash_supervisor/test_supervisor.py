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

"""Verify terminal classification by the full-lifetime crash supervisor."""

from __future__ import annotations

from launcher.sugarsubstitute_launcher.process_execution import ChildProcess

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import sys

from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from launcher.sugarsubstitute_launcher.supervised_termination import (
    SupervisedTermination,
    SupervisedTerminationReason,
)
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashIncidentStore,
    CrashKind,
)
from sugarsubstitute_shared.crash_reporting.protocol import CRASHPAD_DATABASE_ENV


def _start_process(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[ChildProcess, Path]:
    """Start an isolated qualification child with the supplied run contract."""

    return spawn_supervised_process(
        command,
        environment=environment,
    )


def test_supervisor_accepts_only_authenticated_clean_completion(tmp_path: Path) -> None:
    """A child supplying intent and completion should exit without a report."""

    layout = InstallLayout.from_root(tmp_path / "install")
    reports: list[str] = []
    layout.logs_dir.mkdir(parents=True)
    (layout.logs_dir / "app-startup.log").write_text(
        "stale startup evidence\n",
        encoding="utf-8",
    )
    script = (
        "import os; "
        "from sugarsubstitute_shared.crash_reporting.protocol import "
        "CrashRunContext, CleanExitOutcome; "
        "c=CrashRunContext.from_environment(); "
        "assert c is not None; "
        "c.write_exit_intent(CleanExitOutcome.CLOSED, process_id=os.getpid()); "
        "c.write_exit_receipt(CleanExitOutcome.CLOSED, process_id=os.getpid())"
    )

    return_code = ApplicationCrashSupervisor(
        process_starter=_start_process,
        reporter_starter=lambda _layout, incident_id, _environment: reports.append(
            incident_id
        ),
    ).supervise(
        layout=layout,
        command=(sys.executable, "-c", script),
        environment=os.environ,
    )

    assert return_code == 0
    assert reports == []
    canonical_log = layout.logs_dir / "app-startup.log"
    assert canonical_log.is_file()
    assert "Starting SugarSubstitute app" in canonical_log.read_text(encoding="utf-8")
    assert "stale startup evidence" not in canonical_log.read_text(encoding="utf-8")
    assert tuple((layout.appdata_dir / "diagnostics" / "runs").glob("*")) == ()
    assert (
        CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes").pending()
        == ()
    )


def test_supervisor_accepts_clean_completion_with_zero_exit_wrapper_dump(
    tmp_path: Path,
) -> None:
    """A signed zero exit should reject a macOS PyInstaller shutdown dump."""

    layout = InstallLayout.from_root(tmp_path / "install")
    reports: list[str] = []
    script = (
        "import os; "
        "from sugarsubstitute_shared.crash_reporting.protocol import "
        "CrashRunContext, CleanExitOutcome; "
        "c=CrashRunContext.from_environment(); "
        "assert c is not None; "
        "c.write_exit_intent(CleanExitOutcome.CLOSED, process_id=os.getpid()); "
        "c.write_exit_receipt(CleanExitOutcome.CLOSED, process_id=os.getpid())"
    )

    def start_with_wrapper_dump(
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[ChildProcess, Path]:
        """Model the dump emitted while a macOS PyInstaller wrapper exits cleanly."""

        dump = Path(environment[CRASHPAD_DATABASE_ENV]) / "pending" / "wrapper.dmp"
        dump.parent.mkdir(parents=True)
        dump.write_bytes(b"macOS PyInstaller wrapper shutdown")
        return _start_process(command, environment)

    return_code = ApplicationCrashSupervisor(
        process_starter=start_with_wrapper_dump,
        reporter_starter=lambda _layout, incident_id, _environment: reports.append(
            incident_id
        ),
        time_ns=lambda: 0,
    ).supervise(
        layout=layout,
        command=(sys.executable, "-c", script),
        environment=os.environ,
    )

    assert return_code == 0
    assert reports == []
    assert tuple((layout.appdata_dir / "diagnostics" / "crashpad").rglob("*.dmp")) == ()
    assert (
        CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes").pending()
        == ()
    )


def test_supervisor_reports_hard_exit_even_when_exit_code_is_zero(
    tmp_path: Path,
) -> None:
    """An absent receipt must remain abnormal regardless of operating-system status."""

    layout = InstallLayout.from_root(tmp_path / "install")
    reports: list[str] = []

    return_code = ApplicationCrashSupervisor(
        process_starter=_start_process,
        reporter_starter=lambda _layout, incident_id, _environment: reports.append(
            incident_id
        ),
    ).supervise(
        layout=layout,
        command=(sys.executable, "-c", "import os; os._exit(0)"),
        environment=os.environ,
    )

    incidents = CrashIncidentStore(
        layout.appdata_dir / "diagnostics" / "crashes"
    ).pending()
    assert return_code == 0
    assert reports == [incidents[0].incident_id]
    assert incidents[0].kind is CrashKind.ABNORMAL_EXIT
    assert incidents[0].attribution is CrashAttribution.UNCLEAN_TERMINATION
    assert tuple((layout.appdata_dir / "diagnostics" / "runs").glob("*")) == ()


def test_supervisor_preserves_known_readiness_failure_instead_of_calling_it_crash(
    tmp_path: Path,
) -> None:
    """Launcher termination must retain its known cause and startup diagnostics."""

    layout = InstallLayout.from_root(tmp_path / "install")
    reports: list[str] = []
    detail = f"Readiness timed out below {layout.root} api_key=private-value"
    owner = ApplicationCrashSupervisor(
        reporter_starter=lambda _layout, incident_id, _environment: reports.append(
            incident_id
        )
    )
    prepared = owner.prepare(
        layout=layout,
        environment={},
        command=("python", "main.py", "--access-token=argument-secret"),
    )
    startup_output = (
        prepared.context.run_root / prepared.context.run_id / "startup-output.log"
    )
    startup_output.parent.mkdir(parents=True)
    startup_output.write_text(
        "last startup milestone: shell.compose\n", encoding="utf-8"
    )

    class FailedCandidate:
        """Return the exit status used by Windows supervisor termination."""

        pid = 7311

        def wait(self, timeout: float | None = None) -> int:
            """Return the known job termination status."""

            del timeout
            return 1

    outcome = owner.supervise_process(
        layout=layout,
        process=FailedCandidate(),
        prepared=prepared,
        termination=SupervisedTermination(
            SupervisedTerminationReason.READINESS_FAILURE,
            detail,
        ),
    )

    incident = CrashIncidentStore(prepared.context.incident_root).pending()[0]
    assert outcome.incident_id == incident.incident_id
    assert reports == [incident.incident_id]
    assert incident.kind is CrashKind.STARTUP
    assert incident.attribution is CrashAttribution.CONFIRMED
    assert incident.metadata["termination_reason"] == "readiness_failure"
    assert incident.metadata["exit_intent_state"] == "missing"
    assert incident.metadata["exit_receipt_state"] == "missing"
    assert incident.metadata["termination_detail"] == (
        "Readiness timed out below <install-root> api_key=<redacted>"
    )
    assert incident.attachments == ("startup-output.log",)
    assert "argument-secret" not in " ".join(incident.launch_arguments)


def test_supervisor_identifies_real_abort_from_fatal_evidence(tmp_path: Path) -> None:
    """A real abort must produce a confirmed incident even without a minidump."""

    layout = InstallLayout.from_root(tmp_path / "install")
    reports: list[str] = []
    script = (
        "import faulthandler, os; "
        "from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext; "
        "c=CrashRunContext.from_environment(); assert c is not None; "
        "p=c.run_root/c.run_id/'python-fault.log'; "
        "p.parent.mkdir(parents=True, exist_ok=True); "
        "f=p.open('w', encoding='utf-8'); faulthandler.enable(file=f, all_threads=True); "
        "os.abort()"
    )

    ApplicationCrashSupervisor(
        process_starter=_start_process,
        reporter_starter=lambda _layout, incident_id, _environment: reports.append(
            incident_id
        ),
    ).supervise(
        layout=layout,
        command=(sys.executable, "-c", script),
        environment=os.environ,
    )

    incident = CrashIncidentStore(
        layout.appdata_dir / "diagnostics" / "crashes"
    ).pending()[0]
    assert reports == [incident.incident_id]
    assert incident.kind is CrashKind.ABORT
    assert incident.attribution is CrashAttribution.CONFIRMED
    assert incident.attachments == (
        "python-fault.log",
        "startup-output.log",
    )


def test_supervisor_keeps_incident_pending_when_reporter_fails(tmp_path: Path) -> None:
    """Reporter startup failure should defer presentation rather than lose evidence."""

    layout = InstallLayout.from_root(tmp_path / "install")

    def fail_reporter(
        _layout: InstallLayout,
        _incident_id: str,
        _environment: Mapping[str, str],
    ) -> None:
        """Simulate a missing or damaged reporter executable."""

        raise OSError("reporter missing")

    ApplicationCrashSupervisor(
        process_starter=_start_process,
        reporter_starter=fail_reporter,
    ).supervise(
        layout=layout,
        command=(sys.executable, "-c", "raise RuntimeError('boom')"),
        environment=os.environ,
    )

    assert (
        len(
            CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes").pending()
        )
        == 1
    )


def test_supervisor_retains_crashpad_dump_inside_incident(tmp_path: Path) -> None:
    """A detected native dump must become durable incident-owned evidence."""

    layout = InstallLayout.from_root(tmp_path / "install")

    def start_with_dump(
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> tuple[ChildProcess, Path]:
        """Create representative Crashpad evidence before the child exits."""

        dump = Path(environment[CRASHPAD_DATABASE_ENV]) / "pending" / "native.dmp"
        dump.parent.mkdir(parents=True)
        dump.write_bytes(b"crashpad minidump")
        return _start_process(command, environment)

    ApplicationCrashSupervisor(
        process_starter=start_with_dump,
        reporter_starter=lambda _layout, _incident_id, _environment: None,
        time_ns=lambda: 0,
    ).supervise(
        layout=layout,
        command=(sys.executable, "-c", "import os; os._exit(7)"),
        environment=os.environ,
    )

    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    incident = store.pending()[0]
    assert incident.kind is CrashKind.NATIVE
    assert incident.attachments == ("startup-output.log", "native.dmp")
    assert (
        store.attachment_path(incident.incident_id, "native.dmp").read_bytes()
        == b"crashpad minidump"
    )
