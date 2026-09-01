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

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import subprocess
import sys

from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import spawn_detached_process
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashIncidentStore,
    CrashKind,
)
from sugarsubstitute_shared.crash_reporting.protocol import CRASHPAD_DATABASE_ENV


def _start_process(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[subprocess.Popen[bytes], Path]:
    """Start an isolated qualification child with the supplied run contract."""

    return spawn_detached_process(
        command,
        environment=environment,
    )


def test_supervisor_accepts_only_authenticated_clean_completion(tmp_path: Path) -> None:
    """A child supplying intent and completion should exit without a report."""

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

    return_code = ApplicationCrashSupervisor(
        process_starter=_start_process,
        reporter_starter=lambda _layout, incident_id: reports.append(incident_id),
    ).supervise(
        layout=layout,
        command=(sys.executable, "-c", script),
        environment=os.environ,
    )

    assert return_code == 0
    assert reports == []
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
        reporter_starter=lambda _layout, incident_id: reports.append(incident_id),
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


def test_supervisor_identifies_real_abort_from_fatal_evidence(tmp_path: Path) -> None:
    """A real abort must produce a confirmed incident even without a minidump."""

    layout = InstallLayout.from_root(tmp_path / "install")
    reports: list[str] = []
    script = (
        "import faulthandler, os; "
        "from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext; "
        "c=CrashRunContext.from_environment(); assert c is not None; "
        "p=c.incident_root/c.run_id/'python-fault.log'; p.parent.mkdir(parents=True); "
        "f=p.open('w', encoding='utf-8'); faulthandler.enable(file=f, all_threads=True); "
        "os.abort()"
    )

    ApplicationCrashSupervisor(
        process_starter=_start_process,
        reporter_starter=lambda _layout, incident_id: reports.append(incident_id),
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
    assert incident.attachments == ("python-fault.log",)


def test_supervisor_keeps_incident_pending_when_reporter_fails(tmp_path: Path) -> None:
    """Reporter startup failure should defer presentation rather than lose evidence."""

    layout = InstallLayout.from_root(tmp_path / "install")

    def fail_reporter(_layout: InstallLayout, _incident_id: str) -> None:
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
    ) -> tuple[subprocess.Popen[bytes], Path]:
        """Create representative Crashpad evidence before the child exits."""

        dump = Path(environment[CRASHPAD_DATABASE_ENV]) / "pending" / "native.dmp"
        dump.parent.mkdir(parents=True)
        dump.write_bytes(b"crashpad minidump")
        return _start_process(command, environment)

    ApplicationCrashSupervisor(
        process_starter=start_with_dump,
        reporter_starter=lambda _layout, _incident_id: None,
        time_ns=lambda: 0,
    ).supervise(
        layout=layout,
        command=(sys.executable, "-c", "import os; os._exit(7)"),
        environment=os.environ,
    )

    store = CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes")
    incident = store.pending()[0]
    assert incident.kind is CrashKind.NATIVE
    assert incident.attachments == ("native.dmp",)
    assert (
        store.attachment_path(incident.incident_id, "native.dmp").read_bytes()
        == b"crashpad minidump"
    )
