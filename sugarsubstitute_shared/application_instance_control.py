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

"""Address and contact the running application's local control channel."""

from __future__ import annotations

from enum import Enum
import hashlib
import os
from pathlib import Path
from typing import cast


class ApplicationShutdownRequestResult(str, Enum):
    """Describe one attempt to ask the active application to close."""

    ACCEPTED = "accepted"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"


def application_instance_control_name(install_root: Path) -> str:
    """Return one deterministic per-user, per-installation local-server name."""

    normalized_root = os.path.normcase(str(install_root.expanduser().resolve()))
    identity = f"{normalized_root}\0{_current_user_identity()}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"SugarSubstitute-{digest}"


def request_active_application_shutdown(
    install_root: Path,
    *,
    timeout_ms: int = 3000,
) -> ApplicationShutdownRequestResult:
    """Ask the active application to enter its coordinated shutdown path."""

    from PySide6.QtNetwork import QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(application_instance_control_name(install_root))
    if not socket.waitForConnected(timeout_ms):
        return ApplicationShutdownRequestResult.UNAVAILABLE
    socket.write(b"shutdown\n")
    socket.flush()
    socket.waitForBytesWritten(timeout_ms)
    socket.waitForReadyRead(timeout_ms)
    response = cast(bytes, socket.readAll().data()).strip()
    socket.disconnectFromServer()
    if response == b"accepted":
        return ApplicationShutdownRequestResult.ACCEPTED
    return ApplicationShutdownRequestResult.REJECTED


def _current_user_identity() -> str:
    """Return a stable local user label without exposing it in the server name."""

    if os.name == "nt":
        return os.environ.get("USERNAME", "")
    getuid = getattr(os, "getuid", None)
    if callable(getuid):
        return str(getuid())
    return os.environ.get("USER", "")


__all__ = [
    "ApplicationShutdownRequestResult",
    "application_instance_control_name",
    "request_active_application_shutdown",
]
