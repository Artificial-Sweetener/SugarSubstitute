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

"""Own startup presentation for each application run within one broker lifetime."""

from __future__ import annotations
from collections.abc import Sequence
from launcher.sugarsubstitute_launcher.application_launch import (
    installed_application_environment,
)
from launcher.sugarsubstitute_launcher.application_lifecycle_supervisor import (
    ApplicationLifecycleSupervisor,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.splash_session import (
    append_splash_session_args,
    start_launcher_splash_session,
)
from launcher.sugarsubstitute_launcher.startup_splash_session import (
    StartupSplashSession,
)
from sugarsubstitute_shared.application_broker_session import ApplicationBrokerSession


class InstalledApplicationSupervisor:
    """Keep every run's presentation, command and cancellation on the same session."""

    def __init__(
        self,
        *,
        broker: ApplicationBrokerSession,
        layout: InstallLayout,
        command: Sequence[str],
        locale_override: str,
        remote_failure_reason: str | None,
    ) -> None:
        """Retain stable installation inputs independently from replaceable processes."""
        self._broker = broker
        self._layout = layout
        self._command = tuple(command)
        self._locale_override = locale_override
        self._remote_failure_reason = remote_failure_reason

    def supervise(self, *, splash_session: StartupSplashSession | None) -> None:
        """Supervise each authorized run with fresh startup ownership on restart."""
        while True:
            self._supervise_run(splash_session)
            if not self._broker.consume_restart_request():
                return
            splash_session = self._start_splash()

    def supervise_requested_restart(self) -> None:
        """Continue a completed update run only when its child requested restart."""
        if self._broker.consume_restart_request():
            self.supervise(splash_session=self._start_splash())

    def complete_startup(self, splash_session: StartupSplashSession | None) -> None:
        """Transfer presentation to the ready child and retire its startup process."""
        self._broker.bind_startup_presenter(None)
        if splash_session is not None:
            splash_session.ensure_closed()

    def _start_splash(self) -> StartupSplashSession | None:
        """Create a new session rather than inheriting retired process credentials."""
        return start_launcher_splash_session(
            layout=self._layout, locale_override=self._locale_override
        )

    def _supervise_run(self, splash_session: StartupSplashSession | None) -> None:
        """Bind all startup collaborators to one run and release them on every exit."""
        self._broker.bind_startup_presenter(
            (lambda _invocation: splash_session.present())
            if splash_session is not None
            else None
        )
        try:
            supervisor = ApplicationLifecycleSupervisor(
                cancellation_requested=splash_session.cancellation_requested
                if splash_session is not None
                else None
            )
            supervisor.supervise(
                layout=self._layout,
                command=append_splash_session_args(self._command, splash_session),
                environment=installed_application_environment(
                    self._broker, remote_failure_reason=self._remote_failure_reason
                ),
                on_ready=lambda: self.complete_startup(splash_session),
            )
        finally:
            self._broker.bind_startup_presenter(None)
            if splash_session is not None:
                splash_session.close()
