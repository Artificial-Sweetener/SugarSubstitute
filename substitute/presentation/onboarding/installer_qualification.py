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

"""Drive installed onboarding as part of one release-qualification chain."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import time
from typing import Literal, TypeAlias, TypeVar, cast

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Qt, Slot
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import LineEdit, RadioButton  # type: ignore[import-untyped]

from substitute.presentation.onboarding.onboarding_window import OnboardingWindow
from substitute.presentation.widgets.spin_box import SpinBox
from sugarsubstitute_shared.installer_qualification import (
    InstallerQualificationPlan,
)


_POLL_INTERVAL_MILLISECONDS = 25
_WIDGET_T = TypeVar("_WIDGET_T")
QualificationPreflightAction: TypeAlias = Literal[
    "continue_welcome",
    "drive_onboarding",
    "wait",
]


def qualification_preflight_action(
    *,
    current_page: str,
    primary_enabled: bool,
    welcome_continued: bool,
) -> QualificationPreflightAction:
    """Select the next bounded action for installed onboarding automation."""

    if (
        current_page == "OnboardingWelcomePage"
        and primary_enabled
        and not welcome_continued
    ):
        return "continue_welcome"
    if current_page == "OnboardingTargetModePage" and primary_enabled:
        return "drive_onboarding"
    return "wait"


class OnboardingQualificationDriver(QObject):
    """Click production onboarding controls through the real launch handoff."""

    def __init__(
        self,
        *,
        window: OnboardingWindow,
        plan: InstallerQualificationPlan,
    ) -> None:
        """Bind the displayed onboarding window and inherited CI plan."""

        super().__init__(window)
        self._window = window
        self._plan = plan
        self._preflight_deadline = time.monotonic() + plan.timeout_seconds
        self._welcome_continued = False

    def schedule(self) -> None:
        """Queue interaction after the window and readiness receipt are visible."""

        QTimer.singleShot(0, self._await_preflight)

    @Slot()
    def _await_preflight(self) -> None:
        """Let the normal event loop finish preflight before driving controls."""

        try:
            primary_button = self._widget(QWidget, "OnboardingPrimaryButton")
            current_page = self._current_page()
            action = qualification_preflight_action(
                current_page=current_page,
                primary_enabled=primary_button.isEnabled(),
                welcome_continued=self._welcome_continued,
            )
            if action == "continue_welcome":
                self._click("OnboardingPrimaryButton")
                self._welcome_continued = True
                self._plan.record("onboarding.welcome.continued")
                QTimer.singleShot(
                    _POLL_INTERVAL_MILLISECONDS,
                    self._await_preflight,
                )
                return
            if action == "drive_onboarding":
                self._run()
                return
            if time.monotonic() >= self._preflight_deadline:
                raise TimeoutError("Timed out waiting for installed Comfy preflight.")
            QTimer.singleShot(_POLL_INTERVAL_MILLISECONDS, self._await_preflight)
        except Exception as error:
            self._record_failure(error)

    def _run(self) -> None:
        """Complete the selected onboarding path and click its production Open action."""

        try:
            self._plan.record(
                "onboarding.page.ready",
                page=self._current_page(),
            )
            install_edit = self._widget(LineEdit, "OnboardingInstallRootEdit")
            if Path(install_edit.text()).resolve() != self._plan.install_root:
                raise RuntimeError(
                    "Installed onboarding did not retain its locked installation root."
                )

            target_radio = self._widget(
                RadioButton,
                f"OnboardingTargetCardRadio_{self._plan.target_mode}",
            )
            self._mouse_click(target_radio)
            if not target_radio.isChecked():
                raise RuntimeError(
                    "The selected Comfy target radio did not accept the production click."
                )
            self._plan.record(
                "onboarding.target.selected",
                mode=self._plan.target_mode,
            )
            self._click("OnboardingPrimaryButton")
            if self._plan.target_mode == "managed_local":
                self._configure_managed_target()
            else:
                self._configure_remote_target()
            self._process_events()
            self._click("OnboardingPrimaryButton")
            if self._plan.target_mode != "remote":
                self._wait_for_page("OnboardingExistingModelsQuestionPage")
                self._click(
                    "OnboardingExistingModelsYes"
                    if self._plan.managed_model_root is not None
                    else "OnboardingExistingModelsNo"
                )
                self._click("OnboardingPrimaryButton")
            if (
                self._plan.target_mode == "remote"
                or self._plan.managed_model_root is not None
            ):
                self._wait_for_page("OnboardingFolderSetupPage")
            if (
                self._plan.target_mode != "remote"
                and self._plan.managed_model_root is not None
            ):
                self._widget(LineEdit, "OnboardingManagedModelRootEdit").setText(
                    str(self._plan.managed_model_root)
                )
                self._process_events()
            if (
                self._plan.target_mode == "remote"
                or self._plan.managed_model_root is not None
            ):
                self._click("OnboardingPrimaryButton")
            if self._plan.target_mode != "remote":
                self._wait_for_page("OnboardingModelRecommendationPage")
                self._click("OnboardingFindOwnModelsButton")
            self._wait_for_page("OnboardingIntegrationsPage")
            self._click("OnboardingPrimaryButton")
            self._wait_for_page("OnboardingProvisioningPage")
            self._wait_until(
                lambda: self._widget(
                    QWidget,
                    "OnboardingPrimaryButton",
                ).isEnabled(),
                "remote provisioning result",
            )
            if self._window._controller.completion is None:
                raise RuntimeError("Remote setup did not reach its review action.")
            self._click("OnboardingPrimaryButton")
            self._wait_for_page("OnboardingCompletionPage")
            if self._window._controller.completion is None:
                raise RuntimeError(
                    "Completion did not retain its ready application handoff."
                )
            self._plan.record("onboarding.completion.ready")
            self._click_terminal_action("OnboardingPrimaryButton")
            self._plan.record("onboarding.open_substitute.clicked")
        except Exception as error:
            self._record_failure(error)

    def _configure_managed_target(self) -> None:
        """Enter the real managed workspace and endpoint selected for qualification."""

        workspace = self._plan.managed_workspace_path
        if workspace is None:
            raise RuntimeError("Managed qualification did not provide a workspace.")
        self._wait_for_page("OnboardingManagedLocalPage")
        self._widget(LineEdit, "OnboardingManagedHostEdit").setText(
            self._plan.endpoint_host
        )
        self._widget(SpinBox, "OnboardingManagedPortSpinBox").setValue(
            self._plan.endpoint_port
        )
        self._widget(LineEdit, "OnboardingManagedWorkspaceEdit").setText(str(workspace))
        self._window.managed_local_page.runtime_summary_panel.force_cpu_checkbox.setChecked(
            self._plan.force_cpu_mode
        )

    def _configure_remote_target(self) -> None:
        """Enter the external endpoint used by legacy qualification plans."""

        self._wait_for_page("OnboardingRemotePage")
        self._widget(LineEdit, "OnboardingRemoteHostEdit").setText(
            self._plan.endpoint_host
        )
        self._widget(SpinBox, "OnboardingRemotePortSpinBox").setValue(
            self._plan.endpoint_port
        )

    def _record_failure(self, error: Exception) -> None:
        """Publish actionable page state and stop the failed qualification."""

        self._plan.record(
            "onboarding.qualification.failed",
            error_type=type(error).__name__,
            error=str(error),
            page=self._current_page(),
        )
        QCoreApplication.exit(1)

    def _widget(self, widget_type: type[_WIDGET_T], object_name: str) -> _WIDGET_T:
        """Return one production widget by its stable automation name."""

        found = self._window.findChild(widget_type, object_name)
        if found is None:
            raise RuntimeError(f"Installed onboarding widget is missing: {object_name}")
        return cast(_WIDGET_T, found)

    def _current_page(self) -> str:
        """Return the active production onboarding page name."""

        current = self._window.page_stack.currentWidget()
        return current.objectName() if current is not None else ""

    def _click(self, object_name: str) -> None:
        """Click one enabled, visible production control."""

        control = self._clickable_control(object_name)
        self._mouse_click(control)

    def _click_terminal_action(self, object_name: str) -> None:
        """Click the final action without entering another nested Qt event wait."""

        control = self._clickable_control(object_name)
        QTest.mouseClick(
            control,
            Qt.MouseButton.LeftButton,
            pos=control.rect().center(),
        )

    def _clickable_control(self, object_name: str) -> QWidget:
        """Return one enabled, visible production control for qualification."""

        control = self._widget(QWidget, object_name)
        if not control.isEnabled() or not control.isVisible():
            raise RuntimeError(
                "Installed onboarding control is not clickable: "
                f"{object_name} enabled={control.isEnabled()} "
                f"visible={control.isVisible()}."
            )
        return control

    def _mouse_click(self, control: QWidget) -> None:
        """Send a real Qt mouse click and service resulting queued work."""

        QTest.mouseClick(
            control,
            Qt.MouseButton.LeftButton,
            pos=control.rect().center(),
        )
        self._process_events(100)

    def _wait_for_page(self, object_name: str) -> None:
        """Wait until the production page stack selects the expected page."""

        self._wait_until(
            lambda: self._current_page() == object_name,
            f"page {object_name}",
        )

    def _wait_until(self, predicate: Callable[[], bool], description: str) -> None:
        """Wait for one observable condition with the plan's bounded timeout."""

        deadline = time.monotonic() + self._plan.timeout_seconds
        while time.monotonic() < deadline:
            self._process_events()
            if predicate():
                return
        raise TimeoutError(f"Timed out waiting for {description}.")

    @staticmethod
    def _process_events(milliseconds: int = _POLL_INTERVAL_MILLISECONDS) -> None:
        """Advance production Qt work during one bounded interaction interval."""

        application = QApplication.instance()
        if application is None:
            raise RuntimeError("Installed onboarding has no QApplication.")
        application.processEvents()
        QTest.qWait(milliseconds)
        application.processEvents()


def schedule_onboarding_qualification(window: OnboardingWindow) -> None:
    """Schedule onboarding interaction when CI supplied an explicit plan."""

    plan = InstallerQualificationPlan.from_environment()
    if plan is None:
        return
    OnboardingQualificationDriver(window=window, plan=plan).schedule()


__all__ = [
    "OnboardingQualificationDriver",
    "qualification_preflight_action",
    "schedule_onboarding_qualification",
]
