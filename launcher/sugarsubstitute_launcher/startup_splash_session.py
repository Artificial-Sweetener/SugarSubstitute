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

"""Define startup presentation independently of splash-process ownership."""

from typing import Protocol

from sugarsubstitute_shared.launch_splash.client import SocketSplashSessionClient


class StartupSplashSession(Protocol):
    """Expose one splash session to launch orchestration and delegated clients."""

    @property
    def client(self) -> SocketSplashSessionClient:
        """Return the authenticated presentation client."""

    @property
    def app_arguments(self) -> tuple[str, ...]:
        """Return the existing app-level session handoff arguments."""

    def present(self) -> str | None:
        """Present the existing startup surface."""

    def cancellation_requested(self) -> bool:
        """Observe cancellation scoped to this splash session."""

    def ensure_closed(self) -> None:
        """Ask the process owner to ensure its splash has exited."""

    def close(self) -> None:
        """Close through the process owner without acquiring PID-based authority."""
