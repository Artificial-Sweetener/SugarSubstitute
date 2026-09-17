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

"""Project production launcher widgets into deterministic qualification scenarios."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from launcher.sugarsubstitute_launcher.ui.installer_presentation import LauncherUiState
from launcher.sugarsubstitute_launcher.ui.repair_preparation_execution import (
    QtRepairPreparationExecutor,
)


def project_launcher_page(
    window: LauncherMainWindow,
    page: str,
) -> None:
    """Drive real widgets into one deterministic smoke scenario."""

    active_dialog = window.failure_presenter.active_dialog
    if active_dialog is not None:
        active_dialog.hide()
        active_dialog.close()

    if page == "language":
        window.view.show_language_selection()
        return
    if page == "install":
        if window.ui_state is LauncherUiState.SELECT_LANGUAGE:
            window._handle_primary_clicked()
        window.view.show_install_location()
        return
    if page == "install-failure":
        window.view.show_install_location()
        window.view.show_status_output()
        window._handle_initial_install_failed("Simulated disk permission failure")
        return
    if page == "install-complete":
        window.view.show_install_location()
        window.view.status_panel.append_log(
            "Smoke: exact-version application payload verified."
        )
        window.view.status_panel.append_log(
            "Smoke: setup handoff ready; no process was started."
        )
        window.view.show_status_output()
        return
    if page.startswith("repair"):
        window.view.show_repair_scope()
        if page == "repair-full":
            QTest.mouseClick(
                window.view.repair_page.full_comfy_choice,
                Qt.MouseButton.LeftButton,
            )
        elif page == "repair-working":
            window.view.repair_page.set_status(
                "Verifying exact-version files before changing the installation...",
                working=True,
            )
        elif page == "repair-protected-data":
            window.view.repair_page.set_status(
                "Protected data verified: models, projects, outputs, inputs, user data, and third-party nodes are unchanged.",
                working=False,
            )
        elif page == "repair-failure":
            execution = window.findChild(QtRepairPreparationExecutor)
            if execution is None:
                raise RuntimeError("Smoke launcher has no repair preparation executor.")
            execution.failed.emit("Simulated locked application file")
        elif page == "repair-rollback":
            window.view.repair_page.set_status(
                "Validation failed after replacement. The previous application was restored; protected data was unchanged.",
                working=False,
            )
        elif page == "repair-complete":
            window.view.repair_page.set_status(
                "Repair completed and verified. SugarSubstitute is ready to start.",
                working=False,
            )
        return
    raise ValueError(f"Unsupported launcher smoke page: {page}")
