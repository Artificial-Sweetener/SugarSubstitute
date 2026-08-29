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

"""Verify local duplicate-launch shutdown requests."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import cast

from PySide6.QtCore import QEventLoop, QProcess, QTimer

from substitute.app.bootstrap.application_instance_control import (
    bind_application_instance_shutdown_request,
    start_application_instance_control,
    stop_application_instance_control,
)
from sugarsubstitute_shared.application_instance_control import (
    ApplicationShutdownRequestResult,
    request_active_application_shutdown,
)
from tests.support.qt.lifecycle import ensure_qt_application


def test_control_server_routes_shutdown_to_composed_coordinator(tmp_path: Path) -> None:
    """A duplicate invocation should reach the normal shutdown request port."""

    _ = ensure_qt_application()
    requests: list[object | None] = []
    start_application_instance_control(tmp_path)
    bind_application_instance_shutdown_request(requests.append)
    script = (
        "import sys;from pathlib import Path;"
        "from sugarsubstitute_shared.application_instance_control import "
        "request_active_application_shutdown;"
        "print(request_active_application_shutdown(Path(sys.argv[1])).value,flush=True)"
    )
    process = QProcess()
    process.setProgram(sys.executable)
    process.setArguments(["-c", script, str(tmp_path)])
    completion_loop = QEventLoop()
    process.finished.connect(completion_loop.quit)
    try:
        process.start()
        assert process.waitForStarted(5_000)
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(completion_loop.quit)
        timeout.start(10_000)
        if process.state() is not QProcess.ProcessState.NotRunning:
            completion_loop.exec()
        stdout = cast(bytes, process.readAllStandardOutput().data()).decode()
        stderr = cast(bytes, process.readAllStandardError().data()).decode()
    finally:
        if process.state() is not QProcess.ProcessState.NotRunning:
            process.kill()
            assert process.waitForFinished(5_000)
        stop_application_instance_control()

    assert requests == [None]
    assert stderr == ""
    assert stdout.strip() == ApplicationShutdownRequestResult.ACCEPTED.value


def test_control_request_reports_unavailable_without_server(tmp_path: Path) -> None:
    """A stale record must not be mistaken for a reachable application."""

    _ = ensure_qt_application()
    stop_application_instance_control()

    assert (
        request_active_application_shutdown(tmp_path, timeout_ms=25)
        is ApplicationShutdownRequestResult.UNAVAILABLE
    )
