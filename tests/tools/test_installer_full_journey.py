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

"""Qualify the exact launcher-to-Comfy-setup presentation handoff."""

from __future__ import annotations

from pathlib import Path
from typing import Never, cast

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from qfluentwidgets import RadioButton  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from substitute.presentation.onboarding import OnboardingWindow
from tools.install_experience_interactive import run_interactive_full_experience
from tools.install_experience_onboarding import OnboardingCheckSession


def test_full_handoff_presents_installation_root_exactly_once(tmp_path: Path) -> None:
    """Keep the launcher as the sole installation-root decision owner."""

    application = cast(QApplication, QApplication.instance())
    prompt = "Choose where Substitute should keep its setup"
    launcher_prompt_count: int | None = None
    setup_prompt_count: int | None = None
    setup_initial_page: str | None = None
    attempts = 0

    class InertReleaseSource:
        """Reject network metadata access in the no-install walkthrough."""

        def load_manifest(self) -> Never:
            """Fail if the synthetic boundary requests a release manifest."""

            raise AssertionError("Synthetic walkthrough requested a release manifest.")

    def visible_prompt_count(window: object) -> int:
        """Count the exact visible setup-location question on one real window."""

        widget = cast(LauncherMainWindow | OnboardingWindow, window)
        return sum(
            label.text() == prompt and label.isVisible()
            for label in widget.findChildren(QLabel)
        )

    def drive_journey() -> None:
        """Drive the launcher and inspect the first handed-off setup page."""

        nonlocal attempts
        nonlocal launcher_prompt_count
        nonlocal setup_prompt_count
        nonlocal setup_initial_page
        attempts += 1
        onboarding_windows = tuple(
            widget
            for widget in application.topLevelWidgets()
            if isinstance(widget, OnboardingWindow) and widget.isVisible()
        )
        if onboarding_windows:
            onboarding = onboarding_windows[0]
            current_page = onboarding.page_stack.currentWidget()
            setup_initial_page = (
                current_page.objectName() if current_page is not None else None
            )
            setup_prompt_count = visible_prompt_count(onboarding)
            application.exit(0)
            return

        launchers = tuple(
            widget
            for widget in application.topLevelWidgets()
            if isinstance(widget, LauncherMainWindow) and widget.isVisible()
        )
        for launcher in launchers:
            if launcher_prompt_count is None:
                launcher_prompt_count = visible_prompt_count(launcher)
            if launcher.view.primary_button.isEnabled():
                launcher.view.primary_button.click()
        if attempts >= 200:
            application.exit(1)
            return
        QTimer.singleShot(10, drive_journey)

    QTimer.singleShot(0, drive_journey)
    exit_code = run_interactive_full_experience(
        application=application,
        artifact_root=tmp_path / "qualification",
        release_source=InertReleaseSource(),
    )

    assert exit_code == 0
    assert launcher_prompt_count == 1
    assert setup_prompt_count == 0
    assert setup_initial_page == "OnboardingTargetModePage"
    assert launcher_prompt_count + setup_prompt_count == 1
    assert not (tmp_path / "qualification").exists()


def test_existing_models_answer_precedes_inline_picker(tmp_path: Path) -> None:
    """Keep Yes/No and directory browsing as two separate user actions."""

    application = cast(QApplication, QApplication.instance())
    selected_folder = tmp_path / "existing-models"
    chooser_calls: list[tuple[str, str]] = []

    def choose_directory(_parent: QWidget, title: str, initial: str) -> str:
        """Record the explicit browse action without opening a native dialog."""

        chooser_calls.append((title, initial))
        return str(selected_folder)

    session = OnboardingCheckSession(
        install_root=tmp_path / "install",
        install_root_locked=True,
        directory_chooser=choose_directory,
    )
    window = session.window
    window.show()
    application.processEvents()
    try:
        assert window.page_stack.currentWidget() is window.target_mode_page
        window.primary_button.click()
        application.processEvents()
        assert window.page_stack.currentWidget() is window.managed_local_page

        window.primary_button.click()
        application.processEvents()
        assert window.page_stack.currentWidget() is window.existing_models_question_page
        assert not isinstance(
            window.existing_models_question_page.yes_button,
            RadioButton,
        )
        assert not isinstance(
            window.existing_models_question_page.no_button,
            RadioButton,
        )
        assert chooser_calls == []

        window.existing_models_question_page.yes_button.click()
        application.processEvents()
        assert chooser_calls == []
        assert window.page_stack.currentWidget() is window.existing_models_question_page

        window.primary_button.click()
        application.processEvents()
        assert window.page_stack.currentWidget() is window.folder_setup_page
        assert chooser_calls == []
        assert window.folder_setup_page.model_path_block.isHidden() is False
        assert window.folder_setup_page.managed_model_root_edit.text() == ""
        assert window.primary_button.isEnabled() is False
        model_edit = window.folder_setup_page.managed_model_root_edit
        output_edit = window.folder_setup_page.output_root_edit
        model_bottom = model_edit.mapTo(window, QPoint(0, model_edit.height())).y()
        output_top = output_edit.mapTo(window, QPoint(0, 0)).y()
        assert model_edit.isVisible()
        assert model_edit.width() > 0
        assert model_bottom < output_top

        window.folder_setup_page.managed_model_browse_button.click()
        application.processEvents()
        assert len(chooser_calls) == 1
        assert window.folder_setup_page.managed_model_root_edit.text() == str(
            selected_folder
        )
        assert window.primary_button.isEnabled()
    finally:
        session.close()
