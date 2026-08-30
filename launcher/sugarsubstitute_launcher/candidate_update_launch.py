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
    ApplicationReadinessSupervisor,
    CandidateProcess,
    stop_candidate_process,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process import start_detached
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


class CandidateLaunchGuard(Protocol):
    """Authorize one application process handoff."""

    def initial_handoff_environment(
        self,
        environment: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Return the authorized child environment."""

    def release(self) -> None:
        """Release launch ownership."""


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
    initial_guard: CandidateLaunchGuard,
    activation: CandidateUpdateActivation,
    fallback_guard_factory: Callable[[InstallLayout], CandidateLaunchGuard | None],
    supervisor: CandidateReadinessSupervisor | None = None,
    fallback_process_starter: Callable[..., None] = start_detached,
    rollback_reporter: UpdateRollbackReporter = record_update_rollback,
) -> None:
    """Commit after visible readiness or restore and relaunch the prior app."""

    readiness_supervisor = supervisor or ApplicationReadinessSupervisor()
    try:
        process = readiness_supervisor.launch_until_ready(
            layout=layout,
            command=command,
            environment=packaged_application_environment(
                initial_guard.initial_handoff_environment()
            ),
        )
        try:
            activation.commit()
        except BaseException:
            stop_candidate_process(process)
            raise
    except BaseException as candidate_error:
        activation.rollback()
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
        initial_guard.release()
        fallback_guard = fallback_guard_factory(layout)
        if fallback_guard is None:
            raise CandidateUpdateRollbackError(
                "The previous SugarSubstitute version was restored but could not "
                "acquire launch ownership."
            ) from candidate_error
        try:
            fallback_process_starter(
                command,
                environment=packaged_application_environment(
                    fallback_guard.initial_handoff_environment()
                ),
            )
        except BaseException:
            fallback_guard.release()
            raise


__all__ = [
    "CandidateLaunchGuard",
    "CandidateReadinessSupervisor",
    "CandidateUpdateActivation",
    "CandidateUpdateRollbackError",
    "UpdateRollbackReporter",
    "launch_prepared_update",
]
