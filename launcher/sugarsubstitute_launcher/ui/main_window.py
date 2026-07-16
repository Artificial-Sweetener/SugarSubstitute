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

"""Render the standalone installer window using SugarSubstitute chrome."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable, Sequence
import ctypes
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, cast

from PySide6.QtCore import QObject, QRect, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    IconWidget,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    Theme,
    setTheme,
    setThemeColor,
)
from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
    isDarkTheme,
    themeColor,
)
from qframelesswindow import AcrylicWindow  # type: ignore[import-untyped]
from qframelesswindow.titlebar import TitleBar  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.first_run import FirstRunInstaller
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.installer import LayoutInstaller
from launcher.sugarsubstitute_launcher.process import start_detached_handoff
from launcher.sugarsubstitute_launcher.release_discovery import (
    discover_local_release_root,
)
from launcher.sugarsubstitute_launcher.release_sources import (
    LocalFolderReleaseSource,
    default_production_release_source,
)
from launcher.sugarsubstitute_launcher.resources import launcher_icon, launcher_uv_path
from launcher.sugarsubstitute_launcher.platforms import (
    LauncherOperatingSystem,
    detect_launcher_target,
)
from launcher.sugarsubstitute_launcher.runtime import (
    SubprocessRuntimeCommandRunner,
    UvManagedRuntimeInstaller,
)
from sugarsubstitute_shared.presentation.terminal import TerminalOutputView


_LOGGER = logging.getLogger(__name__)
_ACCENT_COLOR = "#E91E63"
_WINDOW_WIDTH = 1260
_WINDOW_HEIGHT = 800
_TITLEBAR_HEIGHT = 34
_STEP_TITLES = (
    "Choose a folder",
    "Pick a setup",
    "Confirm the details",
    "Finish setup",
)

if sys.platform == "win32":
    import win32con  # type: ignore[import-untyped]
    import win32gui  # type: ignore[import-untyped]

    _DWMAPI: Any | None = ctypes.WinDLL("dwmapi")
    _WINDOW_CORNER_ATTRIBUTE = 33
    _WINDOW_CORNER_ROUND = 2
    _WINDOWS_BUILD = int(sys.getwindowsversion().build)
else:
    win32con = None
    win32gui = None
    _DWMAPI = None
    _WINDOW_CORNER_ATTRIBUTE = 0
    _WINDOW_CORNER_ROUND = 0
    _WINDOWS_BUILD = 0


class LauncherUiState(Enum):
    """Identify the user action currently owned by the primary button."""

    PREPARE_INSTALL = "prepare_install"
    INSTALL_APP = "install_app"
    INSTALL_RUNTIME = "install_runtime"
    START_SETUP = "start_setup"
    COMPLETE = "complete"


class LauncherRuntimeInstaller(Protocol):
    """Provision the runtime required to start the installed source app."""

    def provision(self, *, layout: InstallLayout) -> object:
        """Ensure the runtime exists for the supplied install layout."""

        ...


RuntimeInstallerFactory = Callable[[Callable[[str], None]], LauncherRuntimeInstaller]


class _SetupWorker(QObject):
    """Run runtime provisioning and app handoff away from the UI thread."""

    log = Signal(str)
    failed = Signal(str, str)
    succeeded = Signal()
    finished = Signal()

    def __init__(
        self,
        *,
        layout: InstallLayout,
        setup_command: Sequence[str],
        runtime_installer_factory: RuntimeInstallerFactory,
        process_starter: Callable[[Sequence[str]], None],
    ) -> None:
        """Store setup work that must not block the Qt event loop."""

        super().__init__()
        self._layout = layout
        self._setup_command = list(setup_command)
        self._runtime_installer_factory = runtime_installer_factory
        self._process_starter = process_starter

    @Slot()
    def run(self) -> None:
        """Provision the runtime, launch setup, and report progress through signals."""

        try:
            runtime_installer = self._runtime_installer_factory(self.log.emit)
            runtime_installer.provision(layout=self._layout)
        except Exception as error:
            self.failed.emit("runtime", str(error))
            self.finished.emit()
            return

        self.log.emit(f"Runtime ready: {self._layout.runtime_python}")
        self.log.emit("Starting SugarSubstitute setup.")
        try:
            self._process_starter(self._setup_command)
        except Exception as error:
            self.failed.emit("setup", str(error))
            self.finished.emit()
            return

        self.log.emit("Started SugarSubstitute setup.")
        self.log.emit("Waiting for the setup window to open.")
        self.succeeded.emit()
        self.finished.emit()


class _InitialInstallWorker(QObject):
    """Install launcher and app payload without blocking the setup window."""

    log = Signal(str)
    failed = Signal(str)
    succeeded = Signal(object, object, str)
    finished = Signal()

    def __init__(
        self,
        *,
        install_root: Path,
        frozen_setup: bool,
        handoff_geometry: str | None,
        layout_installer: LayoutInstaller,
        first_run_installer: FirstRunInstaller,
    ) -> None:
        """Store initial install work that runs away from the Qt event loop."""

        super().__init__()
        self._install_root = install_root
        self._frozen_setup = frozen_setup
        self._handoff_geometry = handoff_geometry
        self._layout_installer = layout_installer
        self._first_run_installer = first_run_installer

    @Slot()
    def run(self) -> None:
        """Install permanent launcher files and the app payload."""

        try:
            release_source = (
                default_production_release_source()
                if self._frozen_setup
                else LocalFolderReleaseSource(discover_local_release_root())
            )
            if self._frozen_setup:
                downloaded_result = (
                    self._first_run_installer.install_downloaded_launcher(
                        install_root=self._install_root,
                        release_source=release_source,
                        handoff_geometry=self._handoff_geometry,
                        launch_installed=False,
                    )
                )
                layout = downloaded_result.layout
                self.log.emit(f"Installed launcher: {layout.executable_path}")
            else:
                prepared_result = self._layout_installer.prepare(self._install_root)
                layout = prepared_result.layout
                self.log.emit(
                    "Source-run launcher detected; skipped executable self-copy."
                )

            self.log.emit(f"Created install root: {layout.root}")
            self.log.emit(f"Wrote launcher config: {layout.config_path}")
            continued_result = self._first_run_installer.continue_install(
                layout=layout,
                release_source=release_source,
            )
        except Exception as error:
            self.failed.emit(str(error))
            self.finished.emit()
            return

        self.succeeded.emit(
            layout,
            continued_result.app_command,
            continued_result.app_version,
        )
        self.finished.emit()


class LauncherStepItem(QFrame):
    """Render one compact installer/onboarding progress step."""

    def __init__(
        self,
        *,
        index: int,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        """Build the numbered progress row used by the installer rail."""

        super().__init__(parent)
        self.setObjectName("OnboardingStepItem")
        self.setProperty("stepState", "inactive")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        self.index_label = BodyLabel(str(index), self)
        self.index_label.setObjectName("OnboardingStepNumber")
        layout.addWidget(self.index_label, alignment=Qt.AlignmentFlag.AlignTop)

        self.title_label = CaptionLabel(title, self)
        self.title_label.setObjectName("OnboardingStepTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label, 1)

    def set_state(self, *, active: bool, complete: bool) -> None:
        """Apply active, complete, or inactive presentation state."""

        if active:
            state = "active"
        elif complete:
            state = "complete"
        else:
            state = "inactive"
        self.setProperty("stepState", state)
        self.index_label.setProperty("stepState", state)
        self.title_label.setProperty("stepState", state)
        for widget in (self, self.index_label, self.title_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class LauncherMainWindow(AcrylicWindow):  # type: ignore[misc]
    """Let the user choose an install directory and install the app payload."""

    def __init__(
        self,
        *,
        initial_layout: InstallLayout,
        continue_install: bool,
        repair: bool,
        update_check_enabled: bool,
        handoff_geometry: str | None = None,
        process_starter: Callable[[Sequence[str]], None] = start_detached_handoff,
        runtime_installer: LauncherRuntimeInstaller | None = None,
    ) -> None:
        """Build the launcher UI and initialize installer state."""

        super().__init__()
        setTheme(Theme.DARK)
        setThemeColor(QColor(_ACCENT_COLOR))
        self._layout_installer = LayoutInstaller()
        self._first_run_installer = FirstRunInstaller()
        self._continue_install = continue_install
        self._repair = repair
        self._update_check_enabled = update_check_enabled
        self._handoff_geometry = handoff_geometry
        self._process_starter = process_starter
        self._runtime_installer_factory = self._build_runtime_installer_factory(
            runtime_installer
        )
        self._setup_thread: QThread | None = None
        self._setup_worker: _SetupWorker | None = None
        self._install_thread: QThread | None = None
        self._install_worker: _InitialInstallWorker | None = None
        self._setup_command: list[str] | None = None
        self._prepared_layout: InstallLayout | None = (
            initial_layout if continue_install else None
        )
        self._ui_state = (
            LauncherUiState.INSTALL_APP
            if continue_install
            else LauncherUiState.PREPARE_INSTALL
        )
        self._path_edit = LineEdit(self)
        self._path_edit.setText(str(initial_layout.root))
        self._progress_log = TerminalOutputView(
            self,
            min_height=260,
            max_height=340,
        )
        self._status_panel: QFrame | None = None
        self._browse_button: PushButton | None = None
        self._primary_button = PrimaryPushButton(self)
        self._build_ui()
        self._apply_handoff_geometry()
        self._apply_backdrop()
        QTimer.singleShot(0, self._apply_backdrop)
        if self._continue_install:
            QTimer.singleShot(0, self._install_app_payload)

    def _build_ui(self) -> None:
        """Compose the frameless launcher window widgets and connect actions."""

        self.setWindowTitle("SugarSubstitute Setup")
        self.setWindowIcon(launcher_icon())
        self.resize(_WINDOW_WIDTH, _WINDOW_HEIGHT)
        self.setFixedSize(_WINDOW_WIDTH, _WINDOW_HEIGHT)

        title_bar = TitleBar(self)
        title_bar.setFixedHeight(_TITLEBAR_HEIGHT)
        self.setTitleBar(title_bar)
        self.titleBar.maxBtn.hide()
        self.titleBar.minBtn.hide()

        root = QWidget(self)
        root.setObjectName("OnboardingRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        surface = QWidget(root)
        surface.setObjectName("OnboardingSurface")
        surface_layout = QHBoxLayout(surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)

        identity_rail = QFrame(surface)
        identity_rail.setObjectName("OnboardingIdentityRail")
        identity_rail.setFixedWidth(280)
        rail_layout = QVBoxLayout(identity_rail)
        rail_layout.setContentsMargins(24, 24, 18, 18)
        rail_layout.setSpacing(14)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(12)

        icon_badge = QFrame(identity_rail)
        icon_badge.setObjectName("OnboardingIconBadge")
        icon_badge_layout = QVBoxLayout(icon_badge)
        icon_badge_layout.setContentsMargins(10, 10, 10, 10)
        icon_badge_layout.setSpacing(0)
        icon_label = QLabel(icon_badge)
        icon_label.setPixmap(launcher_icon().pixmap(26, 26))
        icon_label.setFixedSize(26, 26)
        icon_badge_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(icon_badge, alignment=Qt.AlignmentFlag.AlignTop)

        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(4)

        title = BodyLabel("Setup", identity_rail)
        title.setObjectName("OnboardingRailTitle")
        title.setWordWrap(True)
        brand_text.addWidget(title)

        subtitle = CaptionLabel(
            "Choose a folder and connect Substitute to ComfyUI.",
            identity_rail,
        )
        subtitle.setObjectName("OnboardingRailSummary")
        subtitle.setWordWrap(True)
        brand_text.addWidget(subtitle)
        brand_row.addLayout(brand_text, 1)
        rail_layout.addLayout(brand_row)

        self.progress_count_label = CaptionLabel("Step 1 of 4", identity_rail)
        self.progress_count_label.setObjectName("OnboardingProgressCount")
        rail_layout.addWidget(self.progress_count_label)

        self.progress_title_label = BodyLabel("Choose a folder", identity_rail)
        self.progress_title_label.setObjectName("OnboardingProgressTitle")
        self.progress_title_label.setWordWrap(True)
        rail_layout.addWidget(self.progress_title_label)

        self.progress_helper_label = CaptionLabel(
            "You can change the ComfyUI connection later.",
            identity_rail,
        )
        self.progress_helper_label.setObjectName("OnboardingProgressHelper")
        self.progress_helper_label.setWordWrap(True)
        rail_layout.addWidget(self.progress_helper_label)

        self.step_items: list[LauncherStepItem] = []
        for index, step_title in enumerate(_STEP_TITLES, start=1):
            step_item = LauncherStepItem(
                index=index,
                title=step_title,
                parent=identity_rail,
            )
            step_item.set_state(active=index == 1, complete=False)
            rail_layout.addWidget(step_item)
            self.step_items.append(step_item)
        rail_layout.addStretch(1)

        content_panel = QFrame(surface)
        content_panel.setObjectName("OnboardingContentPanel")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(24, 24, 24, 18)
        content_layout.setSpacing(14)

        page_stage = QWidget(content_panel)
        page_stage.setObjectName("OnboardingPageStage")
        page_stage_layout = QVBoxLayout(page_stage)
        page_stage_layout.setContentsMargins(0, 0, 0, 0)
        page_stage_layout.setSpacing(0)
        page_stage_layout.addStretch(1)

        page_stack = QStackedWidget(content_panel)
        page_stack.setObjectName("OnboardingPageStack")
        page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        install_root_page = QFrame(content_panel)
        install_root_page.setObjectName("OnboardingPageFrame")
        page_outer_layout = QHBoxLayout(install_root_page)
        page_outer_layout.setContentsMargins(0, 0, 0, 0)
        page_outer_layout.setSpacing(0)
        page_outer_layout.addStretch(1)

        content_column = QWidget(install_root_page)
        content_column.setObjectName("OnboardingContentColumn")
        content_column.setMinimumWidth(820)
        content_column.setMaximumWidth(980)
        column_layout = QVBoxLayout(content_column)
        column_layout.setContentsMargins(4, 6, 4, 8)
        column_layout.setSpacing(18)

        hero_panel = QFrame(content_column)
        hero_panel.setObjectName("OnboardingHeroPanel")
        hero_layout = QHBoxLayout(hero_panel)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(14)

        hero_badge = QFrame(hero_panel)
        hero_badge.setObjectName("OnboardingHeroBadge")
        hero_badge_layout = QVBoxLayout(hero_badge)
        hero_badge_layout.setContentsMargins(10, 10, 10, 10)
        hero_badge_layout.setSpacing(0)
        folder_icon = IconWidget(FIF.FOLDER, hero_badge)
        folder_icon.setFixedSize(22, 22)
        hero_badge_layout.addWidget(folder_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(hero_badge, alignment=Qt.AlignmentFlag.AlignTop)

        hero_text = QVBoxLayout()
        hero_text.setContentsMargins(0, 0, 0, 0)
        hero_text.setSpacing(5)
        eyebrow = CaptionLabel("Start here", hero_panel)
        eyebrow.setObjectName("OnboardingHeroEyebrow")
        hero_text.addWidget(eyebrow)
        page_title = BodyLabel(
            "Choose where Substitute should keep its setup",
            hero_panel,
        )
        page_title.setObjectName("OnboardingPageTitle")
        page_title.setWordWrap(True)
        hero_text.addWidget(page_title)
        page_description = CaptionLabel(
            "Pick the main folder for Substitute's files. If you let Substitute install ComfyUI for you, it will place that there too by default.",
            hero_panel,
        )
        page_description.setObjectName("OnboardingPageDescription")
        page_description.setWordWrap(True)
        hero_text.addWidget(page_description)
        hero_layout.addLayout(hero_text, 1)
        column_layout.addWidget(hero_panel)

        location_panel = QFrame(content_column)
        location_panel.setObjectName("OnboardingSectionPanel")
        panel_layout = QVBoxLayout(location_panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)

        path_block = QFrame(location_panel)
        path_block.setObjectName("OnboardingFieldBlock")
        path_block_layout = QVBoxLayout(path_block)
        path_block_layout.setContentsMargins(0, 0, 0, 0)
        path_block_layout.setSpacing(7)
        path_label = CaptionLabel("Folder", path_block)
        path_label.setObjectName("OnboardingFieldLabel")
        path_block_layout.addWidget(path_label)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(10)
        self._path_edit.setMinimumHeight(36)
        self._browse_button = PushButton("Browse...", path_block)
        self._browse_button.clicked.connect(self._choose_install_directory)
        path_row.addWidget(self._path_edit, 1)
        path_row.addWidget(self._browse_button)
        path_block_layout.addLayout(path_row)

        helper_label = CaptionLabel(
            "Substitute will place the desktop launcher, source app payload, local runtime, settings, and user data under this folder.",
            path_block,
        )
        helper_label.setObjectName("OnboardingFieldHelper")
        helper_label.setWordWrap(True)
        path_block_layout.addWidget(helper_label)

        self._install_location_guidance_label = CaptionLabel(
            _install_location_guidance(),
            path_block,
        )
        self._install_location_guidance_label.setObjectName("OnboardingFieldHelper")
        self._install_location_guidance_label.setWordWrap(True)
        path_block_layout.addWidget(self._install_location_guidance_label)
        panel_layout.addWidget(path_block)
        column_layout.addWidget(location_panel)

        status_panel = QFrame(content_column)
        status_panel.setObjectName("OnboardingStatusPanel")
        self._status_panel = status_panel
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(10)
        status_title = BodyLabel("Live Output", status_panel)
        status_title.setObjectName("OnboardingOutputTitle")
        status_layout.addWidget(status_title)
        status_layout.addWidget(self._progress_log)
        column_layout.addWidget(status_panel)
        status_panel.hide()
        column_layout.addStretch(1)
        page_outer_layout.addWidget(content_column, 1)
        page_outer_layout.addStretch(1)
        page_stack.addWidget(install_root_page)
        page_stack.setCurrentWidget(install_root_page)

        page_stage_layout.addWidget(
            page_stack,
            0,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )
        page_stage_layout.addStretch(1)
        content_layout.addWidget(page_stage, 1)

        footer_row = QFrame(content_panel)
        footer_row.setObjectName("OnboardingFooterRow")
        footer_layout = QHBoxLayout(footer_row)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(10)
        footer_layout.addStretch(1)
        self._primary_button.setObjectName("LauncherPrimaryButton")
        self._primary_button.clicked.connect(self._handle_primary_clicked)
        self._primary_button.setMinimumWidth(164)
        footer_layout.addWidget(self._primary_button, 0, Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(footer_row)

        surface_layout.addWidget(identity_rail, 0)
        surface_layout.addWidget(content_panel, 1)
        surface_layout.setStretch(0, 0)
        surface_layout.setStretch(1, 1)
        root_layout.addWidget(surface)

        self._apply_styles()
        body_layout = QVBoxLayout(self)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(root)
        self.titleBar.raise_()
        self._refresh_primary_button()
        self._append_log("Ready.")
        if self._continue_install:
            self._append_log("Continuing install from installed launcher.")
        if self._repair:
            self._append_log("Repair mode requested.")
        if not self._update_check_enabled:
            self._append_log("Update check disabled for this launch.")

    def _choose_install_directory(self) -> None:
        """Prompt the user for a writable install directory."""

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Choose SugarSubstitute install directory",
            self._path_edit.text(),
        )
        if selected_dir:
            self._path_edit.setText(selected_dir)

    def _handle_primary_clicked(self) -> None:
        """Dispatch the primary button according to the current setup state."""

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

    def _prepare_install_layout(self) -> None:
        """Create base install directories and copy the launcher when frozen."""

        self._show_status_output()
        install_root = Path(self._path_edit.text()).expanduser()
        try:
            current_executable = _current_frozen_executable()
            if current_executable is None:
                prepared_result = self._layout_installer.prepare(install_root)
                prepared_layout = prepared_result.layout
                self._append_log(
                    "Source-run launcher detected; skipped executable self-copy."
                )
            else:
                downloaded_result = (
                    self._first_run_installer.install_downloaded_launcher(
                        install_root=install_root,
                        release_source=default_production_release_source(),
                        handoff_geometry=self._current_handoff_geometry(),
                        launch_installed=True,
                    )
                )
                prepared_layout = downloaded_result.layout
                self._append_log(
                    f"Installed launcher: {prepared_layout.executable_path}"
                )
                self._append_log("Starting installed launcher.")
                self._append_log("Setup will continue from the install directory.")
                self._ui_state = LauncherUiState.COMPLETE
                self._refresh_primary_button()
                QTimer.singleShot(250, self.close)
                return
            self._prepared_layout = prepared_layout
        except OSError as error:
            self._report_install_failure(error)
            return
        except ValueError as error:
            self._report_install_failure(error)
            return
        except Exception as error:
            self._report_install_failure(error)
            return

        self._append_log(f"Created install root: {self._prepared_layout.root}")
        self._append_log(f"Wrote launcher config: {self._prepared_layout.config_path}")
        self._ui_state = LauncherUiState.INSTALL_APP
        self._refresh_primary_button()

    def _start_initial_install_worker(self) -> None:
        """Install launcher and app payload in the current setup window."""

        self._show_status_output()
        if self._install_thread is not None:
            return

        install_root = Path(self._path_edit.text()).expanduser()
        self._primary_button.setEnabled(False)
        self._primary_button.setText("Working...")
        self._set_install_path_controls_enabled(False)
        self._append_log("Preparing SugarSubstitute install.")

        thread = QThread(self)
        worker = _InitialInstallWorker(
            install_root=install_root,
            frozen_setup=_current_frozen_executable() is not None,
            handoff_geometry=self._current_handoff_geometry(),
            layout_installer=self._layout_installer,
            first_run_installer=self._first_run_installer,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.failed.connect(self._handle_initial_install_failed)
        worker.succeeded.connect(self._handle_initial_install_succeeded)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._forget_initial_install_worker)
        self._install_thread = thread
        self._install_worker = worker
        thread.start()

    def _install_app_payload(self) -> None:
        """Install the app source payload for source-run development setup."""

        self._show_status_output()
        if self._prepared_layout is None:
            self._append_log("Install root is not prepared yet.")
            self._ui_state = LauncherUiState.PREPARE_INSTALL
            self._refresh_primary_button()
            return
        try:
            release_root = discover_local_release_root()
            result = self._first_run_installer.continue_install(
                layout=self._prepared_layout,
                release_source=LocalFolderReleaseSource(release_root),
            )
        except Exception as error:
            self._report_install_failure(error)
            return

        self._append_log(f"Installed app payload version: {result.app_version}")
        self._append_log(f"App entrypoint: {self._prepared_layout.app_entrypoint}")
        self._setup_command = self._with_handoff_geometry(result.app_command)
        self._ui_state = LauncherUiState.INSTALL_RUNTIME
        self._refresh_primary_button()
        self._start_setup_worker()

    def _start_setup_worker(self) -> None:
        """Start runtime provisioning and onboarding handoff in a worker thread."""

        self._show_status_output()
        if self._prepared_layout is None:
            self._append_log("Install root is not prepared yet.")
            self._ui_state = LauncherUiState.PREPARE_INSTALL
            self._refresh_primary_button()
            return

        if self._setup_command is None:
            self._append_log("Setup command is not available yet.")
            self._ui_state = LauncherUiState.INSTALL_APP
            self._refresh_primary_button()
            return

        if self._setup_thread is not None:
            return

        self._primary_button.setEnabled(False)
        self._primary_button.setText("Working...")
        self._append_log("Installing Python runtime and app dependencies.")
        self._append_log("This can take a while the first time.")

        thread = QThread(self)
        worker = _SetupWorker(
            layout=self._prepared_layout,
            setup_command=self._setup_command,
            runtime_installer_factory=self._runtime_installer_factory,
            process_starter=self._process_starter,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.failed.connect(self._handle_setup_worker_failed)
        worker.succeeded.connect(self._handle_setup_worker_succeeded)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._forget_setup_worker)
        self._setup_thread = thread
        self._setup_worker = worker
        thread.start()

    def _start_setup_handoff(self) -> None:
        """Start the installed app so it can enter onboarding/setup routing."""

        self._show_status_output()
        if self._setup_command is None:
            self._append_log("Setup command is not available yet.")
            self._ui_state = LauncherUiState.INSTALL_APP
            self._refresh_primary_button()
            return

        self._append_log("Starting SugarSubstitute setup.")
        try:
            self._process_starter(self._setup_command)
        except Exception as error:
            self._append_log("Could not start SugarSubstitute setup.")
            self._append_log(f"Details: {error}")
            self._ui_state = LauncherUiState.START_SETUP
            self._refresh_primary_button()
            return

        self._append_log("Started SugarSubstitute setup.")
        self._ui_state = LauncherUiState.COMPLETE
        self._refresh_primary_button()
        self._append_log("Waiting for the setup window to open.")
        self._close_after_successful_handoff()

    @Slot(str)
    def _handle_initial_install_failed(self, details: str) -> None:
        """Render initial install failure and restore the install action."""

        self._append_log("Setup failed. Check the details below and try again.")
        self._append_log(f"Details: {details}")
        self._ui_state = LauncherUiState.PREPARE_INSTALL
        self._refresh_primary_button()

    @Slot(object, object, str)
    def _handle_initial_install_succeeded(
        self,
        layout: object,
        app_command: object,
        app_version: str,
    ) -> None:
        """Continue setup after the launcher and app payload are installed."""

        if not isinstance(layout, InstallLayout):
            self._handle_initial_install_failed("Installer returned an invalid layout.")
            return
        if not isinstance(app_command, list) or not all(
            isinstance(part, str) for part in app_command
        ):
            self._handle_initial_install_failed(
                "Installer returned an invalid app command."
            )
            return

        self._prepared_layout = layout
        self._append_log(f"Installed app payload version: {app_version}")
        self._append_log(f"App entrypoint: {layout.app_entrypoint}")
        self._setup_command = self._with_handoff_geometry(app_command)
        self._ui_state = LauncherUiState.INSTALL_RUNTIME
        self._refresh_primary_button()
        self._start_setup_worker()

    @Slot(str, str)
    def _handle_setup_worker_failed(self, phase: str, details: str) -> None:
        """Render worker failure and restore the matching retry action."""

        if phase == "runtime":
            self._append_log("Could not install the Python runtime.")
            self._ui_state = LauncherUiState.INSTALL_RUNTIME
        else:
            self._append_log("Could not start SugarSubstitute setup.")
            self._ui_state = LauncherUiState.START_SETUP
        self._append_log(f"Details: {details}")
        self._refresh_primary_button()

    @Slot()
    def _handle_setup_worker_succeeded(self) -> None:
        """Mark setup handoff complete after the background worker succeeds."""

        self._ui_state = LauncherUiState.COMPLETE
        self._refresh_primary_button()
        self._close_after_successful_handoff()

    def _close_after_successful_handoff(self) -> None:
        """Close the installer after the installed app process has started."""

        QTimer.singleShot(0, self.close)

    @Slot()
    def _forget_setup_worker(self) -> None:
        """Forget the completed setup worker and thread."""

        self._setup_thread = None
        self._setup_worker = None

    @Slot()
    def _forget_initial_install_worker(self) -> None:
        """Forget the completed initial install worker and thread."""

        self._install_thread = None
        self._install_worker = None
        if self._ui_state is LauncherUiState.PREPARE_INSTALL:
            self._refresh_primary_button()

    def _refresh_primary_button(self) -> None:
        """Apply the primary button label and enabled state for the setup phase."""

        path_controls_enabled = (
            self._ui_state is LauncherUiState.PREPARE_INSTALL
            and self._install_thread is None
        )
        self._set_install_path_controls_enabled(path_controls_enabled)

        if self._ui_state is LauncherUiState.PREPARE_INSTALL:
            self._primary_button.setText("Install")
            self._primary_button.setEnabled(True)
            return
        if self._ui_state is LauncherUiState.INSTALL_APP:
            self._primary_button.setText("Continue")
            self._primary_button.setEnabled(True)
            return
        if self._ui_state is LauncherUiState.INSTALL_RUNTIME:
            self._primary_button.setText("Install runtime")
            self._primary_button.setEnabled(True)
            return
        if self._ui_state is LauncherUiState.START_SETUP:
            self._primary_button.setText("Open setup")
            self._primary_button.setEnabled(True)
            return
        self._primary_button.setText("Setup started")
        self._primary_button.setEnabled(False)

    def _set_install_path_controls_enabled(self, enabled: bool) -> None:
        """Enable or lock the install path controls as one editable group."""

        self._path_edit.setEnabled(enabled)
        if self._browse_button is not None:
            self._browse_button.setEnabled(enabled)

    def _report_install_failure(self, error: Exception) -> None:
        """Log one setup failure and show an actionable progress message."""

        _LOGGER.exception("Launcher setup failed.")
        self._append_log("Setup failed. Check the details below and try again.")
        self._append_log(f"Details: {error}")

    @Slot(str)
    def _append_log(self, message: str) -> None:
        """Append one user-visible progress line."""

        self._progress_log.append_line(f"{message}\n")

    def _show_status_output(self) -> None:
        """Reveal installer output once setup work has actually started."""

        if self._status_panel is not None:
            self._status_panel.show()

    def _apply_handoff_geometry(self) -> None:
        """Move the launcher onto the previous handoff window frame."""

        geometry = _parse_handoff_geometry(self._handoff_geometry)
        if geometry is not None:
            self.setGeometry(geometry)

    def _current_handoff_geometry(self) -> str:
        """Return this window's frame geometry for the next setup process."""

        geometry = self.frameGeometry()
        return f"{geometry.x()},{geometry.y()},{geometry.width()},{geometry.height()}"

    def _with_handoff_geometry(self, command: Sequence[str]) -> list[str]:
        """Append current window geometry to the installed app launch command."""

        return [*command, f"--handoff-geometry={self._current_handoff_geometry()}"]

    def _build_runtime_installer_factory(
        self,
        runtime_installer: LauncherRuntimeInstaller | None,
    ) -> RuntimeInstallerFactory:
        """Return the runtime installer factory used by setup workers."""

        if runtime_installer is not None:
            return lambda _output_callback: runtime_installer
        return self._create_runtime_installer

    def _create_runtime_installer(
        self,
        output_callback: Callable[[str], None],
    ) -> LauncherRuntimeInstaller:
        """Build the default uv-backed runtime installer."""

        return UvManagedRuntimeInstaller(
            bundled_uv_path=launcher_uv_path(),
            runner=SubprocessRuntimeCommandRunner(output_callback),
        )

    def _apply_styles(self) -> None:
        """Apply launcher shell styling while leaving qfluent controls in charge."""

        accent = themeColor()
        accent_rgb = f"{accent.red()}, {accent.green()}, {accent.blue()}"
        text_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
        wash_rgb = "255, 255, 255" if isDarkTheme() else "0, 0, 0"
        icon_color = QColor("#ffffff") if isDarkTheme() else QColor("#000000")
        hover_bg = QColor(45, 45, 45) if isDarkTheme() else QColor(0, 0, 0, 24)
        pressed_bg = QColor(30, 30, 30) if isDarkTheme() else QColor(0, 0, 0, 36)
        for button in (
            self.titleBar.minBtn,
            self.titleBar.maxBtn,
            self.titleBar.closeBtn,
        ):
            button.setNormalColor(icon_color)
            button.setHoverColor(icon_color)
            button.setPressedColor(icon_color)
            button.setHoverBackgroundColor(hover_bg)
            button.setPressedBackgroundColor(pressed_bg)
        self.titleBar.setStyleSheet("background-color: transparent; border: none;")
        self.setStyleSheet(
            """
            QWidget#OnboardingRoot,
            QWidget#OnboardingSurface,
            QFrame#OnboardingContentPanel {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingIdentityRail {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingIconBadge,
            QFrame#OnboardingHeroBadge {
                background-color: rgba(__ACCENT_RGB__, 0.12);
                border: 1px solid rgba(__ACCENT_RGB__, 0.24);
                border-radius: 14px;
            }
            QFrame#OnboardingStepItem {
                background-color: transparent;
                border: none;
                border-radius: 14px;
            }
            QFrame#OnboardingStepItem[stepState="active"] {
                background-color: rgba(__WASH_RGB__, 0.045);
                border: 1px solid rgba(__WASH_RGB__, 0.075);
            }
            QFrame#OnboardingStepItem[stepState="complete"] {
                background-color: transparent;
                border: none;
            }
            QWidget#OnboardingPageStage,
            QWidget#OnboardingContentColumn,
            QFrame#OnboardingPageFrame,
            QFrame#OnboardingHeroPanel,
            QFrame#OnboardingFieldBlock,
            QFrame#OnboardingFooterRow {
                background-color: transparent;
                border: none;
            }
            QFrame#OnboardingSectionPanel {
                background-color: rgba(__WASH_RGB__, 0.04);
                border: 1px solid rgba(__WASH_RGB__, 0.075);
                border-radius: 22px;
            }
            QFrame#OnboardingStatusPanel {
                background-color: rgba(__WASH_RGB__, 0.035);
                border: 1px solid rgba(__WASH_RGB__, 0.065);
                border-radius: 18px;
            }
            BodyLabel#OnboardingRailTitle {
                font-size: 24px;
                font-weight: 600;
            }
            CaptionLabel#OnboardingRailSummary,
            CaptionLabel#OnboardingProgressHelper,
            CaptionLabel#OnboardingPageDescription,
            CaptionLabel#OnboardingFieldHelper {
                color: rgba(__TEXT_RGB__, 0.74);
            }
            CaptionLabel#OnboardingHeroEyebrow,
            CaptionLabel#OnboardingFieldLabel,
            CaptionLabel#OnboardingProgressCount {
                color: rgba(__ACCENT_RGB__, 0.9);
                font-weight: 600;
                text-transform: uppercase;
            }
            BodyLabel#OnboardingPageTitle,
            BodyLabel#OnboardingProgressTitle {
                font-size: 22px;
                font-weight: 600;
            }
            BodyLabel#OnboardingStepNumber {
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                border-radius: 12px;
                qproperty-alignment: 'AlignCenter';
                background-color: rgba(__WASH_RGB__, 0.06);
                color: rgba(__TEXT_RGB__, 0.68);
                font-size: 12px;
                font-weight: 700;
            }
            BodyLabel#OnboardingStepNumber[stepState="active"] {
                background-color: rgba(__ACCENT_RGB__, 0.32);
                color: rgba(__TEXT_RGB__, 1.0);
            }
            BodyLabel#OnboardingStepNumber[stepState="complete"] {
                background-color: rgba(__ACCENT_RGB__, 0.18);
                color: rgba(__TEXT_RGB__, 0.92);
            }
            CaptionLabel#OnboardingStepTitle {
                color: rgba(__TEXT_RGB__, 0.62);
            }
            CaptionLabel#OnboardingStepTitle[stepState="active"] {
                color: rgba(__TEXT_RGB__, 0.98);
                font-weight: 600;
            }
            CaptionLabel#OnboardingStepTitle[stepState="complete"] {
                color: rgba(__TEXT_RGB__, 0.78);
            }
            BodyLabel#OnboardingOutputTitle {
                color: rgba(__TEXT_RGB__, 0.9);
                font-size: 16px;
                font-weight: 600;
            }
            CaptionLabel#OnboardingFieldLabel {
                font-size: 12px;
            }
            """.replace("__ACCENT_RGB__", accent_rgb)
            .replace("__TEXT_RGB__", text_rgb)
            .replace("__WASH_RGB__", wash_rgb)
        )

    def _apply_backdrop(self) -> None:
        """Apply the same Mica-style backdrop used by onboarding."""

        try:
            self.windowEffect.setMicaEffect(
                self.winId(),
                isDarkMode=isDarkTheme(),
                isAlt=False,
            )
            _normalize_acrylic_frameless_chrome(self)
        except (AttributeError, RuntimeError, OSError) as error:
            _LOGGER.warning("Failed to apply launcher backdrop: %r", error)


def _current_frozen_executable() -> Path | None:
    """Return the frozen launcher executable path when running from PyInstaller."""

    if bool(getattr(sys, "frozen", False)):
        return Path(sys.executable)
    return None


def _install_location_guidance() -> str:
    """Return writable-location guidance for the current launcher target."""

    if detect_launcher_target().operating_system is LauncherOperatingSystem.MACOS:
        return (
            "Use a writable folder in your home directory, such as "
            "~/Applications/SugarSubstitute. System Applications folders can require "
            "administrator access for updates and runtime setup."
        )
    return (
        "Use a normal writable folder such as %USERPROFILE%\\SugarSubstitute. Avoid Program "
        "Files because Windows can block app updates, runtime setup, and local "
        "ComfyUI files there."
    )


def _parse_handoff_geometry(raw_value: str | None) -> QRect | None:
    """Parse an `x,y,width,height` handoff geometry string."""

    if not raw_value:
        return None
    parts = raw_value.split(",")
    if len(parts) != 4:
        return None
    try:
        x, y, width, height = (int(part) for part in parts)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return QRect(x, y, width, height)


def _restore_rounded_window_corners(window_id: object) -> None:
    """Request Windows 11 rounded corners for the launcher window."""

    if sys.platform != "win32" or _DWMAPI is None or _WINDOWS_BUILD < 22000:
        return

    try:
        hwnd = int(cast(Any, window_id))
        corner_preference = ctypes.c_int(_WINDOW_CORNER_ROUND)
        _DWMAPI.DwmSetWindowAttribute(
            hwnd,
            _WINDOW_CORNER_ATTRIBUTE,
            ctypes.byref(corner_preference),
            4,
        )
    except Exception as error:
        _LOGGER.debug("Failed to restore launcher rounded corners: %r", error)


def _normalize_acrylic_frameless_chrome(window: Any) -> None:
    """Remove Qt 6.10 native caption remnants while preserving resizing."""

    if sys.platform != "win32" or win32con is None or win32gui is None:
        return

    try:
        window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        hwnd = int(cast(Any, window.winId()))
        style = int(win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE))
        updated_style = style | int(win32con.WS_THICKFRAME)
        updated_style |= int(win32con.WS_MINIMIZEBOX)
        updated_style |= int(win32con.WS_MAXIMIZEBOX)
        updated_style &= ~int(win32con.WS_CAPTION)

        if updated_style != style:
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, updated_style)
        win32gui.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOZORDER
            | win32con.SWP_FRAMECHANGED,
        )
        _restore_rounded_window_corners(hwnd)
    except Exception as error:
        _LOGGER.debug("Failed to normalize launcher frameless chrome: %r", error)
