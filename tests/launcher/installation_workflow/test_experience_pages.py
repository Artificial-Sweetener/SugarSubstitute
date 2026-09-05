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

"""Verify the production recovery page contract."""

from pathlib import Path

from PySide6.QtWidgets import QLabel

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.experience_models import (
    ExperiencePage,
    RepairChoice,
)
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tests.launcher.installation_workflow.support import (
    close_and_delete_launcher_window,
    release_source_for_test,
    workflow_factory,
)


def test_explicit_repair_mode_opens_with_application_repair_selected(
    tmp_path: Path,
) -> None:
    """Repair.exe should reveal preservation policy before any workflow starts."""

    window = LauncherMainWindow(
        initial_layout=InstallLayout.from_root(tmp_path / "SugarSubstitute"),
        continue_install=False,
        repair=True,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(),
    )

    snapshot = window.view.experience_snapshot()

    assert snapshot.page is ExperiencePage.REPAIR_SCOPE
    assert snapshot.repair_choice is RepairChoice.APPLICATION
    visible_copy = " ".join(
        label.text() for label in window.view.repair_page.findChildren(QLabel)
    ).lower()
    assert "projects" in visible_copy
    assert "third-party custom nodes" in visible_copy
    assert window.repair_execution.running is False
    close_and_delete_launcher_window(window)
