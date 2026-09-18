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
from sugarsubstitute_shared.asset_transfer import TransferProgress

from PySide6.QtWidgets import QLabel, QProgressBar, QWidget

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.experience_models import (
    ExperiencePage,
    RepairChoice,
)
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from launcher.sugarsubstitute_launcher.ui.experience_pages import RepairScopePage
from tests.launcher.support import launcher_test_application
from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
    PreparationStage,
)
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
    assert window.view.repair_page.findChildren(QWidget, "OnboardingHeroEyebrow") == []
    assert window.repair_preparation.running is False
    close_and_delete_launcher_window(window)


def test_repair_preparation_has_a_visible_progress_bar() -> None:
    """Show a Fluent activity bar for the whole immutable preparation interval."""
    application = launcher_test_application()
    page = RepairScopePage()
    page.show()
    try:
        page.set_status("Synthetic preparation in progress", working=True)
        application.processEvents()
        bars = page.findChildren(QProgressBar)
        assert any(bar.isVisible() for bar in bars)
        page.set_status("Synthetic preparation stopped", working=False)
        assert all(not bar.isVisible() for bar in bars)
    finally:
        page.set_status("", working=False)
        page.close()
        page.deleteLater()
        application.processEvents()


def test_preparation_fill_tracks_reported_stages_and_survives_status_updates() -> None:
    """Keep stage completion separate from changing descriptive status text."""
    application = launcher_test_application()
    page = RepairScopePage()
    page.show()
    try:
        page.set_status("Synthetic preparation", working=True)
        view = page.preparation_progress
        view.set_progress(PreparationProgress(PreparationStage.APPLICATION))
        bar = page.findChild(QProgressBar, "RepairPreparationProgress")
        assert bar is not None and bar.isVisible()
        first_value = bar.value()
        assert 0 < first_value < bar.maximum()
        page.set_status("Synthetic preparation still active", working=True)
        assert bar.value() == first_value
        view.set_progress(
            PreparationProgress(PreparationStage.APPLICATION, TransferProgress(50, 100))
        )
        middle_value = bar.value()
        assert first_value < middle_value < bar.maximum()
        view.set_progress(
            PreparationProgress(
                PreparationStage.APPLICATION, TransferProgress(100, 100)
            )
        )
        assert middle_value < bar.value() < bar.maximum()
        view.set_progress(PreparationProgress(PreparationStage.VERIFY_LAUNCHER))
        assert first_value < bar.value() < bar.maximum()
        view.set_progress(PreparationProgress(PreparationStage.READY))
        assert bar.value() == bar.maximum()
    finally:
        page.set_status("", working=False)
        page.close()
        page.deleteLater()
        application.processEvents()
