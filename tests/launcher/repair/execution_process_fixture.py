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

"""Hold test-owned mutation in a supervised process until its parent cancels it."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Event

from launcher.sugarsubstitute_launcher.repair_execution_protocol import (
    REPAIR_EXECUTION_ENDPOINT_ENV,
    encode_repair_frame,
)
from sugarsubstitute_shared.installation_mutation import installation_mutation


def main() -> None:
    """Authenticate, acquire a disposable fixture root, and wait without a UI."""
    if len(sys.argv) > 2 and sys.argv[2] in {"descendant", "exiting_descendant"}:
        with installation_mutation(Path(sys.argv[1])):
            sys.stdout.write("owned\n")
            sys.stdout.flush()
            if sys.argv[2] == "exiting_descendant":
                sys.stdin.read(1)
                os._exit(73)
            Event().wait(60)
        return
    endpoint = json.loads(os.environ[REPAIR_EXECUTION_ENDPOINT_ENV])
    mode = sys.argv[2] if len(sys.argv) > 2 else "freeze"
    with socket.create_connection(
        ("127.0.0.1", endpoint["port"]), timeout=10
    ) as connection:
        connection.sendall(
            encode_repair_frame(
                {"kind": "ready", "token": endpoint["token"], "pid": os.getpid()}
            )
        )
        with installation_mutation(Path(sys.argv[1])):
            if mode.endswith("_child"):
                mode = mode.removesuffix("_child")
                exiting_child = mode.endswith("_exiting")
                mode = mode.removesuffix("_exiting")
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "tests.launcher.repair.execution_process_fixture",
                        str(Path(sys.argv[1]) / "descendant"),
                        "exiting_descendant" if exiting_child else "descendant",
                    ],
                    stdin=subprocess.PIPE if exiting_child else subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    text=True,
                )
                assert child.stdout is not None
                assert child.stdout.readline() == "owned\n"
                child.stdout.close()
                if exiting_child:
                    assert child.stdin is not None
                    child.stdin.write("x")
                    child.stdin.close()
            connection.sendall(
                encode_repair_frame(
                    {
                        "kind": "progress",
                        "stage": "validate_input",
                        "completed": 0,
                        "total": 1,
                    }
                )
            )
            if mode == "crash":
                os._exit(73)
            if mode == "freeze":
                connection.settimeout(60)
                connection.recv(1)
        if mode == "succeeded":
            connection.sendall(encode_repair_frame({"kind": "succeeded"}))
        elif mode == "failed":
            connection.sendall(
                encode_repair_frame(
                    {"kind": "failed", "details": "fixture repair failure"}
                )
            )


if __name__ == "__main__":
    main()
