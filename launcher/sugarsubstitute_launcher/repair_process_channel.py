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

"""Own authenticated child-side observations for supervised repair operations."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import json
import os
import socket
from threading import Lock
from typing import Self

from launcher.sugarsubstitute_launcher.repair_execution_protocol import (
    REPAIR_EXECUTION_ENDPOINT_ENV,
    encode_repair_frame,
)


class RepairProcessChannel:
    """Serialize bounded observations on the authenticated parent connection."""

    def __init__(self, connection: socket.socket) -> None:
        """Retain the operation's sole output connection and frame-write lock."""
        self._connection = connection
        self._lock = Lock()

    @classmethod
    @contextmanager
    def connect(cls) -> Iterator[Self]:
        """Consume the supervisor capability before connecting or loading operation inputs."""
        raw_endpoint = os.environ.pop(REPAIR_EXECUTION_ENDPOINT_ENV, "")
        if not raw_endpoint or len(raw_endpoint) > 4096:
            raise ValueError("Repair execution requires its supervisor capability.")
        endpoint = json.loads(raw_endpoint)
        if not isinstance(endpoint, dict):
            raise ValueError("Repair execution endpoint must be an object.")
        port, token = endpoint.get("port"), endpoint.get("token")
        if (
            type(port) is not int
            or not 0 < port < 65536
            or not isinstance(token, str)
            or len(token) != 64
        ):
            raise ValueError("Repair execution endpoint is malformed.")
        with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
            connection.settimeout(5)
            output = cls(connection)
            output.send({"kind": "ready", "token": token, "pid": os.getpid()})
            yield output

    def send(self, message: Mapping[str, object]) -> None:
        """Write a bounded complete frame without interleaving concurrent observations."""
        frame = encode_repair_frame(message)
        with self._lock:
            self._connection.sendall(frame)

    def output(self, line: str) -> None:
        """Bound each diagnostic observation independently of full process logs."""
        self.send({"kind": "output", "details": line[:4096]})
