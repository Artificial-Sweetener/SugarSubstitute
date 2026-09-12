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

"""Verify launcher activation is acknowledged only by a real window paint."""

from __future__ import annotations

import threading

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

from launcher.sugarsubstitute_launcher.ui.instance_presentation import (
    LauncherInstancePresenter,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInvocation,
)


class _PresentationResult(QObject):
    """Publish one worker result into the owning Qt event loop."""

    completed = Signal(object)


def _present_from_worker(
    presenter: LauncherInstancePresenter,
    result: list[str | None],
) -> tuple[threading.Thread, _PresentationResult]:
    """Start presentation and publish its result without polling Qt manually."""

    completion = _PresentationResult()

    def present() -> None:
        presented = presenter.present(ApplicationInvocation.capture(["Substitute"]))
        result.append(presented)
        completion.completed.emit(presented)

    worker = threading.Thread(target=present)
    worker.start()
    return worker, completion


def _wait_for_presentation(completion: _PresentationResult) -> None:
    """Wait for one observable presentation result with a hard Qt deadline."""

    event_loop = QEventLoop()
    completed = False

    def finish(_result: object) -> None:
        nonlocal completed
        completed = True
        event_loop.quit()

    completion.completed.connect(finish)
    QTimer.singleShot(3_000, event_loop.quit)
    event_loop.exec()
    assert completed


def test_hidden_launcher_is_revealed_and_painted_before_acknowledgement(
    qt_application_owner: QApplication,
) -> None:
    """Treat a hidden recovery window as present only after its next paint."""

    window = QWidget()
    presenter = LauncherInstancePresenter(window)
    result: list[str | None] = []

    try:
        worker, completion = _present_from_worker(presenter, result)
        _wait_for_presentation(completion)
        worker.join(timeout=1.0)

        assert result == ["QWidget"]
        assert window.isVisible()
    finally:
        window.close()
        window.deleteLater()
        qt_application_owner.processEvents()


def test_offscreen_launcher_is_recovered_before_acknowledgement(
    qt_application_owner: QApplication,
) -> None:
    """A live but inaccessible setup window must return to an available monitor."""

    window = QWidget()
    window.resize(480, 320)
    window.move(100_000, 100_000)
    window.show()
    qt_application_owner.processEvents()
    presenter = LauncherInstancePresenter(window)
    result: list[str | None] = []
    try:
        worker, completion = _present_from_worker(presenter, result)
        _wait_for_presentation(completion)
        worker.join(timeout=1.0)

        assert result == ["QWidget"]
        assert any(
            window.frameGeometry().intersects(screen.availableGeometry())
            for screen in QGuiApplication.screens()
        )
    finally:
        window.close()
        window.deleteLater()
        qt_application_owner.processEvents()
