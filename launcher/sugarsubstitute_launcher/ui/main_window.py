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

"""Coordinate the standalone installer window and its application workflow."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, Signal, Slot
from PySide6.QtWidgets import QVBoxLayout
from qframelesswindow import AcrylicWindow  # type: ignore[import-untyped]
from qframelesswindow.titlebar import TitleBar  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.application.installation.models import (
    InstalledApplication,
    ReleaseManifestSource,
)
from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.application.installation.release_source_policy import (
    create_continued_installation_request,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.language_preference import (
    persist_launcher_language_preference,
)
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.resources import launcher_icon
from launcher.sugarsubstitute_launcher.repair_handoff import (
    launch_prepared_repair_helper,
)
from launcher.sugarsubstitute_launcher.ui.installation_execution import (
    QtInstallationExecutor,
)
from launcher.sugarsubstitute_launcher.ui.installation_workers import (
    InstallationWorkflowFactory,
)
from launcher.sugarsubstitute_launcher.ui.installer_errors import (
    launcher_failure_detail,
)
from launcher.sugarsubstitute_launcher.ui.installer_failure_presenter import (
    InstallerFailurePresenter,
)
from launcher.sugarsubstitute_launcher.ui.installer_presentation import (
    LauncherUiState,
    primary_action_for,
)
from launcher.sugarsubstitute_launcher.ui.installer_style import (
    apply_installer_style,
)
from launcher.sugarsubstitute_launcher.ui.installer_view import InstallerView
from launcher.sugarsubstitute_launcher.ui.launcher_theme import (
    configure_launcher_theme,
)
from launcher.sugarsubstitute_launcher.ui.experience_models import RepairChoice
from launcher.sugarsubstitute_launcher.ui.repair_preparation_execution import (
    QtRepairPreparationExecutor,
    require_repair_preparation,
)
from launcher.sugarsubstitute_launcher.ui.window_effects import (
    apply_launcher_window_effects,
)
from launcher.sugarsubstitute_launcher.ui.window_geometry import (
    append_handoff_geometry,
    parse_handoff_geometry,
    serialize_handoff_geometry,
)
from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_BRAND_BAR_HEIGHT,
    INSTALLER_WINDOW_HEIGHT,
    INSTALLER_WINDOW_WIDTH,
    center_installer_window,
)

if TYPE_CHECKING:
    from sugarsubstitute_shared.localization import LanguagePreference
    from sugarsubstitute_shared.presentation.localization import TranslationManager

_LOGGER = logging.getLogger(__name__)


class LauncherMainWindow(AcrylicWindow):  # type: ignore[misc]
    """Present installer state and coordinate asynchronous workflow execution."""

    handoff_completed = Signal()

    def __init__(
        self,
        *,
        initial_layout: InstallLayout,
        continue_install: bool,
        repair: bool,
        update_check_enabled: bool,
        initial_release_source: ReleaseManifestSource,
        workflow_factory: InstallationWorkflowFactory,
        localization_manager: TranslationManager | None = None,
        persist_language_preference: Callable[
            [Path, LanguagePreference], None
        ] = persist_launcher_language_preference,
        handoff_geometry: str | None = None,
    ) -> None:
        """Build the launcher shell and initialize installer state."""

        super().__init__()
        self.setObjectName("LauncherWindow")
        configure_launcher_theme()
        self._initial_layout = initial_layout
        self._continue_install = continue_install
        self._initial_release_source = initial_release_source
        self._workflow_factory = workflow_factory
        self._localization_manager = localization_manager
        self._persist_language_preference = persist_language_preference
        self._handoff_geometry = handoff_geometry
        self._repair_mode = repair
        self.failure_presenter = InstallerFailurePresenter(self)
        self._setup_handoff_close_pending = False
        self._installed_application: InstalledApplication | None = None
        self._setup_command: list[str] | None = None
        self._ui_state = (
            LauncherUiState.INSTALL_APP
            if continue_install
            else (
                LauncherUiState.PREPARE_INSTALL
                if repair
                else LauncherUiState.SELECT_LANGUAGE
            )
        )
        self.execution = QtInstallationExecutor(
            workflow_factory=workflow_factory,
            parent=self,
        )
        self.repair_execution = QtRepairPreparationExecutor(parent=self)
        self.repair_execution.succeeded.connect(self._handle_repair_prepared)
        self.repair_execution.failed.connect(self._handle_repair_preparation_failed)
        self.execution.log.connect(self._append_log)
        self.execution.initial_failed.connect(self._handle_initial_install_failed)
        self.execution.initial_succeeded.connect(self._handle_initial_install_succeeded)
        self.execution.initial_finished.connect(self._handle_initial_install_finished)
        self.execution.setup_failed.connect(self._handle_setup_worker_failed)
        self.execution.setup_succeeded.connect(self._handle_setup_worker_succeeded)
        self.execution.setup_finished.connect(self._handle_setup_execution_finished)

        self._build_shell(initial_layout)
        if self._localization_manager is not None:
            self._localization_manager.languageChanged.connect(
                lambda _snapshot: self._retranslate_window()
            )
        self._append_log(launcher_text("Ready."))
        if continue_install:
            self._append_log(
                launcher_text("Continuing install from installed launcher.")
            )
        if repair:
            self._append_log(launcher_text("Repair mode requested."))
            self.view.show_repair_scope()
            self.view.repair_page.continue_requested.connect(
                self._handle_repair_continue
            )
            self.view.repair_page.cancel_requested.connect(self.close)
        if not update_check_enabled:
            self._append_log(launcher_text("Update check disabled for this launch."))
        self._refresh_primary_button()
        self._apply_handoff_geometry()
        apply_launcher_window_effects(self)
        QTimer.singleShot(0, self._finish_native_shell)
        if continue_install:
            QTimer.singleShot(0, self._install_app_payload)

    def _finish_native_shell(self) -> None:
        """Reapply native material and center its final visible frame once."""

        apply_launcher_window_effects(self)
        if parse_handoff_geometry(self._handoff_geometry) is None:
            center_installer_window(self)

    @property
    def ui_state(self) -> LauncherUiState:
        """Return the installer phase currently projected by the window."""

        return self._ui_state

    def _build_shell(self, initial_layout: InstallLayout) -> None:
        """Compose window chrome around the installer-owned view."""

        self.setWindowTitle(launcher_text("SugarSubstitute Setup"))
        self.setWindowIcon(launcher_icon())
        self.resize(INSTALLER_WINDOW_WIDTH, INSTALLER_WINDOW_HEIGHT)
        self.setFixedSize(INSTALLER_WINDOW_WIDTH, INSTALLER_WINDOW_HEIGHT)
        title_bar = TitleBar(self)
        title_bar.setFixedHeight(INSTALLER_BRAND_BAR_HEIGHT)
        self.setTitleBar(title_bar)
        self.titleBar.maxBtn.hide()
        self.titleBar.minBtn.hide()

        self.view = InstallerView(
            initial_install_path=str(initial_layout.root),
            localization_manager=self._localization_manager,
            show_language_first=(not self._continue_install and not self._repair_mode),
            parent=self,
        )
        self.view.primary_requested.connect(self._handle_primary_clicked)
        self.view.back_requested.connect(self._handle_back_clicked)
        body_layout = QVBoxLayout(self)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.view)
        apply_installer_style(self)
        self.titleBar.raise_()

    def _handle_primary_clicked(self) -> None:
        """Dispatch the primary button according to the current setup state."""

        if self._ui_state is LauncherUiState.SELECT_LANGUAGE:
            self._ui_state = LauncherUiState.PREPARE_INSTALL
            self.view.show_install_location()
            self._refresh_primary_button()
            return
        if self._ui_state is LauncherUiState.PREPARE_INSTALL:
            self._start_initial_install_worker()
            return
        if self._ui_state is LauncherUiState.INSTALL_APP:
            self._install_app_payload()
            return
        if self._ui_state is LauncherUiState.INSTALL_RUNTIME:
            self._start_setup_worker()
            return
        if self._ui_state is LauncherUiState.START_SETUP:
            self._start_setup_handoff()

    def _retranslate_window(self) -> None:
        """Refresh launcher-owned chrome after a language selection changes."""

        self.setWindowTitle(launcher_text("SugarSubstitute Setup"))
        self._refresh_primary_button()

    def _handle_back_clicked(self) -> None:
        """Return from install location to the language-first entry step."""

        if self._ui_state is not LauncherUiState.PREPARE_INSTALL:
            return
        self._ui_state = LauncherUiState.SELECT_LANGUAGE
        self.view.show_language_selection()
        self._refresh_primary_button()

    def _handle_repair_continue(self) -> None:
        """Prepare the explicitly selected repair before detached replacement."""

        if self.repair_execution.running:
            return
        scope = (
            RepairScope.FULL_MANAGED_COMFY
            if self.view.repair_page.choice is RepairChoice.FULL_MANAGED_COMFY
            else RepairScope.APPLICATION
        )
        self.view.repair_page.set_status(
            launcher_text(
                "Downloading and verifying this installer's exact release. "
                "Your active installation has not been changed yet."
            ),
            working=True,
        )
        self.repair_execution.start(
            layout=self._initial_layout,
            release_source=self._initial_release_source,
            scope=scope,
        )

    @Slot(object)
    def _handle_repair_prepared(self, result: object) -> None:
        """Launch the independent helper only after every artifact is verified."""

        try:
            preparation = require_repair_preparation(result)
            request = preparation.request.with_process_behavior(
                wait_pid=None,
                wait_process_created_at=None,
                relaunch=True,
            )
            request.save(preparation.request_path)
            launch_prepared_repair_helper(request_path=preparation.request_path)
        except Exception as error:
            _LOGGER.exception("Could not hand off prepared repair.")
            self._handle_repair_preparation_failed(launcher_failure_detail(error))
            return
        self.view.repair_page.set_status(
            launcher_text("Repair is ready. Closing this window to replace app files."),
            working=True,
        )
        self.handoff_completed.emit()
        QTimer.singleShot(0, self.close)

    @Slot(str)
    def _handle_repair_preparation_failed(self, details: str) -> None:
        """Restore the repair action after a staging or handoff failure."""

        self.view.repair_page.set_status(
            launcher_text(
                "Repair could not be prepared. Nothing in the active installation was changed. Details: %1",
                details,
            ),
            working=False,
        )
        self.failure_presenter.show_failure(
            stage=launcher_text("Prepare repair"),
            details=details,
        )

    def _start_initial_install_worker(self) -> None:
        """Install launcher and app payload in the current setup window."""

        self._show_status_output()
        if self.execution.initial_running:
            return

        install_root = Path(self.view.install_path).expanduser()
        if self._localization_manager is not None:
            self._persist_language_preference(
                install_root,
                self._localization_manager.snapshot.requested,
            )
        self.view.set_primary_action(text=launcher_text("Working..."), enabled=False)
        self.view.set_path_controls_enabled(False)
        self._append_log(launcher_text("Preparing SugarSubstitute install."))

        self.execution.start_initial(
            layout=InstallLayout.from_root(install_root),
            frozen_setup=_current_frozen_executable() is not None,
            release_source=self._initial_release_source,
            handoff_geometry=self._current_handoff_geometry(),
        )

    def _install_app_payload(self) -> None:
        """Install the app source payload for source-run development setup."""

        self._show_status_output()
        try:
            workflow = self._workflow_factory(self._append_log)
            application = workflow.install_application(
                create_continued_installation_request(self._initial_layout)
            )
        except Exception as error:
            self._report_install_failure(error)
            return

        self._accept_installed_application(application)
        self._start_setup_worker()

    def _start_setup_worker(self) -> None:
        """Start runtime provisioning and onboarding handoff in a worker thread."""

        if self.execution.initial_running:
            return
        self._show_status_output()
        if self._installed_application is None:
            self._append_log(launcher_text("Install root is not prepared yet."))
            self._ui_state = LauncherUiState.PREPARE_INSTALL
            self._refresh_primary_button()
            return
        if self._setup_command is None:
            self._append_log(launcher_text("Setup command is not available yet."))
            self._ui_state = LauncherUiState.INSTALL_APP
            self._refresh_primary_button()
            return
        if self.execution.setup_running:
            return

        self.view.set_primary_action(text=launcher_text("Working..."), enabled=False)
        self._append_log(
            launcher_text("Installing Python runtime and app dependencies.")
        )
        self._append_log(launcher_text("This can take a while the first time."))

        self.execution.start_setup(
            application=self._installed_application,
            setup_command=self._setup_command,
        )

    def _start_setup_handoff(self) -> None:
        """Start the installed app so it can enter onboarding/setup routing."""

        self._show_status_output()
        if self._setup_command is None:
            self._append_log(launcher_text("Setup command is not available yet."))
            self._ui_state = LauncherUiState.INSTALL_APP
            self._refresh_primary_button()
            return

        self._append_log(launcher_text("Starting SugarSubstitute setup."))
        try:
            self._workflow_factory(self._append_log).start_setup(self._setup_command)
        except Exception as error:
            self._append_log(launcher_text("Could not start SugarSubstitute setup."))
            self._append_log(launcher_text("Details: %1", error))
            self._ui_state = LauncherUiState.START_SETUP
            self.view.show_failure(
                launcher_text(
                    "Setup could not continue. Review the details and try again."
                )
            )
            self.failure_presenter.show_failure(
                stage=launcher_text("Open setup"),
                details=launcher_failure_detail(error),
            )
            self._refresh_primary_button()
            return

        self._append_log(launcher_text("Started SugarSubstitute setup."))
        self._ui_state = LauncherUiState.COMPLETE
        self._refresh_primary_button()
        self._append_log(launcher_text("Waiting for the setup window to open."))
        self._close_after_successful_handoff()

    @Slot(str)
    def _handle_initial_install_failed(self, details: str) -> None:
        """Render initial install failure and restore the install action."""

        self._append_log(
            launcher_text("Setup failed. Check the details below and try again.")
        )
        self._append_log(launcher_text("Details: %1", details))
        self._ui_state = LauncherUiState.PREPARE_INSTALL
        self.view.show_failure(
            launcher_text("Setup could not continue. Review the details and try again.")
        )
        self.failure_presenter.show_failure(
            stage=launcher_text("Install application"),
            details=details,
        )
        self._refresh_primary_button()

    @Slot(object)
    def _handle_initial_install_succeeded(self, result: object) -> None:
        """Accept installed artifacts while their worker finishes cleanup."""

        if not isinstance(result, InstalledApplication):
            self._handle_initial_install_failed(
                launcher_text("Installer returned an invalid layout.")
            )
            return
        self._accept_installed_application(result)

    def _accept_installed_application(self, application: InstalledApplication) -> None:
        """Store installed artifacts and project their visible completion details."""

        self._installed_application = application
        self._append_log(
            launcher_text(
                "Installed app payload version: %1",
                application.app_version,
            )
        )
        self._append_log(
            launcher_text("App entrypoint: %1", application.layout.app_entrypoint)
        )
        self._setup_command = append_handoff_geometry(
            application.app_command,
            self.frameGeometry(),
        )
        self._ui_state = LauncherUiState.INSTALL_RUNTIME
        self._refresh_primary_button()

    @Slot(str, str)
    def _handle_setup_worker_failed(self, phase: str, details: str) -> None:
        """Render worker failure and restore the matching retry action."""

        if phase == "runtime":
            self._append_log(launcher_text("Could not install the Python runtime."))
            self._ui_state = LauncherUiState.INSTALL_RUNTIME
        else:
            self._append_log(launcher_text("Could not start SugarSubstitute setup."))
            self._ui_state = LauncherUiState.START_SETUP
        self._append_log(launcher_text("Details: %1", details))
        self.view.show_failure(
            launcher_text("Setup could not continue. Review the details and try again.")
        )
        self.failure_presenter.show_failure(stage=phase, details=details)
        self._refresh_primary_button()

    @Slot()
    def _handle_setup_worker_succeeded(self) -> None:
        """Hide the installer and request deterministic worker shutdown."""

        self._ui_state = LauncherUiState.COMPLETE
        self._refresh_primary_button()
        self.hide()
        if not self.execution.setup_running:
            self._close_after_successful_handoff()
            return
        self._setup_handoff_close_pending = True

    def _close_after_successful_handoff(self) -> None:
        """Close the installer after the installed app process has started."""

        self.handoff_completed.emit()
        QTimer.singleShot(0, self.close)

    @Slot()
    def _handle_setup_execution_finished(self) -> None:
        """Complete a successful handoff after its Qt worker has stopped."""

        if self._setup_handoff_close_pending:
            self._setup_handoff_close_pending = False
            self._close_after_successful_handoff()

    @Slot()
    def _handle_initial_install_finished(self) -> None:
        """Advance only after the initial Qt worker has released ownership."""

        if self._ui_state is LauncherUiState.PREPARE_INSTALL:
            self._refresh_primary_button()
            return
        if self._ui_state is LauncherUiState.INSTALL_RUNTIME:
            QTimer.singleShot(0, self._start_setup_worker)

    def _refresh_primary_button(self) -> None:
        """Project the current setup phase onto editable and primary controls."""

        path_controls_enabled = (
            self._ui_state is LauncherUiState.PREPARE_INSTALL
            and not self.execution.initial_running
        )
        self.view.set_path_controls_enabled(path_controls_enabled)
        action = primary_action_for(self._ui_state)
        self.view.set_primary_action(text=action.text, enabled=action.enabled)

    def _report_install_failure(self, error: Exception) -> None:
        """Log one setup failure and show an actionable progress message."""

        _LOGGER.exception("Launcher setup failed.")
        self._append_log(
            launcher_text("Setup failed. Check the details below and try again.")
        )
        self._append_log(launcher_text("Details: %1", launcher_failure_detail(error)))
        self.view.show_failure(
            launcher_text("Setup could not continue. Review the details and try again.")
        )
        self.failure_presenter.show_failure(
            stage=launcher_text("Install application"),
            details=launcher_failure_detail(error),
        )

    @Slot(str)
    def _append_log(self, message: str) -> None:
        """Append one user-visible progress line through the installer view."""

        self.view.append_log(message)

    def _show_status_output(self) -> None:
        """Reveal installer output once setup work has actually started."""

        self.view.show_status_output()

    def _apply_handoff_geometry(self) -> None:
        """Restore handoff placement or center a fresh installer window."""

        geometry = parse_handoff_geometry(self._handoff_geometry)
        if geometry is not None:
            self.setGeometry(geometry)
            return
        center_installer_window(self)

    def _current_handoff_geometry(self) -> str:
        """Return this window's frame geometry for the next setup process."""

        return serialize_handoff_geometry(self.frameGeometry())


def _current_frozen_executable() -> Path | None:
    """Return the frozen launcher executable path when running from PyInstaller."""

    if bool(getattr(sys, "frozen", False)):
        return Path(sys.executable)
    return None
