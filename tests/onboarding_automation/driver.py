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

"""Drive the real onboarding window through deterministic automation scenarios."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import TypeVar, cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from qfluentwidgets import LineEdit, RadioButton  # type: ignore[import-untyped]

from substitute.application.onboarding.comfy_environment_service import (
    ComfyEnvironmentService,
)
from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.onboarding_execution import (
    create_onboarding_environment_submitter,
    create_onboarding_provisioning_submitter_factory,
)
from substitute.presentation.onboarding import OnboardingController, OnboardingWindow
from substitute.presentation.onboarding.comfy_environment_coordinator import (
    ComfyEnvironmentCoordinator,
)
from substitute.presentation.widgets.spin_box import SpinBox
from tests.onboarding_automation.environment_fixture import (
    QuiescentProcessGateway,
)
from tests.support.execution.runtime_support import ExecutionRuntimeStub
from tests.onboarding_automation.fixture_owner import OnboardingScenarioFixtureOwner
from tests.onboarding_automation.result import ScenarioResult
from tests.onboarding_automation.scenarios import (
    ScenarioDefinition,
    ScenarioOutcome,
)
from tests.onboarding_automation.screenshot_capture import capture_widget
from tests.support.qt.lifecycle import (
    activate_widget_layouts,
    destroy_qt_object,
    ensure_qt_application,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


_WIDGET_T = TypeVar("_WIDGET_T", bound=QWidget)
_BANNED_FAILURE_TERMS = (
    "remediation",
    "invalid repository state",
    "provisioner",
)


class OnboardingAutomationDriver:
    """Drive one onboarding window instance through a scripted scenario."""

    def __init__(
        self,
        *,
        scenario: ScenarioDefinition,
        screenshot_dir: Path,
    ) -> None:
        """Build the real onboarding window/controller pair for one scenario."""

        self._scenario = scenario
        self._screenshot_dir = screenshot_dir
        ensure_qt_application()
        self._fixture_owner = OnboardingScenarioFixtureOwner(scenario)
        self._fixture_owner.prepare()
        flow_service = self._fixture_owner.build_flow_service()
        execution_runtime = ExecutionRuntimeStub()
        self._controller = OnboardingController(
            initial_install_root=scenario.install_root,
            flow_mode=scenario.flow_mode,
            readiness_assessment=scenario.readiness_assessment,
            flow_service=flow_service,
            submitter_factory=create_onboarding_provisioning_submitter_factory(
                execution_runtime
            ),
        )
        python_gateway = self._fixture_owner.build_python_gateway()
        environment_submitter = create_onboarding_environment_submitter(
            execution_runtime,
            self._controller,
        )
        environment_coordinator = ComfyEnvironmentCoordinator(
            service=ComfyEnvironmentService(
                process_gateway=QuiescentProcessGateway(),
                python_gateway=python_gateway,
            ),
            submitter=environment_submitter,
            close_submitter=environment_submitter.close,
            parent=self._controller,
        )
        self._window = OnboardingWindow(
            controller=self._controller,
            environment_coordinator=environment_coordinator,
        )
        self._window.show()
        self._window.raise_()
        activate_widget_layouts(
            self._window,
            self._window.root_container,
            self._window.page_stack,
        )

    def run(self) -> ScenarioResult:
        """Execute the scripted onboarding interactions and return their result."""

        try:
            self._capture("welcome")
            self._set_line_edit(
                "OnboardingInstallRootEdit", self._scenario.install_root
            )
            self._click("OnboardingPrimaryButton")
            self._wait_for_page("OnboardingTargetModePage")
            self._capture("target_mode")

            self._select_target_mode(self._scenario.target_mode.value)
            self._click("OnboardingPrimaryButton")
            if self._scenario.target_mode.value == "managed_local":
                self._wait_for_page("OnboardingManagedLocalPage")
                self._capture("managed_local")
                if self._scenario.assert_managed_summary:
                    self._assert_managed_summary()
                self._set_line_edit(
                    "OnboardingManagedHostEdit",
                    self._scenario.endpoint_host,
                )
                self._set_spin_box(
                    "OnboardingManagedPortSpinBox",
                    self._scenario.endpoint_port,
                )
                self._set_line_edit(
                    "OnboardingManagedWorkspaceEdit",
                    self._scenario.managed_workspace_path,
                )
                self._window.managed_local_page.runtime_summary_panel.force_cpu_checkbox.setChecked(
                    self._scenario.force_cpu_mode
                )
            elif self._scenario.target_mode.value == "attached_local":
                self._wait_for_page("OnboardingAttachedLocalPage")
                self._capture("attached_local")
                self._set_line_edit(
                    "OnboardingAttachedHostEdit",
                    self._scenario.endpoint_host,
                )
                self._set_spin_box(
                    "OnboardingAttachedPortSpinBox",
                    self._scenario.endpoint_port,
                )
                if self._scenario.attached_workspace_path is not None:
                    self._set_line_edit(
                        "OnboardingAttachedWorkspaceEdit",
                        self._scenario.attached_workspace_path,
                    )
                else:
                    self._set_line_edit("OnboardingAttachedWorkspaceEdit", "")
            else:
                self._wait_for_page("OnboardingRemotePage")
                self._capture("remote")
                self._set_line_edit(
                    "OnboardingRemoteHostEdit",
                    self._scenario.endpoint_host,
                )
                self._set_spin_box(
                    "OnboardingRemotePortSpinBox",
                    self._scenario.endpoint_port,
                )

            self._click("OnboardingPrimaryButton")
            self._wait_until(
                lambda: (
                    self._current_page_name()
                    in {
                        "OnboardingFolderSetupPage",
                        "OnboardingAttachedPythonChoicePage",
                    }
                ),
                timeout_seconds=30.0,
                description="folder setup or attached Python recovery",
            )
            if self._current_page_name() == "OnboardingAttachedPythonChoicePage":
                if self._scenario.expected_outcome is ScenarioOutcome.SUCCESS:
                    raise AssertionError(
                        "Automatic attached Python discovery unexpectedly required recovery."
                    )
                self._capture("attached_python_recovery")
                return ScenarioResult(
                    scenario=self._scenario.name,
                    success=False,
                    current_page=self._current_page_name(),
                    status_text=(
                        self._window.attached_python_choice_page.choice_panel.title_label.text()
                    ),
                    detail_text=(
                        self._window.attached_python_choice_page.choice_panel.description_label.text()
                    ),
                    launch_command=(),
                    screenshot_dir=str(self._screenshot_dir),
                )
            self._capture("folders")
            self._click("OnboardingPrimaryButton")
            self._wait_for_page("OnboardingIntegrationsPage")
            self._capture("integrations")
            self._click("OnboardingPrimaryButton")
            self._wait_for_page("OnboardingProvisioningPage")
            self._capture("provisioning")
            if self._scenario.retry_after_failure:
                self._wait_for_provisioning_button_text("Try again")
                self._assert_user_facing_failure_copy()
                self._capture("failure")
                self._fixture_owner.clear_forced_failure_stage()
                self._click("OnboardingPrimaryButton")
                self._wait_for_provisioning_button_text("Review setup")
            else:
                self._wait_for_terminal_provisioning_state()
            if self._scenario.expected_outcome is ScenarioOutcome.FAILURE:
                self._assert_user_facing_failure_copy()
                self._capture("failure")
                return ScenarioResult(
                    scenario=self._scenario.name,
                    success=False,
                    current_page=self._current_page_name(),
                    status_text=self._window.provisioning_page.status_label.text(),
                    detail_text=self._window.provisioning_page.detail_label.text(),
                    launch_command=(),
                    screenshot_dir=str(self._screenshot_dir),
                )
            self._click("OnboardingPrimaryButton")
            self._wait_for_page("OnboardingCompletionPage")
            self._capture("completion")
            return ScenarioResult(
                scenario=self._scenario.name,
                success=True,
                current_page=self._current_page_name(),
                status_text=self._window.provisioning_page.status_label.text(),
                detail_text=self._window.provisioning_page.detail_label.text(),
                launch_command=self._controller.completion.launch_command
                if self._controller.completion is not None
                else (),
                screenshot_dir=str(self._screenshot_dir),
            )
        finally:
            try:
                self._window._emit_close_requested_on_close = False
                self._window.close()
                self._controller.shutdown()
                destroy_qt_object(self._window)
                destroy_qt_object(self._controller)
            finally:
                self._fixture_owner.close()

    def _current_page_name(self) -> str:
        """Return the object name for the current page widget."""

        current_widget = self._window.page_stack.currentWidget()
        assert current_widget is not None
        return current_widget.objectName()

    def _widget(self, widget_type: type[_WIDGET_T], object_name: str) -> _WIDGET_T:
        """Look up one widget by object name and expected type."""

        widget = self._window.findChild(widget_type, object_name)
        if widget is None:
            raise LookupError(f"Widget not found: {object_name}")
        return cast(_WIDGET_T, widget)

    def _click(self, object_name: str) -> None:
        """Click one named widget and flush the Qt event queue."""

        widget = self._widget(QWidget, object_name)
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)

    def _set_line_edit(self, object_name: str, value: Path | str) -> None:
        """Set one named line edit through its real widget instance."""

        widget = self._widget(LineEdit, object_name)
        widget.setText(str(value))
        if widget.text() != str(value):
            raise AssertionError(
                f"Line edit {object_name} did not keep the expected value."
            )

    def _set_spin_box(self, object_name: str, value: int) -> None:
        """Set one named spin box through its real widget instance."""

        widget = self._widget(SpinBox, object_name)
        widget.setValue(value)

    def _select_target_mode(self, mode_value: str) -> None:
        """Select one target-mode card through its radio control."""

        radio = self._widget(RadioButton, f"OnboardingTargetCardRadio_{mode_value}")
        QTest.mouseClick(radio, Qt.MouseButton.LeftButton)

    def _capture(self, checkpoint_name: str) -> None:
        """Capture the current onboarding window to a deterministic PNG path."""

        capture_widget(
            self._window,
            self._screenshot_dir / f"{checkpoint_name}.png",
        )

    def _wait_for_page(self, expected_object_name: str) -> None:
        """Wait until the current page matches the expected widget object name."""

        self._wait_until(
            lambda: self._current_page_name() == expected_object_name,
            timeout_seconds=5.0,
            description=f"page {expected_object_name}",
        )

    def _wait_for_terminal_provisioning_state(self) -> None:
        """Wait until provisioning reaches a success or failure terminal state."""

        expected_button_text = (
            "Review setup"
            if self._scenario.expected_outcome is ScenarioOutcome.SUCCESS
            else "Try again"
        )
        self._wait_until(
            lambda: self._window.primary_button.text() == expected_button_text,
            timeout_seconds=self._scenario.provisioning_timeout_seconds,
            description=f"provisioning terminal state {expected_button_text}",
        )

    def _wait_for_provisioning_button_text(self, expected_text: str) -> None:
        """Wait until the provisioning page primary button shows one expected label."""

        self._wait_until(
            lambda: self._window.primary_button.text() == expected_text,
            timeout_seconds=self._scenario.provisioning_timeout_seconds,
            description=f"provisioning button text {expected_text}",
        )

    def _wait_until(
        self,
        predicate: Callable[[], bool],
        *,
        timeout_seconds: float,
        description: str,
    ) -> None:
        """Wait until the supplied predicate succeeds or raise on timeout."""

        try:
            wait_for_qt_condition(
                predicate,
                timeout_ms=round(timeout_seconds * 1000),
            )
        except AssertionError as error:
            raise TimeoutError(f"Timed out waiting for {description}.") from error

    def _assert_managed_summary(self) -> None:
        """Assert that the managed-local summary panel shows the selected strategy."""

        panel = self._window.managed_local_page.runtime_summary_panel
        if "windows_nvidia" not in panel.target_label.text():
            raise AssertionError(
                "Managed runtime summary did not show the selected target."
            )
        if "cuda_nightly_cu130" not in panel.backend_label.text():
            raise AssertionError(
                "Managed runtime summary did not show the selected backend."
            )
        if "nightly" not in panel.torch_channel_label.text().lower():
            raise AssertionError(
                "Managed runtime summary did not show the selected torch channel."
            )

    def _assert_user_facing_failure_copy(self) -> None:
        """Fail the scenario when banned developer-facing language reaches the UI."""

        rendered_failure_text = "\n".join(
            (
                self._window.provisioning_page.status_label.text(),
                self._window.provisioning_page.detail_label.text(),
            )
        ).lower()
        for banned_term in _BANNED_FAILURE_TERMS:
            if banned_term in rendered_failure_text:
                raise AssertionError(
                    f"Failure surface exposed banned wording: {banned_term}"
                )


def resolve_scenario_entrypoint(install_root: Path) -> Path:
    """Resolve the real source or installed entrypoint used by one setup scenario."""

    return resolve_app_layout(install_root).entrypoint_path
