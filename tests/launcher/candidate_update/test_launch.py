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

"""Verify candidate update launch, commit, rollback, and fallback."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
)
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    CandidateProcess,
    ApplicationStartupCancelled,
)
from launcher.sugarsubstitute_launcher.candidate_update_launch import (
    launch_prepared_update,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ClassifiedProcessExit,
    PreparedCrashRun,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.supervised_termination import (
    SupervisedTermination,
)
from sugarsubstitute_shared.application_runtime_mode import (
    APPLICATION_RUNTIME_MODE_ENV,
    PACKAGED_APPLICATION_RUNTIME_MODE,
)
from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext
from sugarsubstitute_shared.update_rollback_report import (
    UpdateRollbackReportStore,
    UpdateRollbackStage,
)


class _Activation:
    """Record candidate update terminal transitions."""

    def __init__(self) -> None:
        """Create an empty transition log."""

        self.transitions: list[str] = []

    def commit(self) -> None:
        """Record commit."""

        self.transitions.append("commit")

    def rollback(self) -> None:
        """Record rollback."""

        self.transitions.append("rollback")

    def reject(self, reason: str) -> None:
        """Record failed-target rejection."""

        self.transitions.append(f"reject:{reason}")


class _FailingCommitActivation(_Activation):
    """Fail after readiness to exercise launcher-initiated candidate termination."""

    def commit(self) -> None:
        """Raise the activation failure before the candidate can be committed."""

        raise RuntimeError("activation publication failed")


class _Supervisor:
    """Return or reject one candidate launch."""

    def __init__(self, *, fail: bool, cancel: bool = False) -> None:
        """Store whether launch should fail."""

        self._fail = fail
        self._cancel = cancel
        self.environments: list[dict[str, str]] = []
        self.process = _ReadyProcess()

    def launch_until_ready(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> CandidateProcess:
        """Record candidate inputs and return a ready process or fail."""

        _ = layout
        _ = command
        self.environments.append(dict(environment))
        if self._cancel:
            self.process.terminate()
            raise ApplicationStartupCancelled(self.process)
        if self._fail:
            raise ApplicationReadinessError("candidate failed")
        return self.process


class _ReadyProcess:
    """Represent a process that remains alive after readiness."""

    pid = 123
    return_code: int | None = None

    def poll(self) -> int | None:
        """Report a running process."""

        return self.return_code

    def terminate(self) -> None:
        """Satisfy the candidate process lifecycle port."""
        self.return_code = 1

    def kill(self) -> None:
        """Satisfy the candidate process lifecycle port."""

    def wait(self, timeout: float | None = None) -> int:
        """Satisfy the candidate process lifecycle port."""

        _ = timeout
        return 0


class _CrashSupervisor:
    """Record candidate adoption and restored fallback supervision."""

    def __init__(self, diagnostics_root: Path) -> None:
        """Store deterministic crash orchestration evidence."""

        self._diagnostics_root = diagnostics_root
        self.adopted: list[CandidateProcess] = []
        self.cancellations: list[bool] = []
        self.termination_reasons: list[str] = []
        self.fallbacks: list[tuple[list[str], dict[str, str]]] = []

    def prepare(
        self,
        *,
        layout: InstallLayout,
        environment: Mapping[str, str],
        command: Sequence[str] = (),
    ) -> PreparedCrashRun:
        """Add a recognizable crash contract to the candidate environment."""

        _ = (layout, command)
        prepared_environment = dict(environment)
        prepared_environment["CRASH_CONTRACT"] = "active"
        return PreparedCrashRun(
            context=CrashRunContext.create(self._diagnostics_root),
            environment=prepared_environment,
            started_at_ns=1,
        )

    def supervise_process(
        self,
        *,
        layout: InstallLayout,
        process: CandidateProcess,
        prepared: PreparedCrashRun,
        termination: SupervisedTermination = SupervisedTermination(),
    ) -> ClassifiedProcessExit:
        """Record full-lifetime adoption of the ready candidate."""

        _ = layout
        _ = prepared
        self.adopted.append(process)
        self.cancellations.append(termination.is_user_cancellation)
        self.termination_reasons.append(termination.reason.value)
        return ClassifiedProcessExit(0)

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> int:
        """Record full-lifetime supervision of the restored fallback."""

        _ = layout
        self.fallbacks.append((list(command), dict(environment)))
        return 0


def test_ready_candidate_commits_without_fallback(tmp_path: Path) -> None:
    """A visible candidate should become the installed update."""

    layout = InstallLayout.from_root(tmp_path / "install")
    activation = _Activation()
    supervisor = _Supervisor(fail=False)
    crash_supervisor = _CrashSupervisor(tmp_path / "diagnostics")

    launch_prepared_update(
        layout=layout,
        command=["python", "main.py"],
        attempted_version="0.21.3",
        environment={"BROKER": "connected"},
        activation=activation,
        supervisor=supervisor,
        crash_supervisor=crash_supervisor,
    )

    assert activation.transitions == ["commit"]
    assert supervisor.environments == [
        {
            "BROKER": "connected",
            APPLICATION_RUNTIME_MODE_ENV: PACKAGED_APPLICATION_RUNTIME_MODE,
            "CRASH_CONTRACT": "active",
        }
    ]
    assert crash_supervisor.adopted == [supervisor.process]
    assert UpdateRollbackReportStore(layout.root).load() is None


def test_failed_candidate_rolls_back_and_launches_previous_app(
    tmp_path: Path,
) -> None:
    """A failed candidate should restore and start the prior known-good app."""

    layout = InstallLayout.from_root(tmp_path / "install")
    activation = _Activation()
    crash_supervisor = _CrashSupervisor(tmp_path / "diagnostics")

    launch_prepared_update(
        layout=layout,
        command=["python", "main.py"],
        attempted_version="0.21.3",
        environment={"BROKER": "connected"},
        activation=activation,
        supervisor=_Supervisor(fail=True),
        crash_supervisor=crash_supervisor,
    )

    assert activation.transitions == ["reject:ApplicationReadinessError"]
    assert crash_supervisor.fallbacks == [
        (
            ["python", "main.py"],
            {
                "BROKER": "connected",
                APPLICATION_RUNTIME_MODE_ENV: PACKAGED_APPLICATION_RUNTIME_MODE,
            },
        ),
    ]
    rollback_report = UpdateRollbackReportStore(layout.root).load()
    assert rollback_report is not None
    assert rollback_report.attempted_version == "0.21.3"
    assert rollback_report.stage is UpdateRollbackStage.CANDIDATE_READINESS
    assert rollback_report.exception_type == "ApplicationReadinessError"
    assert rollback_report.message == "candidate failed"


def test_cancelled_candidate_rolls_back_without_failure_report_or_fallback(
    tmp_path: Path,
) -> None:
    """Respect cancellation without committing or relaunching an unwanted update."""
    import pytest

    layout = InstallLayout.from_root(tmp_path / "install")
    activation = _Activation()
    readiness = _Supervisor(fail=False, cancel=True)
    crash = _CrashSupervisor(layout.appdata_dir / "diagnostics")
    with pytest.raises(ApplicationStartupCancelled):
        launch_prepared_update(
            layout=layout,
            command=("app",),
            attempted_version="1.0.0",
            environment={},
            activation=activation,
            supervisor=readiness,
            crash_supervisor=crash,
            rollback_reporter=lambda **kwargs: pytest.fail(
                "Cancellation is not an update failure"
            ),
        )
    assert activation.transitions == ["rollback"]
    assert crash.fallbacks == []
    assert crash.cancellations == [True]
    assert crash.termination_reasons == ["user_cancellation"]


def test_activation_failure_retains_known_update_termination_reason(
    tmp_path: Path,
) -> None:
    """A launcher-stopped candidate must not be classified as an unknown app crash."""

    layout = InstallLayout.from_root(tmp_path / "install")
    activation = _FailingCommitActivation()
    readiness = _Supervisor(fail=False)
    crash = _CrashSupervisor(layout.appdata_dir / "diagnostics")

    launch_prepared_update(
        layout=layout,
        command=("app",),
        attempted_version="1.0.0",
        environment={},
        activation=activation,
        supervisor=readiness,
        crash_supervisor=crash,
    )

    assert readiness.process.return_code == 1
    assert activation.transitions == ["reject:RuntimeError"]
    assert crash.termination_reasons == ["update_activation_failure"]
    assert crash.fallbacks
