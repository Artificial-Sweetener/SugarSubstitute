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

"""Prove selected launcher readiness before accepting its owned lifetime."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

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
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface


class GenerationStartupError(RuntimeError):
    """Report a retired generation that failed before exposing a usable surface."""


class LauncherGenerationSupervisor:
    """Separate safe startup fallback from the lifetime of a usable generation."""

    def __init__(
        self,
        *,
        readiness: ApplicationReadinessSupervisor | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> None:
        """Use the shared readiness owner for process cleanup and cancellation."""
        self._readiness = readiness or ApplicationReadinessSupervisor(
            process_starter=_start_generation,
            cancellation_requested=cancellation_requested,
            accepted_surfaces=(
                ApplicationReadinessSurface.MAIN_SHELL,
                ApplicationReadinessSurface.ONBOARDING,
                ApplicationReadinessSurface.LAUNCHER_WINDOW,
            ),
        )

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> int:
        """Retire failed startup while preserving authenticated Close and handoff."""
        crash = ApplicationCrashSupervisor()
        prepared = crash.prepare(
            layout=layout,
            environment=environment,
            command=command,
        )
        try:
            process = self._readiness.launch_until_ready(
                layout=layout, command=command, environment=prepared.environment
            )
        except ApplicationStartupCancelled as cancelled:
            if cancelled.terminated_process is not None:
                crash.supervise_process(
                    layout=layout,
                    process=cancelled.terminated_process,
                    prepared=prepared,
                    termination=SupervisedTermination(
                        SupervisedTerminationReason.USER_CANCELLATION
                    ),
                )
            return 0
        except ApplicationReadinessError as error:
            if error.terminated_process is not None:
                classified = crash.supervise_process(
                    layout=layout,
                    process=error.terminated_process,
                    prepared=prepared,
                    present_report=False,
                    termination=SupervisedTermination(
                        SupervisedTerminationReason.GENERATION_READINESS_FAILURE,
                        str(error),
                        error.diagnostics,
                    ),
                )
                if classified.return_code == 0 and classified.incident_id is None:
                    return 0
            raise GenerationStartupError(
                "Selected launcher failed visible readiness"
            ) from error
        try:
            return crash.supervise_process(
                layout=layout, process=process, prepared=prepared
            ).return_code
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10.0)
            raise


def _start_generation(
    command: Sequence[str], environment: Mapping[str, str]
) -> tuple[CandidateProcess, Path]:
    """Start a generation inside the same native family boundary as app candidates."""
    try:
        return spawn_supervised_process(
            command, environment=environment, allow_handoff=True
        )
    except (OSError, ValueError) as error:
        raise GenerationStartupError("Selected launcher could not start") from error
