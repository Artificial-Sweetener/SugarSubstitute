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

"""Verify recovery from the initial downloaded-launcher installation failure."""

from __future__ import annotations

from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tests.launcher.installation_workflow.support import (
    close_and_delete_launcher_window,
    release_source_for_test,
    wait_for_launcher_condition,
    workflow_factory,
)
from tests.launcher.support import launcher_test_application


def test_initial_install_failure_restores_editable_retry_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed launcher install should restore path editing and the install action."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")

    class _FailingFirstRunInstaller:
        """Fail the first launcher installation stage."""

        def install_downloaded_launcher(
            self,
            *,
            install_root: Path,
            release_source: object,
            handoff_geometry: str | None,
            launch_installed: bool,
        ) -> object:
            """Raise a representative filesystem installation failure."""

            _ = (install_root, release_source, handoff_geometry, launch_installed)
            raise OSError("launcher copy failed")

    monkeypatch.setattr(
        "launcher.sugarsubstitute_launcher.ui.main_window._current_frozen_executable",
        lambda: tmp_path / "SugarSubstitute-Setup-Windows-x64.exe",
    )
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(
            artifact_installer=_FailingFirstRunInstaller(),
        ),
    )

    window.view.primary_button.click()
    wait_for_launcher_condition(
        application,
        lambda: not window.execution.initial_running,
    )

    assert window.view.primary_button.text() == "Install"
    assert window.view.primary_button.isEnabled() is True
    assert window.view.install_path_edit.isEnabled() is True
    assert window.view.browse_button is not None
    assert window.view.browse_button.isEnabled() is True
    assert "launcher copy failed" in (window.view.progress_log.log_view.toPlainText())
    close_and_delete_launcher_window(window)
