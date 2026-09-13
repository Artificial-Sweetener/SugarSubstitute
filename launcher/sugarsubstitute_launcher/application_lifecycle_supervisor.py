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

from collections.abc import Callable, Mapping, Sequence

from launcher.sugarsubstitute_launcher.application_readiness_supervisor import (
    ApplicationReadinessError,
    ApplicationReadinessSupervisor,
)
from launcher.sugarsubstitute_launcher.crash_supervisor import (
    ApplicationCrashSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_readiness import ApplicationReadinessSurface


class ApplicationLifecycleSupervisor:
    """Require a visible shell before supervising the remaining process lifetime."""

    def __init__(self) -> None:
        """Create the readiness and crash owners for one launch sequence."""

        self._readiness = ApplicationReadinessSupervisor(
            accepted_surfaces=(
                ApplicationReadinessSurface.MAIN_SHELL,
                ApplicationReadinessSurface.ONBOARDING,
            )
        )
        self._crash = ApplicationCrashSupervisor()

    def supervise(
        self,
        *,
        layout: InstallLayout,
        command: Sequence[str],
        environment: Mapping[str, str],
        on_ready: Callable[[], None] | None = None,
    ) -> int:
        """Start, prove, and classify one application process."""

        prepared = self._crash.prepare(layout=layout, environment=environment)
        try:
            process = self._readiness.launch_until_ready(
                layout=layout,
                command=command,
                environment=prepared.environment,
            )
        except ApplicationReadinessError as error:
            if error.terminated_process is not None:
                self._crash.supervise_process(
                    layout=layout,
                    process=error.terminated_process,
                    prepared=prepared,
                )
            raise
        if on_ready is not None:
            on_ready()
        return self._crash.supervise_process(
            layout=layout,
            process=process,
            prepared=prepared,
        )


__all__ = ["ApplicationLifecycleSupervisor"]
