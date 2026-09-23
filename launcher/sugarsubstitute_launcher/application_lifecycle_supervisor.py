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

"""Own visible-readiness and crash classification for one application run."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from pathlib import Path
import logging

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.application_startup_contract import (
    ApplicationStartupCancelled,
    CandidateProcess,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.supervised_termination import (
    SupervisedTermination,
    SupervisedTerminationReason,
)
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface


class ApplicationLifecycleSupervisor:
    """Coordinate visible readiness and authoritative terminal process classification."""

    def __init__(
        self,
        *,
        accepted_surfaces: Collection[ApplicationReadinessSurface] = (
            ApplicationReadinessSurface.MAIN_SHELL,
            ApplicationReadinessSurface.ONBOARDING,
        ),
        readiness_timeout_seconds: float | None = None,
        readiness_supervisor: ApplicationReadinessSupervisor | None = None,
        crash_supervisor: ApplicationCrashSupervisor | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        process_starter: Callable[
            [Sequence[str], Mapping[str, str]], tuple[CandidateProcess, Path]
        ]
        | None = None,
    ) -> None:
        """Create or adopt readiness and crash owners for one visible launch policy."""

        if readiness_supervisor is not None:
            self._readiness = readiness_supervisor
        elif readiness_timeout_seconds is None:
            self._readiness = ApplicationReadinessSupervisor(
                accepted_surfaces=accepted_surfaces,
                cancellation_requested=cancellation_requested,
                process_starter=process_starter,
            )
        else:
            self._readiness = ApplicationReadinessSupervisor(
                accepted_surfaces=accepted_surfaces,
                timeout_seconds=readiness_timeout_seconds,
                cancellation_requested=cancellation_requested,
                process_starter=process_starter,
            )
        self._crash = crash_supervisor or ApplicationCrashSupervisor()

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
        on_ready: Callable[[], None] | None = None,
    ) -> int:
        """Start, prove, and classify one application process."""

        prepared = self._crash.prepare(
            layout=layout,
            environment=environment,
            command=command,
        )
        try:
            process = self._readiness.launch_until_ready(
                layout=layout,
                command=command,
                environment=prepared.environment,
            )
        except ApplicationStartupCancelled as cancelled:
            if cancelled.terminated_process is not None:
                self._crash.supervise_process(
                    layout=layout,
                    process=cancelled.terminated_process,
                    prepared=prepared,
                    termination=SupervisedTermination(
                        SupervisedTerminationReason.USER_CANCELLATION
                    ),
                )
            raise
        except ApplicationReadinessError as error:
            if error.terminated_process is not None:
                outcome = self._crash.supervise_process(
                    layout=layout,
                    process=error.terminated_process,
                    prepared=prepared,
                    present_report=False,
                    termination=SupervisedTermination(
                        SupervisedTerminationReason.READINESS_FAILURE,
                        str(error),
                        error.diagnostics,
                    ),
                )
                if outcome.incident_id is None:
                    logging.getLogger(__name__).info(
                        "Application closed cleanly before primary surface readiness | "
                        "process_id=%s | exit_code=%s",
                        error.terminated_process.pid,
                        outcome.return_code,
                    )
                    return outcome.return_code
                error.incident_id = outcome.incident_id
            raise
        if on_ready is not None:
            on_ready()
        return self._crash.supervise_process(
            layout=layout,
            process=process,
            prepared=prepared,
        ).return_code


__all__ = ["ApplicationLifecycleSupervisor"]
