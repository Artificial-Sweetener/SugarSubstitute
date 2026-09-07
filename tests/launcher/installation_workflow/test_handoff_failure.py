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

"""Verify recovery from failed installed-application handoff."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tests.launcher.installation_workflow.support import (
    advance_to_install_location,
    close_and_delete_launcher_window,
    release_source_for_test,
    wait_for_launcher_condition,
    workflow_factory,
)
from tests.launcher.support import launcher_test_application


def test_launcher_handoff_failure_keeps_open_setup_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed setup handoff should leave a retry action instead of a dead end."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    class _FakeLayoutInstaller:
        """Return a prepared install layout."""

        def prepare(self, install_root: Path) -> object:
            """Return the prepared layout."""

            assert install_root == layout.root
            return SimpleNamespace(layout=layout)

    class _FakeFirstRunInstaller:
        """Return an app command that the process starter will reject."""

        def continue_install(
            self, *, layout: InstallLayout, release_source: object
        ) -> object:
            """Return a fake continued install result."""

            _ = release_source
            return SimpleNamespace(
                layout=layout,
                app_version="0.4.0",
                app_command=["missing-python.exe", str(layout.app_entrypoint)],
            )

    class _FakeRuntimeInstaller:
        """Succeed runtime provisioning for handoff failure coverage."""

        def provision(self, *, layout: InstallLayout) -> object:
            """Return a successful runtime provisioning marker."""

            _ = layout
            return SimpleNamespace(python_executable=layout.runtime_python)

    def _fail_handoff(_command: Sequence[str]) -> None:
        """Raise the same broad failure class as subprocess startup."""

        raise OSError("missing-python.exe was not found")

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.application.installation.release_source_policy.discover_local_release_root",
        lambda: tmp_path / ".local-release-channel",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(
            layout_preparer=_FakeLayoutInstaller(),
            artifact_installer=_FakeFirstRunInstaller(),
            runtime_provisioner=_FakeRuntimeInstaller(),
            process_starter=_fail_handoff,
        ),
    )

    advance_to_install_location(window)
    window.view.primary_button.click()
    window.view.primary_button.click()
    wait_for_launcher_condition(
        application,
        lambda: window.view.primary_button.text() == "Open setup",
    )

    assert window.view.primary_button.text() == "Open setup"
    assert window.view.primary_button.isEnabled() is True
    assert (
        "Could not start SugarSubstitute setup."
        in window.view.progress_log.log_view.toPlainText()
    )
    wait_for_launcher_condition(
        application,
        lambda: not window.execution.setup_running,
    )
    close_and_delete_launcher_window(window)
