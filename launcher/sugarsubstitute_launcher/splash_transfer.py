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

"""Transfer splash presentation while retaining cleanup in the creating supervisor."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
import json
from uuid import UUID

from sugarsubstitute_shared.launch_splash.client import SocketSplashSessionClient
from sugarsubstitute_shared.launch_splash.session import (
    SplashSessionSpec,
    splash_cancel_signal_path,
    splash_session_args,
    splash_session_from_args,
)

_SPLASH_TRANSFER_ENV = "SUGAR_SUBSTITUTE_DELEGATED_SPLASH_SESSION"


@dataclass(frozen=True, slots=True)
class BorrowedSplashSession:
    """Use one existing surface while the native supervisor retains its process handle."""

    client: SocketSplashSessionClient
    resource_identity: str
    release: Callable[[str], None]

    @property
    def app_arguments(self) -> tuple[str, ...]:
        """Continue the same authenticated session into the application child."""
        return tuple(splash_session_args(self.client.spec))

    def present(self) -> str | None:
        """Present the existing surface without starting another host."""
        return "startup-splash" if self.client.activate() else None

    def cancellation_requested(self) -> bool:
        """Observe only this session's cancellation signal."""
        return splash_cancel_signal_path(self.client.spec).is_file()

    def ensure_closed(self) -> None:
        """Request bounded cleanup through the original authenticated owner."""
        self.release(self.resource_identity)

    def close(self) -> None:
        """Use the same idempotent owner operation for explicit closure."""
        self.ensure_closed()


def export_splash_session(
    spec: SplashSessionSpec, *, resource_identity: str
) -> dict[str, str]:
    """Serialize presentation credentials and exact cleanup identity for one child."""
    if UUID(resource_identity).hex != resource_identity:
        raise ValueError("Invalid splash cleanup identity.")
    return {
        _SPLASH_TRANSFER_ENV: json.dumps(
            {
                "schema_version": 1,
                "resource_identity": resource_identity,
                "arguments": splash_session_args(spec),
            }
        )
    }


def take_borrowed_splash_session(
    environment: MutableMapping[str, str],
    *,
    release: Callable[[str], None],
) -> BorrowedSplashSession | None:
    """Consume one child handoff without leaking transfer authority to descendants."""
    raw = environment.pop(_SPLASH_TRANSFER_ENV, None)
    if raw is None:
        return None
    payload = json.loads(raw)
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
    ):
        raise ValueError("Invalid splash handoff schema.")
    identity = payload.get("resource_identity")
    if not isinstance(identity, str) or UUID(identity).hex != identity:
        raise ValueError("Invalid splash cleanup identity.")
    raw_arguments = payload.get("arguments")
    if not isinstance(raw_arguments, list):
        raise ValueError("Invalid splash handoff arguments.")
    arguments: list[str] = []
    for argument in raw_arguments:
        if not isinstance(argument, str):
            raise ValueError("Invalid splash handoff argument.")
        arguments.append(argument)
    spec = splash_session_from_args(arguments)
    if spec is None:
        raise ValueError("Splash handoff session is missing.")
    return BorrowedSplashSession(SocketSplashSessionClient(spec), identity, release)
