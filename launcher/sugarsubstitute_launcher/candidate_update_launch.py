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

"""Launch, prove, commit, or roll back one prepared application update."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import logging
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
    ApplicationReadinessSupervisor,
    stop_candidate_process,
)
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    ApplicationStartupCancelled,
    CandidateProcess,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ClassifiedProcessExit,
    ApplicationCrashSupervisor,
    PreparedCrashRun,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.supervised_termination import (
    SupervisedTermination,
    SupervisedTerminationReason,
)
from launcher.sugarsubstitute_launcher.update_rollback_reporting import (
    record_update_rollback,
)
from sugarsubstitute_shared.application_runtime_mode import (
    packaged_application_environment,
)
from sugarsubstitute_shared.update_rollback_report import UpdateRollbackStage


_LOGGER = logging.getLogger(__name__)


class CandidateUpdateRollbackError(RuntimeError):
    """Report a rolled-back update whose prior app could not be relaunched."""


class CandidateUpdateActivation(Protocol):
    """Commit or roll back one prepared update."""

    def commit(self) -> None:
        """Commit the candidate update."""

    def rollback(self) -> None:
        """Restore the prior update state."""

    def reject(self, reason: str) -> None:
        """Restore the prior state and quarantine a failed target."""


class CandidateReadinessSupervisor(Protocol):
    """Wait until one candidate application is visibly ready."""

    def launch_until_ready(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> CandidateProcess:
        """Return the candidate process after readiness."""


class CandidateCrashSupervisor(Protocol):
    """Own crash contracts across candidate and fallback app lifetimes."""

    def prepare(
        self,
        *,
        layout: InstallLayout,
        environment: Mapping[str, str],
        command: Sequence[str] = (),
    ) -> PreparedCrashRun:
        """Prepare a crash-aware child environment before readiness launch."""

    def supervise_process(
        self,
        *,
        layout: InstallLayout,
        process: CandidateProcess,
        prepared: PreparedCrashRun,
        termination: SupervisedTermination = SupervisedTermination(),
    ) -> ClassifiedProcessExit:
        """Classify a candidate for the remainder of its lifetime."""

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> int:
        """Start and classify a restored fallback for its full lifetime."""


class UpdateRollbackReporter(Protocol):
    """Persist diagnostics after the previous application is restored."""

    def __call__(
        self,
        *,
        install_root: Path,
        attempted_version: str,
        stage: UpdateRollbackStage,
        error: BaseException,
    ) -> None:
        """Record one successfully rolled-back update failure."""


def launch_prepared_update(
    *,
    layout: InstallLayout,
    command: Sequence[str],
    attempted_version: str,
    environment: Mapping[str, str],
    activation: CandidateUpdateActivation,
    supervisor: CandidateReadinessSupervisor | None = None,
    crash_supervisor: CandidateCrashSupervisor | None = None,
    rollback_reporter: UpdateRollbackReporter = record_update_rollback,
    on_ready: Callable[[], None] | None = None,
    cancellation_requested: Callable[[], bool] | None = None,
) -> None:
    """Commit after visible readiness or restore and relaunch the prior app."""

    readiness_supervisor = supervisor or ApplicationReadinessSupervisor(
        cancellation_requested=cancellation_requested
    )
    crash_owner = crash_supervisor or ApplicationCrashSupervisor()
    prepared = crash_owner.prepare(
        layout=layout,
        environment=packaged_application_environment(environment),
        command=command,
    )
    candidate_process: CandidateProcess | None = None
    try:
        process = readiness_supervisor.launch_until_ready(
            layout=layout,
            command=command,
            environment=prepared.environment,
        )
        candidate_process = process
        if on_ready is not None:
            on_ready()
        try:
            activation.commit()
        except BaseException:
            stop_candidate_process(process)
            raise
    except ApplicationStartupCancelled as cancelled:
        if cancelled.terminated_process is not None:
            crash_owner.supervise_process(
                layout=layout,
                process=cancelled.terminated_process,
                prepared=prepared,
                termination=SupervisedTermination(
                    SupervisedTerminationReason.USER_CANCELLATION
                ),
            )
        activation.rollback()
        _LOGGER.info(
            "Cancelled update startup; restored the previous application without relaunching"
        )
        raise
    except BaseException as candidate_error:
        terminated_process = (
            candidate_error.terminated_process
            if (
                isinstance(candidate_error, ApplicationReadinessError)
                and candidate_error.terminated_process is not None
            )
            else candidate_process
        )
        if terminated_process is not None:
            reason = (
                SupervisedTerminationReason.UPDATE_READINESS_FAILURE
                if isinstance(candidate_error, ApplicationReadinessError)
                else SupervisedTerminationReason.UPDATE_ACTIVATION_FAILURE
            )
            crash_owner.supervise_process(
                layout=layout,
                process=terminated_process,
                prepared=prepared,
                termination=SupervisedTermination(
                    reason,
                    str(candidate_error),
                ),
            )
        activation.reject(type(candidate_error).__name__)
        rollback_reporter(
            install_root=layout.root,
            attempted_version=attempted_version,
            stage=UpdateRollbackStage.CANDIDATE_READINESS,
            error=candidate_error,
        )
        _LOGGER.error(
            "Candidate update failed readiness and was rolled back.",
            exc_info=True,
        )
        crash_owner.supervise(
            layout=layout,
            command=command,
            environment=packaged_application_environment(environment),
        )
        return
    crash_owner.supervise_process(
        layout=layout,
        process=process,
        prepared=prepared,
    )


__all__ = [
    "CandidateCrashSupervisor",
    "CandidateReadinessSupervisor",
    "CandidateUpdateActivation",
    "CandidateUpdateRollbackError",
    "UpdateRollbackReporter",
    "launch_prepared_update",
]
