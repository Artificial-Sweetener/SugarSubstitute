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

"""Verify responsive Qt coordination for Comfy environment observation."""

from __future__ import annotations

from pathlib import Path
from threading import Event
import time
from typing import cast

from PySide6.QtWidgets import QApplication

from substitute.application.onboarding.comfy_environment_service import (
    ComfyEnvironmentService,
    ComfyPreflightSnapshot,
)
from substitute.app.bootstrap.onboarding_execution import (
    create_onboarding_environment_submitter,
)
from substitute.domain.onboarding import (
    ComfyPythonDiscoveryResult,
    ComfyPythonProbeResult,
    LocalComfyTerminationResult,
)
from substitute.presentation.onboarding.comfy_environment_coordinator import (
    ComfyEnvironmentCoordinator,
)
from tests.execution_test_helpers import ExecutionRuntimeStub


_APPLICATION: QApplication | None = None


def _application() -> QApplication:
    """Keep one GUI application alive for this worker's remaining Qt tests."""

    global _APPLICATION
    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        _APPLICATION = instance
    elif _APPLICATION is None:
        _APPLICATION = QApplication([])
    return _APPLICATION


class _BlockingEnvironmentService:
    """Hold one preflight scan so the owner-thread behavior can be observed."""

    def __init__(self) -> None:
        """Create explicit worker-entry and release gates."""

        self.entered = Event()
        self.release = Event()

    def inspect_preflight(self) -> ComfyPreflightSnapshot:
        """Wait in the worker until the test permits delivery."""

        self.entered.set()
        if not self.release.wait(timeout=5.0):
            raise TimeoutError("Test did not release the environment scan.")
        return ComfyPreflightSnapshot(processes=())

    def discover_attached_python(self, workspace: Path) -> ComfyPythonDiscoveryResult:
        """Return unused automatic-discovery evidence."""

        _ = workspace
        return ComfyPythonDiscoveryResult(binding=None, probes=())

    def validate_browsed_python(
        self,
        *,
        workspace: Path,
        executable: Path,
    ) -> ComfyPythonProbeResult:
        """Reject an unused browse operation."""

        _ = workspace, executable
        raise AssertionError("Browse is not part of this test.")

    def close_processes(self, processes: object) -> LocalComfyTerminationResult:
        """Reject an unused termination operation."""

        _ = processes
        raise AssertionError("Termination is not part of this test.")


def test_preflight_scan_does_not_block_qt_owner_thread() -> None:
    """A slow process scan should leave the onboarding owner thread responsive."""

    app = _application()
    service = _BlockingEnvironmentService()
    execution_runtime = ExecutionRuntimeStub()
    submitter = create_onboarding_environment_submitter(execution_runtime, app)
    coordinator = ComfyEnvironmentCoordinator(
        service=cast(ComfyEnvironmentService, service),
        submitter=submitter,
        close_submitter=submitter.close,
        poll_interval_milliseconds=10_000,
    )
    snapshots: list[ComfyPreflightSnapshot] = []
    coordinator.preflight_changed.connect(snapshots.append)

    started = time.monotonic()
    coordinator.start_preflight()
    elapsed = time.monotonic() - started

    assert elapsed < 0.1
    assert service.entered.wait(timeout=1.0)
    assert snapshots == []

    service.release.set()
    deadline = time.monotonic() + 2.0
    while not snapshots and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    assert snapshots == [ComfyPreflightSnapshot(processes=())]
    coordinator.shutdown()


def test_leaving_page_suppresses_in_flight_monitor_result() -> None:
    """A completed scan should not update UI after its owning page is left."""

    app = _application()
    service = _BlockingEnvironmentService()
    execution_runtime = ExecutionRuntimeStub()
    submitter = create_onboarding_environment_submitter(execution_runtime, app)
    coordinator = ComfyEnvironmentCoordinator(
        service=cast(ComfyEnvironmentService, service),
        submitter=submitter,
        close_submitter=submitter.close,
        poll_interval_milliseconds=10_000,
    )
    snapshots: list[ComfyPreflightSnapshot] = []
    coordinator.preflight_changed.connect(snapshots.append)

    coordinator.start_preflight()
    assert service.entered.wait(timeout=1.0)
    coordinator.stop_monitoring()
    service.release.set()

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    assert snapshots == []
    coordinator.shutdown()
