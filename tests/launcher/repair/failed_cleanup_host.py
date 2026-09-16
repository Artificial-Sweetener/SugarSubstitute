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

"""Exercise automatic repair-host retirement with a failed native kill boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QThread, QTimer, Slot
from PySide6.QtWidgets import QApplication
import pytest

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.repair.request import (
    PreparedRepairRequest,
)
from launcher.sugarsubstitute_launcher.process_execution import (
    ChildProcess,
    spawn_supervised_process,
)
from launcher.sugarsubstitute_launcher import repair_execution_supervisor as supervision
from launcher.sugarsubstitute_launcher.ui.repair_controller import RepairController
from launcher.sugarsubstitute_launcher.ui.repair_window import RepairWindow
from launcher.sugarsubstitute_launcher.ui.repair_worker import RepairWorker
from sugarsubstitute_shared.installation_mutation import (
    installation_mutation,
    InstallationMutationBusyError,
)


class FailedTermination:
    """Retain a real native family while failing only its external kill operation."""

    def __init__(self, process: ChildProcess) -> None:
        """Keep the native handle alive until the disposable host process exits."""
        self.process = process

    @property
    def pid(self) -> int:
        """Expose the actual retained root identity."""
        return self.process.pid

    def poll(self) -> int | None:
        """Observe the real process without altering its lifetime."""
        return self.process.poll()

    def wait(self, timeout: float | None = None) -> int:
        """Keep real native exit confirmation at the process boundary."""
        return self.process.wait(timeout)

    def kill(self) -> None:
        """Inject a kernel-operation failure while the real child remains alive."""
        raise OSError("Injected native family termination failure")

    def terminate(self) -> None:
        """Apply the same failure to either form of forced termination."""
        self.kill()


def main() -> int:
    """Close a real offscreen repair host with a live mutation-owning descendant."""
    root = Path(sys.argv[1])
    application = QApplication(sys.argv[:1])
    request = PreparedRepairRequest(
        root,
        RepairScope.APPLICATION,
        "1.2.3",
        "stable",
        "windows_x64",
        root / "staged-app",
        root / "staged-launcher",
        "a" * 64,
        "b" * 64,
    )
    retained: list[FailedTermination] = []

    def start(
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        startup_log_path: Path,
    ) -> tuple[ChildProcess, Path]:
        """Replace only native termination, preserving actual spawn and containment."""
        process, log = spawn_supervised_process(
            command,
            environment=environment,
            startup_log_path=startup_log_path,
        )
        boundary = FailedTermination(process)
        retained.append(boundary)
        return boundary, log

    window = RepairWindow()
    supervisor = supervision.RepairExecutionSupervisor(
        command_builder=lambda candidate: (
            sys.executable,
            "-m",
            "tests.launcher.repair.execution_process_fixture",
            str(candidate.install_root),
            "freeze_child",
        )
    )

    class CloseAfterProgress(QObject):
        """Deliver the fixture's close request on the window's owning Qt thread."""

        @Slot(object)
        def cancel_owned_work(self, _value: object) -> None:
            """Prove both locks are held before requesting the ordinary window close."""
            assert QThread.currentThread() is application.thread()
            for directory in (root, root / "descendant"):
                with pytest.raises(InstallationMutationBusyError):
                    with installation_mutation(directory):
                        pytest.fail("Fixture did not retain mutation ownership")
            (root / "cancellation-observed.txt").write_text(
                "both-owned", encoding="utf-8"
            )
            window.close()

    observer = CloseAfterProgress(window)

    def worker_factory(candidate: PreparedRepairRequest) -> RepairWorker:
        """Use production Qt adaptation and request close on actual child progress."""
        worker = RepairWorker(candidate, supervisor=supervisor)
        worker.progress.connect(observer.cancel_owned_work)
        return worker

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(supervision, "spawn_supervised_process", start)
        controller = RepairController(window, request, worker_factory=worker_factory)
        QTimer.singleShot(0, controller.start)
        window.show()
        return int(application.exec())


if __name__ == "__main__":
    raise SystemExit(main())
