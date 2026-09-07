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

"""Verify the standalone installer's visible onboarding surface."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QFrame, QWidget

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import (
    LauncherOperatingSystem,
    detect_launcher_target,
)
from launcher.sugarsubstitute_launcher.ui.installer_qualification import (
    InstallerQualificationDriver,
)
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from launcher.sugarsubstitute_launcher.ui.installer_presentation import LauncherUiState
from sugarsubstitute_shared.installer_qualification import InstallerQualificationPlan
from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_BRAND_BAR_HEIGHT,
    INSTALLER_WORDMARK_OPTICAL_Y_OFFSET,
    INSTALLER_WINDOW_HEIGHT,
    INSTALLER_WINDOW_WIDTH,
    InstallerBrandBar,
    InstallerBodyMaterialSurface,
)
from sugarsubstitute_shared.presentation.terminal import TerminalOutputView
from tests.launcher.support import launcher_test_application
from tests.launcher.installation_workflow.support import (
    close_and_delete_launcher_window,
    release_source_for_test,
    wait_for_launcher_condition,
    workflow_factory,
)


def test_launcher_initial_screen_matches_onboarding_step_one_shell(
    tmp_path: Path,
) -> None:
    """The downloaded setup UI should present itself as onboarding step one."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(),
    )
    window.show()
    application.processEvents()

    assert window.width() == INSTALLER_WINDOW_WIDTH
    assert window.height() == INSTALLER_WINDOW_HEIGHT
    assert window.titleBar.minBtn.isHidden() is True
    assert window.titleBar.maxBtn.isHidden() is True
    assert window.titleBar.height() == INSTALLER_BRAND_BAR_HEIGHT
    assert window.titleBar.closeBtn.geometry().top() == 0
    assert window.titleBar.closeBtn.geometry().right() == window.titleBar.rect().right()
    assert window.titleBar.canDrag(QPoint(600, INSTALLER_BRAND_BAR_HEIGHT - 8))
    assert window.ui_state.name == LauncherUiState.SELECT_LANGUAGE.name
    assert window.view.progress_count_label.text() == "Step 1 of 5 · Language"
    assert isinstance(window.view.brand_bar, InstallerBrandBar)
    assert isinstance(window.view.content_panel, InstallerBodyMaterialSurface)
    assert window.view.brand_bar.wordmark.isVisible() is True
    wordmark_top = window.view.brand_bar.wordmark.mapTo(
        window.view.brand_bar,
        QPoint(0, 0),
    ).y()
    centered_wordmark_top = (
        window.view.brand_bar.height() - window.view.brand_bar.wordmark.height()
    ) // 2
    assert wordmark_top == centered_wordmark_top + INSTALLER_WORDMARK_OPTICAL_Y_OFFSET
    assert window.view.language_combo.objectName() == "LauncherLanguageSelector"
    viewport_center = window.view.page_stage.viewport().mapToGlobal(
        window.view.page_stage.viewport().rect().center()
    )
    page_center = window.view.language_page.mapToGlobal(
        window.view.language_page.rect().center()
    )
    combo_center = window.view.language_combo.mapToGlobal(
        window.view.language_combo.rect().center()
    )
    language_badge = window.view.language_page.findChild(
        QFrame,
        "OnboardingHeroBadge",
    )
    assert language_badge is not None
    visible_left = language_badge.mapToGlobal(language_badge.rect().topLeft()).x()
    visible_right = window.view.language_description_label.mapToGlobal(
        window.view.language_description_label.rect().topRight()
    ).x()
    visible_center = (visible_left + visible_right) // 2
    assert abs(page_center.x() - viewport_center.x()) <= 1
    assert abs(combo_center.x() - viewport_center.x()) <= 1
    assert abs(visible_center - viewport_center.x()) <= 1
    assert window.view.language_description_label.height() == (
        window.view.language_description_label.sizeHint().height()
    )
    assert window.view.primary_button.text() == "Continue"
    assert window.view.findChild(QWidget, "OnboardingStepItem") is None
    window.view.primary_button.click()
    assert window.ui_state is LauncherUiState.PREPARE_INSTALL
    assert window.view.progress_count_label.text() == "Step 2 of 5 · Choose a folder"
    assert window.view.install_path_edit.text() == str(layout.root)
    assert window.view.install_path_edit.isEnabled() is True
    assert window.view.browse_button is not None
    assert window.view.browse_button.isEnabled() is True
    assert window.view.primary_button.text() == "Install"
    assert isinstance(window.view.progress_log, TerminalOutputView)
    assert window.view.progress_log.log_view.minimumHeight() == 220
    assert window.view.progress_log.log_view.maximumHeight() == 280
    guidance = window.view.install_location_guidance_label.text()
    target = detect_launcher_target()
    if target.operating_system is LauncherOperatingSystem.WINDOWS:
        assert "Avoid Program Files" in guidance
    elif target.operating_system is LauncherOperatingSystem.MACOS:
        assert "~/Applications/SugarSubstitute" in guidance
    else:
        assert "~/.local/share/SugarSubstitute" in guidance
    assert "Ready." in window.view.progress_log.log_view.toPlainText()
    assert window.view.status_panel is not None
    assert window.view.status_panel.isHidden() is True
    assert "InstallerContentWash" in window.view.styleSheet()
    assert "InstallerBrandBar" in window.view.styleSheet()
    assert "OnboardingSectionPanel" in window.view.styleSheet()
    assert "background: transparent" in window.view.styleSheet()
    assert window.view.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert window.view.brand_bar.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    header_pixel = window.view.grab().toImage().pixelColor(600, 60)
    body_pixel = window.view.grab().toImage().pixelColor(600, 300)
    assert header_pixel.alpha() == 0
    assert body_pixel.alpha() > 0
    close_and_delete_launcher_window(window)


def test_fresh_launcher_window_is_centered_on_its_assigned_screen(
    tmp_path: Path,
) -> None:
    """Center a new setup journey when no process handoff supplied geometry."""

    window = LauncherMainWindow(
        initial_layout=InstallLayout.from_root(tmp_path / "SugarSubstitute"),
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(),
    )

    screen = window.screen()
    assert screen is not None
    assert window.frameGeometry().center() == screen.availableGeometry().center()
    close_and_delete_launcher_window(window)


def test_installer_qualification_clicks_visible_production_install_action(
    tmp_path: Path,
) -> None:
    """Release qualification should click the displayed installer control."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    event_log_path = tmp_path / "installer-events.jsonl"
    window = LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(),
    )
    window.view.primary_requested.disconnect(window._handle_primary_clicked)
    click_count = 0

    def _record_click() -> None:
        """Count the production button signal emitted by QTest."""

        nonlocal click_count
        click_count += 1
        if click_count == 1:
            window._ui_state = LauncherUiState.PREPARE_INSTALL
            window.view.show_install_location()
            window._refresh_primary_button()

    window.view.primary_requested.connect(_record_click)
    window.show()
    application.processEvents()
    driver = InstallerQualificationDriver(
        window=window,
        plan=InstallerQualificationPlan(
            token="installer-click",
            install_root=layout.root,
            endpoint_host="127.0.0.1",
            endpoint_port=8188,
            event_log_path=event_log_path,
            timeout_seconds=5.0,
        ),
    )

    driver.schedule()
    wait_for_launcher_condition(application, lambda: click_count == 2)

    assert click_count == 2
    events = [
        json.loads(line)["event"]
        for line in event_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert events == [
        "installer.language.ready",
        "installer.window.ready",
        "installer.install.clicked",
    ]
    close_and_delete_launcher_window(window)


def test_launcher_page_fits_fixed_window_with_live_output_visible(
    tmp_path: Path,
) -> None:
    """The downloaded installer page should fit before and during install work."""

    application = launcher_test_application()
    window = LauncherMainWindow(
        initial_layout=InstallLayout.from_root(tmp_path / "SugarSubstitute"),
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(),
    )
    window.show()
    application.processEvents()

    try:
        page_stage = window.findChild(QWidget, "OnboardingPageStage")
        page_stack = window.findChild(QWidget, "OnboardingPageStack")
        assert page_stage is not None
        assert page_stack is not None

        for live_output_visible in (False, True):
            if live_output_visible:
                window.view.show_status_output()
                application.processEvents()
            page = window.view.page_stack.currentWidget()
            assert page is not None

            assert page.sizeHint().height() <= page_stage.contentsRect().height()
            assert page_stage.contentsRect().contains(page_stack.geometry())
            assert page_stack.contentsRect().contains(page.geometry())
            top_gap = page_stack.geometry().top() - page_stage.contentsRect().top()
            bottom_gap = (
                page_stage.contentsRect().bottom() - page_stack.geometry().bottom()
            )
            assert abs(top_gap - bottom_gap) <= 2
    finally:
        close_and_delete_launcher_window(window)
