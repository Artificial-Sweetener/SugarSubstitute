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

"""Execute prepared repair inside a parent-owned, Qt-free worker process."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import logging
import os
from pathlib import Path
import socket
from threading import Lock

from launcher.sugarsubstitute_launcher.application.repair.progress import RepairProgress
from launcher.sugarsubstitute_launcher.repair_execution_protocol import (
    REPAIR_EXECUTION_ENDPOINT_ENV,
    encode_repair_frame,
)

_LOGGER = logging.getLogger(__name__)


def run_repair_execution_invocation(arguments: Sequence[str]) -> int | None:
    """Accept one private request only when an execution-control capability exists."""
    prefix = "--repair-worker-request="
    values = [
        argument.removeprefix(prefix)
        for argument in arguments
        if argument.startswith(prefix)
    ]
    if not values:
        return None
    if len(arguments) != 1 or len(values) != 1 or not values[0]:
        raise ValueError("Repair execution requires exactly one request path.")
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
    from launcher.sugarsubstitute_launcher.repair_helper import run_prepared_repair

    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        connection.settimeout(5)
        output = _RepairExecutionOutput(connection)
        output.send({"kind": "ready", "token": token, "pid": os.getpid()})
        try:
            run_prepared_repair(
                Path(values[0]),
                progress_observer=output.progress,
                output_callback=output.output,
            )
        except Exception as error:
            _LOGGER.exception("Supervised repair execution failed")
            output.send({"kind": "failed", "details": str(error)[:4096]})
            return 1
        output.send({"kind": "succeeded"})
        return 0


class _RepairExecutionOutput:
    """Serialize concurrent executor observations on one bounded connection."""

    def __init__(self, connection: socket.socket) -> None:
        """Retain only the worker's authenticated parent transport."""
        self._connection = connection
        self._lock = Lock()

    def send(self, message: Mapping[str, object]) -> None:
        """Prevent interleaving frames from subprocess-output and execution threads."""
        frame = encode_repair_frame(message)
        with self._lock:
            self._connection.sendall(frame)

    def progress(self, progress: RepairProgress) -> None:
        """Project the transaction's authoritative progress without inferring stages."""
        self.send(
            {
                "kind": "progress",
                "stage": progress.stage.value if progress.stage is not None else None,
                "completed": progress.completed,
                "total": progress.total,
            }
        )

    def output(self, line: str) -> None:
        """Bound each diagnostic update independently of full process logging."""
        self.send({"kind": "output", "details": line[:4096]})
