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

"""Block only the HTTPS read boundary inside the production preparation child."""

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
from unittest.mock import patch

from launcher.sugarsubstitute_launcher.__main__ import run_launcher
from sugarsubstitute_shared.launcher_update.persistence import write_json_atomic


class BlockedResponse:
    """Expose an uncooperative response after optional descendant ownership is live."""

    def __init__(self, root: Path, descendant: bool) -> None:
        """Retain fixture-only signaling and process settings."""
        self._root = root
        self._descendant = descendant

    def read(self) -> bytes:
        """Wait beyond the UI cancellation bound without consulting application events."""
        child_pid: int | None = None
        if self._descendant:
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tests.launcher.repair.execution_process_fixture",
                    str(self._root / "descendant"),
                    "descendant",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text=True,
            )
            assert child.stdout is not None
            assert child.stdout.readline() == "owned\n"
            child.stdout.close()
            child_pid = child.pid
        write_json_atomic(
            self._root / "blocked.json", {"pid": os.getpid(), "child_pid": child_pid}
        )
        Event().wait(60)
        raise TimeoutError("Blocked response was not cancelled by its owner")


def main() -> int:
    """Use production bootstrap and service with only HTTPS response I/O substituted."""
    input_argument, root, mode = sys.argv[1:]

    @contextmanager
    def blocked_request(*args: object, **kwargs: object) -> Iterator[BlockedResponse]:
        """Keep the source adapter's context management and parsing path intact."""
        del args, kwargs
        yield BlockedResponse(Path(root), mode == "descendant")

    sys.argv = [sys.argv[0], input_argument]
    with patch("urllib.request.urlopen", blocked_request):
        return run_launcher()


if __name__ == "__main__":
    raise SystemExit(main())
