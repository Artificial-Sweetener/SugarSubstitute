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

"""Bound pytest worker tests even when native code retains the interpreter lock."""

from __future__ import annotations

import faulthandler
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO


class PytestWorkerTimeoutGuard:
    """Own one worker's native-safe timeout and persistent active-test evidence."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        evidence_directory: Path,
        worker_id: str,
    ) -> None:
        """Store the worker timeout policy without creating normal-run artifacts."""

        self._timeout_seconds = timeout_seconds
        self._evidence_directory = evidence_directory
        self._worker_id = worker_id
        self._evidence_path = evidence_directory / (
            f"pytest-worker-{worker_id}-{os.getpid()}.txt"
        )
        self._evidence_file: BinaryIO | None = None
        self._armed = False

    @contextmanager
    def guard_test(self, nodeid: str) -> Generator[None, None, None]:
        """Bound one complete test lifecycle and retain evidence on abrupt exit."""

        if self._timeout_seconds <= 0:
            yield
            return

        evidence_file = self._prepare_active_evidence(nodeid)
        faulthandler.dump_traceback_later(
            self._timeout_seconds,
            repeat=False,
            file=evidence_file,
            exit=True,
        )
        self._armed = True
        try:
            yield
        finally:
            self._disarm()
            self._write_evidence(status="idle", nodeid=nodeid)

    def close_cleanly(self) -> None:
        """Remove worker evidence only after pytest finishes the session cleanly."""

        self._disarm()
        evidence_file = self._evidence_file
        self._evidence_file = None
        if evidence_file is not None:
            evidence_file.close()
        self._evidence_path.unlink(missing_ok=True)

    def _prepare_active_evidence(self, nodeid: str) -> BinaryIO:
        """Open the worker evidence file and publish the active test identity."""

        evidence_file = self._evidence_file
        if evidence_file is None:
            self._evidence_directory.mkdir(parents=True, exist_ok=True)
            evidence_file = self._evidence_path.open("w+b")
            self._evidence_file = evidence_file
        self._write_evidence(status="active", nodeid=nodeid)
        return evidence_file

    def _write_evidence(self, *, status: str, nodeid: str) -> None:
        """Replace the worker marker with its current lifecycle state."""

        evidence_file = self._evidence_file
        if evidence_file is None:
            raise RuntimeError("pytest worker evidence is not open")
        evidence = (
            f"status={status}\n"
            f"worker={self._worker_id}\n"
            f"pid={os.getpid()}\n"
            f"nodeid={nodeid}\n"
            f"timeout_seconds={self._timeout_seconds:g}\n"
        ).encode("utf-8")
        evidence_file.seek(0)
        evidence_file.truncate()
        evidence_file.write(evidence)
        evidence_file.flush()

    def _disarm(self) -> None:
        """Cancel the process-global fault timer when this owner armed it."""

        if not self._armed:
            return
        faulthandler.cancel_dump_traceback_later()
        self._armed = False


__all__ = ["PytestWorkerTimeoutGuard"]
