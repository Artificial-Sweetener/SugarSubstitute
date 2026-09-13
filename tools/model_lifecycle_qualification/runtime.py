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

"""Own shared runtime evidence and semantic waiting for model probes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import sys

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import substitute
from substitute._version import __version__
import sugarsubstitute_shared


def runtime_evidence() -> dict[str, str]:
    """Return exact runtime and source provenance for durable evidence."""

    return {
        "application_version": __version__,
        "python_executable": str(Path(sys.executable).resolve()),
        "substitute_source": str(Path(substitute.__file__ or "").resolve()),
        "shared_source": str(Path(sugarsubstitute_shared.__file__ or "").resolve()),
    }


def wait_until(
    application: QApplication,
    condition: Callable[[], bool],
    description: str,
) -> None:
    """Process Qt work until an observable condition or a hard deadline."""

    if condition():
        return
    event_loop = QEventLoop()
    probe = QTimer()
    probe.setInterval(10)

    def observe() -> None:
        """Finish when the requested production state becomes observable."""

        if condition():
            event_loop.quit()

    probe.timeout.connect(observe)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(event_loop.quit)
    probe.start()
    deadline.start(5_000)
    event_loop.exec()
    probe.stop()
    if not condition():
        raise TimeoutError(f"Timed out waiting for {description}.")
    application.processEvents()


__all__ = ["runtime_evidence", "wait_until"]
