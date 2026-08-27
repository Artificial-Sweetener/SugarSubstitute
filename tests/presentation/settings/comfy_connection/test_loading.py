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

"""Test non-blocking Comfy connection snapshot loading."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QSignalSpy

from tests.presentation.settings.comfy_connection.support import (
    FakeComfyConnectionService,
    ThreadedRunnerFactory,
    build_page,
    managed_target,
)


def test_comfy_connection_page_initial_load_is_async(tmp_path: Path) -> None:
    """Constructing the page should not block on connection snapshot loading."""

    service = FakeComfyConnectionService(managed_target(tmp_path), block_load=True)
    threaded_factory = ThreadedRunnerFactory()
    page = build_page(
        tmp_path,
        service=service,
        task_runner_factory=threaded_factory,
    )
    try:
        assert service.load_started.wait(timeout=5.0)
        assert service.load_finished is False
        assert threaded_factory.runner is not None
        completed = QSignalSpy(threaded_factory.runner.taskCompleted)
        delivery_loop = QEventLoop()
        failure_timeout = QTimer()
        failure_timeout.setSingleShot(True)
        threaded_factory.runner.taskCompleted.connect(delivery_loop.quit)
        failure_timeout.timeout.connect(delivery_loop.quit)
        assert service.load_release is not None
        service.load_release.set()
        failure_timeout.start(5_000)
        delivery_loop.exec()
        delivered_before_timeout = failure_timeout.isActive()
        failure_timeout.stop()

        assert delivered_before_timeout, "snapshot result was not delivered"
        assert completed.count() == 1
        assert service.load_finished is True
        assert page.host_edit.text() == "127.0.0.1"
        assert page.save_button.isEnabled() is False
    finally:
        if service.load_release is not None:
            service.load_release.set()
        threaded_factory.shutdown()
        page.close()
