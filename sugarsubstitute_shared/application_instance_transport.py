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

"""Select fileless application-instance transports for each operating system."""

from __future__ import annotations

import errno
import os
import sys
import time
from typing import Protocol

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInstanceEndpoint,
)


_CONNECT_TIMEOUT_SECONDS = 5.0


class ApplicationInstanceListener(Protocol):
    """Accept framed same-user connections from one native owner endpoint."""

    def accept(self) -> ApplicationInstanceConnection:
        """Accept and authorize one local connection."""

    def close(self) -> None:
        """Release endpoint ownership idempotently."""


class InstanceEndpointUnavailableError(OSError):
    """Report an elected owner whose local endpoint never became available."""


def instance_endpoint(identity: str) -> ApplicationInstanceEndpoint:
    """Map an application identity to one OS-owned fileless endpoint."""

    if os.name == "nt":
        return ApplicationInstanceEndpoint(
            transport="windows-named-pipe",
            address=rf"\\.\pipe\SugarSubstitute-{identity}",
        )
    if sys.platform.startswith("linux"):
        return ApplicationInstanceEndpoint(
            transport="abstract-unix",
            address=f"SugarSubstitute-{identity}",
        )
    port = 32000 + (int(identity[:8], 16) % 20000)
    return ApplicationInstanceEndpoint(
        transport="loopback-tcp",
        address="127.0.0.1",
        port=port,
    )


def bind_instance_listener(
    endpoint: ApplicationInstanceEndpoint,
) -> ApplicationInstanceListener:
    """Atomically claim and listen on one native endpoint."""

    if endpoint.transport == "windows-named-pipe":
        from sugarsubstitute_shared.application_instance_windows import (
            WindowsNamedPipeListener,
        )

        return WindowsNamedPipeListener(endpoint)
    from sugarsubstitute_shared.application_instance_socket import (
        bind_socket_listener,
    )

    return bind_socket_listener(endpoint)


def connect_instance_endpoint(
    endpoint: ApplicationInstanceEndpoint,
) -> ApplicationInstanceConnection:
    """Connect to an elected broker with bounded startup-race retries."""

    deadline = time.monotonic() + _CONNECT_TIMEOUT_SECONDS
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            if endpoint.transport == "windows-named-pipe":
                from sugarsubstitute_shared.application_instance_windows import (
                    connect_windows_named_pipe,
                )

                return connect_windows_named_pipe(endpoint)
            from sugarsubstitute_shared.application_instance_socket import (
                connect_socket_endpoint,
            )

            return connect_socket_endpoint(endpoint)
        except OSError as error:
            last_error = error
            time.sleep(0.025)
    raise InstanceEndpointUnavailableError(
        f"The active application supervisor did not accept IPC: {last_error!r}"
    )


def endpoint_is_already_owned(error: OSError) -> bool:
    """Return whether endpoint creation lost a native atomic election."""

    if os.name == "nt":
        return getattr(error, "winerror", None) in {5, 231}
    return error.errno in {errno.EADDRINUSE, errno.EACCES}


__all__ = [
    "ApplicationInstanceListener",
    "InstanceEndpointUnavailableError",
    "bind_instance_listener",
    "connect_instance_endpoint",
    "endpoint_is_already_owned",
    "instance_endpoint",
]
