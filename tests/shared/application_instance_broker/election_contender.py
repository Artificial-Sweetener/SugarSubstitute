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

"""Coordinate an independent native election contender through a test socket."""

from pathlib import Path
import socket
import sys

from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import ApplicationInvocation


def main() -> None:
    """Wait at the start barrier, elect once, and retain ownership until released."""
    root, port = Path(sys.argv[1]), int(sys.argv[2])
    with socket.create_connection(("127.0.0.1", port), timeout=20) as connection:
        with connection.makefile("rwb", buffering=0) as stream:
            stream.write(b"ready\n")
            assert stream.readline() == b"go\n"
            broker = ApplicationInstanceBroker.elect(
                install_root=root,
                invocation=ApplicationInvocation.capture(("fixture",)),
            )
            try:
                if broker is not None:
                    broker.bind_startup_presenter(lambda _request: "fixture-surface")
                stream.write(b"owner\n" if broker is not None else b"forwarded\n")
                assert stream.readline() == b"exit\n"
            finally:
                if broker is not None:
                    broker.close()


if __name__ == "__main__":
    main()
