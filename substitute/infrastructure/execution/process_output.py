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

"""Own non-blocking binary output collection for native child processes."""

from __future__ import annotations

from queue import Empty, Queue
import subprocess
from threading import Thread


class BinaryProcessOutput:
    """Collect one native process pipe without blocking its supervising thread."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        """Start one short-lived output reader for the supplied process."""

        self._process = process
        self._chunks: Queue[bytes | None] = Queue()
        self._thread = Thread(
            target=self._read,
            name="native-process-output-reader",
            daemon=True,
        )
        self._thread.start()

    def take(self, *, wait_seconds: float = 0.25) -> bytes | None:
        """Return one available output chunk within the bounded wait."""

        try:
            return self._chunks.get(timeout=wait_seconds)
        except Empty:
            return None

    def join(self, *, timeout_seconds: float = 5.0) -> None:
        """Wait briefly for the reader to consume the closed process pipe."""

        self._thread.join(timeout=timeout_seconds)

    def _read(self) -> None:
        """Read bounded chunks until the process closes its output pipe."""

        if self._process.stdout is None:
            self._chunks.put(None)
            return
        while chunk := self._process.stdout.read(4096):
            self._chunks.put(chunk)
        self._chunks.put(None)
