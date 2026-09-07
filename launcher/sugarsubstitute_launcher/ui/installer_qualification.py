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

"""Drive the visible production installer only during release qualification."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Qt, Slot
from PySide6.QtTest import QTest

from sugarsubstitute_shared.installer_qualification import (
    InstallerQualificationPlan,
)
from launcher.sugarsubstitute_launcher.ui.installer_presentation import (
    LauncherUiState,
)

if TYPE_CHECKING:
    from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow


class InstallerQualificationDriver(QObject):
    """Click the production Install control and observe its real handoff."""

    def __init__(
        self,
        *,
        window: LauncherMainWindow,
        plan: InstallerQualificationPlan,
    ) -> None:
        """Bind one qualification plan to its displayed installer window."""

        super().__init__(window)
        self._window = window
        self._plan = plan
        window.handoff_completed.connect(self._record_handoff)
        window.execution.initial_failed.connect(self._record_initial_failure)
        window.execution.setup_failed.connect(self._record_setup_failure)

    def schedule(self) -> None:
        """Queue automation after the installer has entered the Qt event loop."""

        QTimer.singleShot(0, self._accept_language)

    @Slot()
    def _accept_language(self) -> None:
        """Accept the visible manifest-backed language before install choices."""

        try:
            button = self._window.view.primary_button
            selector = self._window.view.language_combo
            if (
                self._window.ui_state is not LauncherUiState.SELECT_LANGUAGE
                or not selector.isVisible()
                or not button.isEnabled()
            ):
                raise RuntimeError("Installer did not open on language selection.")
            self._plan.record(
                "installer.language.ready",
                selected_language=selector.currentData(),
            )
            QTest.mouseClick(
                button,
                Qt.MouseButton.LeftButton,
                pos=button.rect().center(),
            )
            QTimer.singleShot(0, self._click_install)
        except Exception as error:
            self._record_driver_failure(error)

    @Slot()
    def _click_install(self) -> None:
        """Validate and click the same primary control exposed to users."""

        try:
            configured_root = Path(self._window.view.install_path).resolve()
            if configured_root != self._plan.install_root:
                raise RuntimeError(
                    "Installer qualification root differs from the displayed path: "
                    f"{configured_root} != {self._plan.install_root}."
                )
            button = self._window.view.primary_button
            if not self._window.isVisible() or not button.isVisible():
                raise RuntimeError("Production installer controls are not visible.")
            if (
                not button.isEnabled()
                or self._window.ui_state is not LauncherUiState.PREPARE_INSTALL
            ):
                raise RuntimeError(
                    "Production installer did not expose its enabled initial action: "
                    f"state={self._window.ui_state.value!r} "
                    f"enabled={button.isEnabled()}."
                )
            self._plan.record(
                "installer.window.ready",
                title=self._window.windowTitle(),
                primary_action=button.text(),
            )
            QTest.mouseClick(
                button,
                Qt.MouseButton.LeftButton,
                pos=button.rect().center(),
            )
            self._plan.record("installer.install.clicked")
        except Exception as error:
            self._record_driver_failure(error)

    def _record_driver_failure(self, error: Exception) -> None:
        """Record one automation-contract failure and stop qualification."""

        self._plan.record(
            "installer.qualification.failed",
            error_type=type(error).__name__,
            error=str(error),
        )
        QCoreApplication.exit(1)

    @Slot()
    def _record_handoff(self) -> None:
        """Record that the production installer launched installed onboarding."""

        self._plan.record("installer.onboarding.handoff")

    @Slot(str)
    def _record_initial_failure(self, details: str) -> None:
        """Fail qualification when the initial installation phase fails."""

        self._record_installation_failure(phase="initial_install", details=details)

    @Slot(str, str)
    def _record_setup_failure(self, reason: str, details: str) -> None:
        """Fail qualification when runtime setup cannot complete."""

        self._record_installation_failure(
            phase="runtime_setup",
            reason=reason,
            details=details,
        )

    def _record_installation_failure(
        self,
        *,
        phase: str,
        details: str,
        reason: str | None = None,
    ) -> None:
        """Persist actionable failure evidence and stop the qualification process."""

        self._plan.record(
            "installer.qualification.failed",
            phase=phase,
            reason=reason,
            details=details,
        )
        QCoreApplication.exit(1)


def schedule_installer_qualification(window: LauncherMainWindow) -> None:
    """Schedule real installer interaction when CI supplied an explicit plan."""

    plan = InstallerQualificationPlan.from_environment()
    if plan is None:
        return
    InstallerQualificationDriver(window=window, plan=plan).schedule()


__all__ = ["InstallerQualificationDriver", "schedule_installer_qualification"]
