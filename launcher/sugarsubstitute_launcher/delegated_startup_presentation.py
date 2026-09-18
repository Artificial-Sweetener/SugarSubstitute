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

"""Retain startup presentation at the supervisor that owns the splash process."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from types import TracebackType

from launcher.sugarsubstitute_launcher.splash_transfer import export_splash_session
from launcher.sugarsubstitute_launcher.startup_splash_session import (
    StartupSplashSession,
)
from sugarsubstitute_shared.application_broker_session import ApplicationBrokerSession
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation


class DelegatedStartupPresentation:
    """Keep activation independent of the replaceable delegated child channel."""

    def __init__(
        self,
        *,
        broker: ApplicationBrokerSession,
        splash: StartupSplashSession,
        register_resource: Callable[[Callable[[], None]], str],
    ) -> None:
        """Bind one presentation lifetime to the existing splash resource owner."""
        self._broker = broker
        self._splash = splash
        self._register_resource = register_resource
        self._active = False
        self._lock = Lock()

    def __enter__(self) -> dict[str, str]:
        """Expose the splash before the selected launcher or app can register."""
        with self._lock:
            self._active = True
        try:
            self._broker.bind_startup_presenter(self._present)
            identity = self._register_resource(self._release_splash)
            return export_splash_session(
                self._splash.client.spec, resource_identity=identity
            )
        except BaseException:
            self._deactivate()
            raise

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release presentation on every terminal path, including baseline fallback."""
        self._deactivate()

    def _present(self, invocation: ApplicationInvocation) -> str | None:
        """Present only this still-active startup's physical surface."""
        with self._lock:
            active = self._active
        return self._splash.present() if active else None

    def _release_splash(self) -> None:
        """Transfer activation at readiness before the creator closes its splash."""
        self._deactivate()
        self._splash.close()

    def _deactivate(self) -> None:
        """Prevent a late release from clearing a subsequent startup's presenter."""
        with self._lock:
            if not self._active:
                return
            self._active = False
            self._broker.bind_startup_presenter(None)
