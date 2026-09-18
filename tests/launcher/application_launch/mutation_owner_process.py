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

"""Hold a real installation operation while servicing no recovery requests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys

from sugarsubstitute_shared.installation_mutation import installation_mutation


def main() -> None:
    """Signal native ownership, then wait only for fixture teardown or termination."""
    root, port, nonce = sys.argv[1:]
    with installation_mutation(Path(root)):
        with socket.create_connection(("127.0.0.1", int(port)), timeout=30) as channel:
            channel.sendall(
                json.dumps({"pid": os.getpid(), "nonce": nonce}).encode() + b"\n"
            )
            channel.recv(1)


if __name__ == "__main__":
    main()
