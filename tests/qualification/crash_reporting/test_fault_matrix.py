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

"""Qualify destructive crash boundaries through real supervised processes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys

import pytest

from launcher.sugarsubstitute_launcher.candidate_update_launch import (
    launch_prepared_update,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import spawn_detached_process
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncidentStore,
    CrashKind,
)
from substitute.application.crash_reports import build_crash_error_report
from substitute.application.errors import render_error_report


_CHILD_MODULE = "tests.support.crash_reporting.fault_child"
_LAUNCHER_UI_CHILD_MODULE = "tests.support.crash_reporting.launcher_ui_child"


@dataclass(frozen=True, slots=True)
class ExpectedFault:
    """Describe the durable classification expected from one real process."""

    mode: str
    kind: CrashKind
    boundary: CrashBoundary
    attribution: CrashAttribution


_FAULTS = (
    ExpectedFault(
        "startup",
        CrashKind.ABNORMAL_EXIT,
        CrashBoundary.SUPERVISOR,
        CrashAttribution.UNCLEAN_TERMINATION,
    ),
    ExpectedFault(
        "python_main",
        CrashKind.PYTHON_UNHANDLED,
        CrashBoundary.PROCESS_MAIN,
        CrashAttribution.CONFIRMED,
    ),
    ExpectedFault(
        "python_thread",
        CrashKind.THREAD_UNHANDLED,
        CrashBoundary.PYTHON_THREAD,
        CrashAttribution.CONFIRMED,
    ),
    ExpectedFault(
        "unraisable",
        CrashKind.UNRAISABLE,
        CrashBoundary.PROCESS_MAIN,
        CrashAttribution.CONFIRMED,
    ),
    ExpectedFault(
        "qt_event",
        CrashKind.PYTHON_UNHANDLED,
        CrashBoundary.QT_EVENT,
        CrashAttribution.CONFIRMED,
    ),
    ExpectedFault(
        "qt_fatal",
        CrashKind.QT_FATAL,
        CrashBoundary.QT_MESSAGE,
        CrashAttribution.CONFIRMED,
    ),
    ExpectedFault(
        "execution",
        CrashKind.PYTHON_UNHANDLED,
        CrashBoundary.EXECUTION_JOB,
        CrashAttribution.CONFIRMED,
    ),
    ExpectedFault(
        "privacy",
        CrashKind.PYTHON_UNHANDLED,
        CrashBoundary.PROCESS_MAIN,
        CrashAttribution.CONFIRMED,
    ),
    ExpectedFault(
        "abort", CrashKind.ABORT, CrashBoundary.SUPERVISOR, CrashAttribution.CONFIRMED
    ),
    ExpectedFault(
        "hard_exit",
        CrashKind.ABNORMAL_EXIT,
        CrashBoundary.SUPERVISOR,
        CrashAttribution.UNCLEAN_TERMINATION,
    ),
)


def _start_child(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[subprocess.Popen[bytes], Path]:
    """Start a destructive child without sharing its console streams."""

    return spawn_detached_process(
        command,
        environment=environment,
    )


@pytest.mark.parametrize("expected", _FAULTS, ids=lambda item: item.mode)
def test_real_process_fault_is_durable_and_presented(
    tmp_path: Path,
    expected: ExpectedFault,
) -> None:
    """Every destructive boundary must produce one pending presented incident."""

    layout = InstallLayout.from_root(tmp_path / expected.mode)
    reports: list[str] = []
    supervisor = ApplicationCrashSupervisor(
        process_starter=_start_child,
        reporter_starter=lambda _layout, incident_id: reports.append(incident_id),
        native_runtime_resolver=lambda _layout: (
            tmp_path / "unused-handler",
            tmp_path / "unused-client",
        ),
    )

    command = [sys.executable, "-m", _CHILD_MODULE, expected.mode]
    if expected.mode == "privacy":
        command.append("--access-token=argument-secret")
    supervisor.supervise(
        layout=layout,
        command=command,
        environment={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )

    incidents = CrashIncidentStore(
        layout.appdata_dir / "diagnostics" / "crashes"
    ).pending()
    assert len(incidents) == 1
    incident = incidents[0]
    assert reports == [incident.incident_id]
    assert incident.kind is expected.kind
    assert incident.boundary is expected.boundary
    assert incident.attribution is expected.attribution
    assert incident.attachments == (
        () if expected.mode == "startup" else ("python-fault.log",)
    )
    if expected.mode == "privacy":
        report_text = render_error_report(build_crash_error_report(incident))
        assert "qualification-secret" not in report_text
        assert "argument-secret" not in report_text
        assert "private-value" not in report_text
        assert str(Path.cwd()) not in report_text
        assert "<redacted>" in report_text
        assert "<install-root>" in report_text


def test_real_process_clean_exit_creates_no_incident(tmp_path: Path) -> None:
    """A token-authenticated clean exit must not produce a false crash report."""

    layout = InstallLayout.from_root(tmp_path / "clean")
    reports: list[str] = []
    supervisor = ApplicationCrashSupervisor(
        process_starter=_start_child,
        reporter_starter=lambda _layout, incident_id: reports.append(incident_id),
        native_runtime_resolver=lambda _layout: (
            tmp_path / "unused-handler",
            tmp_path / "unused-client",
        ),
    )

    return_code = supervisor.supervise(
        layout=layout,
        command=(sys.executable, "-m", _CHILD_MODULE, "clean"),
        environment=os.environ,
    )

    assert return_code == 0
    assert reports == []
    assert (
        CrashIncidentStore(layout.appdata_dir / "diagnostics" / "crashes").pending()
        == ()
    )


@pytest.mark.platforms("windows")
def test_real_launcher_ui_child_crash_is_durable_and_presented(
    tmp_path: Path,
) -> None:
    """Launcher bootstrap must install Crashpad before importing any UI owner."""

    layout = InstallLayout.from_root(tmp_path / "launcher-ui")
    reports: list[str] = []
    project_root = Path(__file__).resolve().parents[3]
    runtime = project_root / "third_party" / "bin" / "crashpad" / "windows-x64"
    supervisor = ApplicationCrashSupervisor(
        process_starter=_start_child,
        reporter_starter=lambda _layout, incident_id: reports.append(incident_id),
        native_runtime_resolver=lambda _layout: (
            runtime / "crashpad_handler.exe",
            runtime / "sugarsubstitute_crashpad_client.dll",
        ),
    )

    return_code = supervisor.supervise(
        layout=layout,
        command=(sys.executable, "-m", _LAUNCHER_UI_CHILD_MODULE),
        environment=os.environ,
    )

    incidents = CrashIncidentStore(
        layout.appdata_dir / "diagnostics" / "crashes"
    ).pending()
    assert return_code != 0
    assert len(incidents) == 1
    assert reports == [incidents[0].incident_id]
    assert incidents[0].kind is CrashKind.PYTHON_UNHANDLED
    assert incidents[0].boundary is CrashBoundary.PROCESS_MAIN
    assert incidents[0].attribution is CrashAttribution.CONFIRMED
    assert incidents[0].attachments == ("python-fault.log",)


class _RealCandidateReadiness:
    """Launch a real candidate while treating process creation as readiness."""

    def launch_until_ready(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> subprocess.Popen[bytes]:
        """Start the candidate with the prepared crash contract."""

        del layout
        process, _fault_log = _start_child(command, environment)
        return process


class _CandidateActivation:
    """Record the terminal update transition during qualification."""

    def __init__(self) -> None:
        """Create an empty transition record."""

        self.transitions: list[str] = []

    def commit(self) -> None:
        """Record candidate commitment."""

        self.transitions.append("commit")

    def rollback(self) -> None:
        """Record candidate rollback."""

        self.transitions.append("rollback")


def test_real_update_candidate_handoff_preserves_crash_supervision(
    tmp_path: Path,
) -> None:
    """A committed update candidate must remain supervised for its full lifetime."""

    layout = InstallLayout.from_root(tmp_path / "candidate")
    reports: list[str] = []
    activation = _CandidateActivation()
    crash_supervisor = ApplicationCrashSupervisor(
        process_starter=_start_child,
        reporter_starter=lambda _layout, incident_id: reports.append(incident_id),
        native_runtime_resolver=lambda _layout: (
            tmp_path / "unused-handler",
            tmp_path / "unused-client",
        ),
    )

    launch_prepared_update(
        layout=layout,
        command=(sys.executable, "-m", _CHILD_MODULE, "python_main"),
        attempted_version="qualification",
        environment=os.environ,
        activation=activation,
        supervisor=_RealCandidateReadiness(),
        crash_supervisor=crash_supervisor,
    )

    incidents = CrashIncidentStore(
        layout.appdata_dir / "diagnostics" / "crashes"
    ).pending()
    assert activation.transitions == ["commit"]
    assert len(incidents) == 1
    assert reports == [incidents[0].incident_id]
    assert incidents[0].boundary is CrashBoundary.PROCESS_MAIN
