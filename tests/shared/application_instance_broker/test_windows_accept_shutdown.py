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

"""Verify native pipe accept teardown transfers handle ownership exactly once."""

from __future__ import annotations

from multiprocessing.connection import Connection
from pathlib import Path
import threading

import pytest

from sugarsubstitute_shared.application_instance_election import (
    application_instance_endpoints,
)


@pytest.mark.platforms("windows")
def test_shutdown_owns_accept_connection_during_accept_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Release the endpoint when shutdown interrupts the pending accept operation."""
    import _winapi
    from multiprocessing.connection import PipeConnection

    from sugarsubstitute_shared.application_instance_windows import (
        WindowsNamedPipeListener,
    )

    entered = threading.Event()
    closing = threading.Event()
    accepted = threading.Event()
    closes: list[Connection] = []
    errors: list[BaseException] = []
    original_close = PipeConnection.close

    def interrupted_connect(handle: int, *, overlapped: bool) -> None:
        """Pause the native boundary until shutdown has claimed the connection."""
        del handle, overlapped
        entered.set()
        assert closing.wait(2.0)
        raise OSError("qualification interrupted accept")

    def close_connection(connection: Connection) -> None:
        """Expose overlapping cleanup attempts before releasing the real handle."""
        closes.append(connection)
        if len(closes) == 1:
            closing.set()
            assert accepted.wait(2.0)
        original_close(connection)

    endpoint = application_instance_endpoints(tmp_path)[0]
    listener = WindowsNamedPipeListener(endpoint)
    monkeypatch.setattr(_winapi, "ConnectNamedPipe", interrupted_connect)
    monkeypatch.setattr(PipeConnection, "close", close_connection)

    def accept() -> None:
        """Capture the interrupted accept without leaking a worker exception."""
        try:
            listener.accept()
        except OSError as error:
            errors.append(error)
        finally:
            accepted.set()

    worker = threading.Thread(target=accept)
    worker.start()
    try:
        assert entered.wait(2.0)
        listener.close()
        worker.join(timeout=2.0)
        assert not worker.is_alive()
        assert len(errors) == 1
        assert len(closes) == 1
        replacement = WindowsNamedPipeListener(endpoint)
        replacement.close()
    finally:
        closing.set()
        listener.close()
        worker.join(timeout=2.0)
