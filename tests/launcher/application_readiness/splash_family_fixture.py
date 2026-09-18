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

"""Exercise launcher splash creation with an uncooperative synthetic host."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Event

from launcher.sugarsubstitute_launcher import splash_session
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tests.launcher.application_readiness.process_family_fixture import command


class _RuntimeLayout(InstallLayout):
    """Substitute only installed runtime locations for a native fixture."""

    @property
    def runtime_python(self) -> Path:
        """Execute the repository interpreter without copying an installation."""
        return Path(sys.executable)

    @property
    def app_dir(self) -> Path:
        """Resolve the synthetic payload from the repository's test package."""
        return Path(__file__).resolve().parents[3]


def main() -> None:
    """Publish a ready splash family or retain its production session owner."""
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
        port = int(sys.argv[2])
        (root / "fixture-channel.json").write_text(json.dumps(port), encoding="utf-8")
        splash_session._HOST_MODULE = __name__
        session = splash_session.start_launcher_splash_session(
            layout=_RuntimeLayout.from_root(root), locale_override=None
        )
        assert session is not None
        try:
            _publish("owner", port)
            Event().wait(60)
        finally:
            session.close()
        return
    root = Path.cwd()
    port = int(json.loads((root / "fixture-channel.json").read_text(encoding="utf-8")))
    with subprocess.Popen(
        command("leaf", port, root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ) as leaf:
        try:
            sys.stderr.write("synthetic splash diagnostic\n")
            sys.stderr.flush()
            sys.stdout.write(
                json.dumps(
                    {
                        "type": "ready",
                        "endpoint": "127.0.0.1:49152",
                        "token": "s" * 32,
                        "host_pid": os.getpid(),
                    }
                )
                + "\n"
            )
            sys.stdout.flush()
            _publish("splash", port)
            Event().wait(60)
        finally:
            leaf.kill()
            leaf.wait(timeout=5)


def _publish(role: str, port: int) -> None:
    """Signal readiness through a test-owned connection before interruption."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
        connection.sendall(json.dumps({"role": role, "pid": os.getpid()}).encode())


if __name__ == "__main__":
    main()
