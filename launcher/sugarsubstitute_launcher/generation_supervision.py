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

"""Contain a selected launcher before exposing fallback to its baseline."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_execution import spawn_supervised_process


class GenerationStartupError(RuntimeError):
    """Report a failure before a selected process family became live."""


class LauncherGenerationSupervisor:
    """Keep selected process lifetime failures distinct from safe startup fallback."""

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
    ) -> int:
        """Supervise the generation and reap its family before propagating errors."""
        crash = ApplicationCrashSupervisor()
        try:
            prepared = crash.prepare(layout=layout, environment=environment)
            process, _log_path = spawn_supervised_process(
                command, environment=prepared.environment, allow_handoff=True
            )
        except (OSError, ValueError) as error:
            raise GenerationStartupError("Selected launcher could not start") from error
        try:
            return crash.supervise_process(
                layout=layout, process=process, prepared=prepared
            ).return_code
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10.0)
            raise
