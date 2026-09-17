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

"""Qualify native worker teardown before launcher owners publish completion."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Never

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, Qt
from PySide6.QtWidgets import QApplication
import pytest
from shiboken6 import isValid

from launcher.sugarsubstitute_launcher.application.installation.models import (
    InstalledApplication,
)
from launcher.sugarsubstitute_launcher.repair_preparation_operation import (
    RepairPreparationOperation,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.installation_execution import (
    QtInstallationExecutor,
)
from launcher.sugarsubstitute_launcher.ui.repair_preparation_execution import (
    QtRepairPreparationExecutor,
)
from tests.launcher.installation_workflow.support import (
    release_source_for_test,
    workflow_factory,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


@pytest.mark.parametrize("stage", ["initial", "runtime", "preparation"])
def test_completion_releases_only_fully_stopped_native_workers(
    stage: str,
    tmp_path: Path,
    qt_application_owner: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observe native exit and deferred deletion at the public completion boundary.

    Substitute only blocking artifact and runtime boundaries. Production workers,
    scheduling, native deferred deletion, and the zero-time join probe remain real.
    """
    started, release, destroyed = Event(), Event(), Event()
    completion: list[tuple[bool, bool]] = []
    native_thread: QThread | None = None
    native_objects: list[QObject] = []

    def fail_external_work(*_args: object, **_kwargs: object) -> Never:
        """Expose a controlled external failure after native cleanup is registered."""
        current = QThread.currentThread()
        assert current is not qt_application_owner.thread()
        probe = QObject()
        native_objects.append(probe)
        probe.destroyed.connect(destroyed.set, Qt.ConnectionType.DirectConnection)
        current.finished.connect(probe.deleteLater)
        started.set()
        if not release.wait(10):
            raise TimeoutError("Native completion fixture was not released")
        raise OSError("Controlled external operation failure")

    def observe_completion() -> None:
        """Record native completion without advancing it or waiting for cleanup."""
        assert native_thread is not None
        completion.append((destroyed.is_set(), native_thread.wait(0)))

    layout = InstallLayout.from_root(tmp_path / "installation")
    owner: QObject
    if stage in {"initial", "runtime"}:
        executor = QtInstallationExecutor(
            workflow_factory=workflow_factory(
                artifact_installer=SimpleNamespace(continue_install=fail_external_work),
                runtime_provisioner=SimpleNamespace(provision=fail_external_work),
            )
        )
        owner = executor
        if stage == "initial":
            executor.initial_finished.connect(observe_completion)
            assert executor.start_initial(
                layout=layout,
                frozen_setup=False,
                release_source=release_source_for_test(),
                handoff_geometry=None,
            )
        else:
            executor.setup_finished.connect(observe_completion)
            application = InstalledApplication(layout, ("unused",), "1.2.3", True)
            assert executor.start_setup(
                application=application, setup_command=("unused",)
            )
    else:
        monkeypatch.setattr(
            RepairPreparationOperation,
            "run",
            fail_external_work,
        )
        preparation = QtRepairPreparationExecutor()
        owner = preparation
        preparation.finished.connect(observe_completion)
        assert preparation.start(
            layout=layout, release_source=release_source_for_test()
        )
    try:
        wait_for_qt_condition(started.is_set)
        threads = owner.findChildren(QThread)
        assert len(threads) == 1
        native_thread = threads[0]
        release.set()
        wait_for_qt_condition(lambda: bool(completion))
        assert completion == [(True, True)], stage
    finally:
        release.set()
        wait_for_qt_condition(lambda: bool(completion))
        if native_thread is not None and isValid(native_thread):
            assert native_thread.wait(10_000)
        owner.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
