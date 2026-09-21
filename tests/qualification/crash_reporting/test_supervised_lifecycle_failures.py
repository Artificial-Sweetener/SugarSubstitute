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

"""Qualify real supervisor-initiated cancellation and update termination."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.application_lifecycle_supervisor import (
    ApplicationLifecycleSupervisor,
)
from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    ApplicationStartupCancelled,
)
from launcher.sugarsubstitute_launcher.candidate_update_launch import (
    launch_prepared_update,
)
from launcher.sugarsubstitute_launcher.crash_report_application import (
    _build_complete_crash_report,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashIncidentStore,
    CrashKind,
)
from sugarsubstitute_shared.update_rollback_report import UpdateRollbackStage
from tests.support.crash_reporting.process_synchronization import (
    controlled_expiry_clock,
    synchronized_process_starter,
)


_CHILD_MODULE = "tests.support.crash_reporting.fault_child"
_UPDATE_MARKER_ENV = "SUGAR_SUBSTITUTE_QUALIFY_UPDATE_MARKER"


def _start_child(
    command: Sequence[str],
    environment: Mapping[str, str],
) -> tuple[ChildProcess, Path]:
    """Start one destructive child inside the production process-family boundary."""

    return spawn_supervised_process(command, environment=environment)


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

    def reject(self, reason: str) -> None:
        """Record candidate rejection."""

        self.transitions.append(f"reject:{reason}")


@pytest.mark.platforms("windows")
def test_real_user_cancellation_creates_no_false_incident(tmp_path: Path) -> None:
    """Cancelling a started process must clean evidence without reporting a crash."""

    layout = InstallLayout.from_root(tmp_path / "cancelled")
    checks = 0

    def cancellation_requested() -> bool:
        """Cancel only after the readiness owner has started the real child."""

        nonlocal checks
        checks += 1
        return checks > 1

    crash_supervisor = ApplicationCrashSupervisor(
        process_starter=_start_child,
        reporter_starter=lambda _layout, _incident_id, _environment: None,
        native_runtime_resolver=lambda _layout: (
            tmp_path / "unused-handler",
            tmp_path / "unused-client",
        ),
    )
    lifecycle = ApplicationLifecycleSupervisor(
        readiness_timeout_seconds=10,
        crash_supervisor=crash_supervisor,
        cancellation_requested=cancellation_requested,
        process_starter=_start_child,
    )

    with pytest.raises(ApplicationStartupCancelled):
        lifecycle.supervise(
            layout=layout,
            command=(sys.executable, "-m", _CHILD_MODULE, "wait_for_termination"),
            environment=os.environ,
        )

    crash_root = layout.appdata_dir / "diagnostics" / "crashes"
    assert CrashIncidentStore(crash_root).pending() == ()
    assert not crash_root.exists() or tuple(crash_root.iterdir()) == ()


@pytest.mark.platforms("windows")
def test_real_update_readiness_failure_retains_cause_and_clean_fallback(
    tmp_path: Path,
) -> None:
    """A killed update candidate must be a startup failure, not an app crash."""

    layout = InstallLayout.from_root(tmp_path / "update-readiness")
    marker = tmp_path / "candidate-started.marker"
    reports: list[str] = []
    rollback_records: list[tuple[str, UpdateRollbackStage, str]] = []
    activation = _CandidateActivation()
    crash_supervisor = ApplicationCrashSupervisor(
        process_starter=_start_child,
        reporter_starter=lambda _layout, incident_id, _environment: reports.append(
            incident_id
        ),
        native_runtime_resolver=lambda _layout: (
            tmp_path / "unused-handler",
            tmp_path / "unused-client",
        ),
    )

    def record_rollback(
        *,
        install_root: Path,
        attempted_version: str,
        stage: UpdateRollbackStage,
        error: BaseException,
    ) -> None:
        """Record the real candidate failure without writing another report type."""

        assert install_root == layout.root
        rollback_records.append((attempted_version, stage, type(error).__name__))

    launch_prepared_update(
        layout=layout,
        command=(sys.executable, "-m", _CHILD_MODULE, "wait_once_then_clean"),
        attempted_version="qualification-update",
        environment={**os.environ, _UPDATE_MARKER_ENV: str(marker)},
        activation=activation,
        supervisor=ApplicationReadinessSupervisor(
            timeout_seconds=0.5,
            process_starter=synchronized_process_starter(),
            monotonic=controlled_expiry_clock(),
        ),
        crash_supervisor=crash_supervisor,
        rollback_reporter=record_rollback,
    )

    (incident,) = CrashIncidentStore(
        layout.appdata_dir / "diagnostics" / "crashes"
    ).pending()
    report = _build_complete_crash_report(layout, incident).report_text
    assert activation.transitions == ["reject:ApplicationReadinessError"]
    assert rollback_records == [
        (
            "qualification-update",
            UpdateRollbackStage.CANDIDATE_READINESS,
            "ApplicationReadinessError",
        )
    ]
    assert reports == [incident.incident_id]
    assert incident.kind is CrashKind.STARTUP
    assert incident.attribution is CrashAttribution.CONFIRMED
    assert incident.metadata["termination_reason"] == "update_readiness_failure"
    assert "Kind: startup" in report
    assert "termination_reason: update_readiness_failure" in report
    assert "qualification update candidate waiting before readiness" in report
    assert "SugarSubstitute crashed" not in report
