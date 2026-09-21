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

"""Distinguish an explicitly cancelled child from an unexplained abnormal exit."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.supervised_termination import (
    SupervisedTermination,
    SupervisedTerminationReason,
)
from sugarsubstitute_shared.crash_reporting import CrashIncidentStore


class _ExitedProcess:
    """Provide an observed OS exit without manufacturing a clean-exit receipt."""

    pid = 4401

    def wait(self, timeout: float | None = None) -> int:
        """Return a nonzero exit from a completed process."""
        return 1


@pytest.mark.parametrize("cancelled", [False, True])
def test_only_explicit_user_cancellation_suppresses_an_abnormal_exit_report(
    tmp_path: Path,
    cancelled: bool,
) -> None:
    """User-requested termination is expected; the same unexplained exit is a crash."""
    layout = InstallLayout.from_root(tmp_path)
    reports: list[str] = []
    owner = ApplicationCrashSupervisor(
        reporter_starter=lambda _layout, incident, _environment: reports.append(
            incident
        )
    )
    prepared = owner.prepare(layout=layout, environment={})
    assert (
        owner.supervise_process(
            layout=layout,
            process=_ExitedProcess(),
            prepared=prepared,
            termination=(
                SupervisedTermination(SupervisedTerminationReason.USER_CANCELLATION)
                if cancelled
                else SupervisedTermination()
            ),
        ).return_code
        == 1
    )
    assert bool(reports) is not cancelled
    assert (
        bool(CrashIncidentStore(prepared.context.incident_root).pending())
        is not cancelled
    )


def test_cancellation_outcome_survives_unavailable_diagnostic_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Retain a locked attachment without turning an intentional close into failure."""
    layout = InstallLayout.from_root(tmp_path)
    reports: list[str] = []
    owner = ApplicationCrashSupervisor(
        reporter_starter=lambda _layout, incident, _environment: reports.append(
            incident
        )
    )
    prepared = owner.prepare(layout=layout, environment={})
    fault_log = (
        prepared.context.incident_root / prepared.context.run_id / "python-fault.log"
    )
    fault_log.parent.mkdir(parents=True)
    fault_log.write_text("retained diagnostic", encoding="utf-8")
    unlink = Path.unlink

    def unavailable(path: Path, missing_ok: bool = False) -> None:
        """Simulate the filesystem refusing deletion of an open diagnostic file."""
        if path == fault_log:
            raise PermissionError("file is still in use")
        unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unavailable)
    assert (
        owner.supervise_process(
            layout=layout,
            process=_ExitedProcess(),
            prepared=prepared,
            termination=SupervisedTermination(
                SupervisedTerminationReason.USER_CANCELLATION
            ),
        ).return_code
        == 1
    )
    assert reports == []
    assert fault_log.read_text(encoding="utf-8") == "retained diagnostic"
    assert any(
        getattr(record, "run_id", None) == prepared.context.run_id
        and "retained" in record.getMessage()
        for record in caplog.records
    )
