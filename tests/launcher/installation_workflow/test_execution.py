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

"""Verify Qt installation execution lifecycle boundaries."""

from __future__ import annotations

from pathlib import Path

from launcher.sugarsubstitute_launcher.application.installation.models import (
    InstalledApplication,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.installation_execution import (
    QtInstallationExecutor,
)
from tests.launcher.installation_workflow.support import (
    wait_for_launcher_condition,
    workflow_factory,
)
from tests.launcher.support import launcher_test_application


def test_setup_execution_finishes_only_after_worker_thread_stops(
    tmp_path: Path,
) -> None:
    """Setup completion is published only after its worker thread has stopped."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    executor = QtInstallationExecutor(workflow_factory=workflow_factory())
    events: list[tuple[str, bool]] = []
    executor.setup_succeeded.connect(
        lambda: events.append(("succeeded", executor.setup_running))
    )
    executor.setup_finished.connect(
        lambda: events.append(("finished", executor.setup_running))
    )
    installed_application = InstalledApplication(
        layout=layout,
        app_command=("python.exe", "main.py"),
        app_version="0.4.0",
        launcher_installed=True,
    )

    assert executor.start_setup(
        application=installed_application,
        setup_command=installed_application.app_command,
    )
    wait_for_launcher_condition(application, lambda: not executor.setup_running)

    assert events == [("succeeded", True), ("finished", False)]
