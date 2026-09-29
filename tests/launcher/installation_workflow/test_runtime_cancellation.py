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

"""Qualify cancellation through production Qt execution and runtime composition."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.application.installation.composition import (
    build_installation_workflow,
)
from launcher.sugarsubstitute_launcher.application.installation.models import (
    InstalledApplication,
)
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.runtime_models import (
    RuntimeCommandRunner,
    RuntimeProvisioningResult,
)
from launcher.sugarsubstitute_launcher.ui.installation_execution import (
    QtInstallationExecutor,
)
from tests.launcher.installation_workflow.support import wait_for_launcher_condition
from tests.launcher.support import launcher_test_application


class NativeChildExit:
    """Retain the launched child's kernel identity until cancellation completes."""

    def __init__(self, pid: int) -> None:
        """Open a waitable handle before the child can leave the process table."""
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.OpenProcess.argtypes = [
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        self._kernel.OpenProcess.restype = ctypes.c_void_p
        self._kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self._kernel.WaitForSingleObject.restype = ctypes.c_ulong
        self._kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel.CloseHandle.restype = ctypes.c_int
        self._handle = self._kernel.OpenProcess(0x00100000, False, pid)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def has_exited(self) -> bool:
        """Observe the original process, independent of PID-table retirement."""
        result = self._kernel.WaitForSingleObject(self._handle, 0)
        if result == 0:
            return True
        if result == 258:
            return False
        raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        """Release the observation handle after the Qt workflow stops."""
        if not self._kernel.CloseHandle(self._handle):
            raise ctypes.WinError(ctypes.get_last_error())


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("cancelled_attempts", [1, 2])
def test_setup_cancellation_releases_native_command_before_qt_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancelled_attempts: int
) -> None:
    """The UI's cancellation signal must reach the production command owner."""
    app = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path)
    LauncherConfig.from_layout(layout=layout, runtime_setup_pending=True).save(
        layout.config_path
    )
    children: list[NativeChildExit] = []
    handoffs: list[tuple[str, ...]] = []
    failures: list[str] = []
    attempts: list[Path] = []
    completion_cleanup: list[bool] = []

    class ControlledRuntime:
        """Substitute the external package-manager command, retaining its real owner."""

        def __init__(
            self, *, uv_provider: object, runner: RuntimeCommandRunner
        ) -> None:
            """Retain the command runner created by production composition."""
            self._runner = runner

        def provision(self, *, layout: InstallLayout) -> RuntimeProvisioningResult:
            """Run a silent native command until its owner receives cancellation."""
            attempts.append(layout.root)
            script = "import os; print(os.getpid(), flush=True)"
            if len(attempts) <= cancelled_attempts:
                script += "; from threading import Event; Event().wait(20)"
            self._runner.run(
                [
                    sys.executable,
                    "-c",
                    script,
                ],
                cwd=layout.root,
                env=os.environ,
            )
            return RuntimeProvisioningResult(
                layout.runtime_python, layout.app_dir / "requirements.txt"
            )

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.composition.UvManagedRuntimeInstaller",
        ControlledRuntime,
    )
    executor = QtInstallationExecutor(
        workflow_factory=lambda output, progress, activity, cancellation: (
            build_installation_workflow(
                output_callback=output,
                progress_observer=progress,
                activity_callback=activity,
                cancellation=cancellation,
                process_starter=lambda command: handoffs.append(tuple(command)),
            )
        )
    )

    def observe(line: str) -> None:
        """Cancel once the runtime's native child has reported readiness."""
        if line.isdecimal():
            if len(attempts) <= cancelled_attempts:
                children.append(NativeChildExit(int(line)))
                executor.request_cancel()

    executor.log.connect(observe)
    executor.setup_failed.connect(lambda stage, detail: failures.append(detail))
    executor.setup_finished.connect(
        lambda: completion_cleanup.append(
            not executor.setup_running and all(child.has_exited() for child in children)
        )
    )
    try:
        for attempt in range(cancelled_attempts + 1):
            assert executor.start_setup(
                application=InstalledApplication(
                    layout, ("unused",), "qualification", False
                ),
                setup_command=("unused",),
            )
            wait_for_launcher_condition(app, lambda: not executor.setup_running)
            assert len(attempts) == attempt + 1
            assert completion_cleanup == [True] * (attempt + 1)
            assert failures == []
            if attempt < cancelled_attempts:
                assert len(children) == attempt + 1
                assert handoffs == []
                assert LauncherConfig.load(layout.config_path).runtime_setup_pending
            else:
                assert handoffs == [("unused",)]
                assert not LauncherConfig.load(layout.config_path).runtime_setup_pending
    finally:
        executor.request_cancel()
        wait_for_launcher_condition(app, lambda: not executor.setup_running)
        executor.deleteLater()
        app.processEvents()
        for child in children:
            child.close()
