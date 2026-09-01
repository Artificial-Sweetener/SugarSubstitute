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

"""Verify production recovery and zero-model onboarding page contracts."""

from pathlib import Path

from PySide6.QtWidgets import QLabel

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.experience_models import (
    ExperiencePage,
    ModelCardPresentation,
    RepairChoice,
)
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from sugarsubstitute_shared.model_discovery.models import ModelCategory
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


def test_model_onboarding_starts_unchecked_and_records_explicit_selection(
    tmp_path: Path,
) -> None:
    """Neither interests nor provider-ranked model files may be preselected."""

    window = LauncherMainWindow(
        initial_layout=InstallLayout.from_root(tmp_path / "SugarSubstitute"),
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(),
    )
    window.view.show_model_interests((ModelCategory.CHECKPOINTS, ModelCategory.LORAS))
    assert window.view.experience_snapshot().selected_categories == ()

    card = ModelCardPresentation(
        category=ModelCategory.CHECKPOINTS,
        model_name="Safe sample",
        version_name="v1",
        creator="Creator",
        base_model="SDXL",
        size_bytes=1024**3,
        destination=tmp_path / "models" / "checkpoints",
    )
    window.view.show_model_gallery((card,))
    unchecked = window.view.experience_snapshot()
    assert unchecked.visible_models == (card.identity,)
    assert unchecked.selected_models == ()

    window.view.model_gallery_page.set_model_selected(card.identity, selected=True)

    assert window.view.experience_snapshot().selected_models == (card.identity,)
    close_and_delete_launcher_window(window)
