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

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import time
from collections.abc import Callable
from typing import TypeVar, cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import LineEdit, RadioButton  # type: ignore[import-untyped]

from substitute.application.onboarding import OnboardingFlowService
from substitute.app.bootstrap.installation_context import (
    build_onboarding_service_bundle,
)
from substitute.app.bootstrap.app_layout import resolve_app_layout
from substitute.app.bootstrap.onboarding_execution import (
    create_onboarding_provisioning_submitter_factory,
)
from substitute.infrastructure.comfy.managed_install import ensure_managed_comfy_setup
from substitute.infrastructure.comfy.attached_install import (
    prepare_attached_comfy_setup,
)
from substitute.infrastructure.comfy.workspace_python_discovery import (
    resolve_attached_comfy_python,
)
from substitute.infrastructure.comfy.managed_process_containment import (
    ManagedProcessHandle,
)
from substitute.infrastructure.comfy.managed_shutdown import kill_managed_comfy
from substitute.presentation.onboarding import OnboardingController, OnboardingWindow
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingFlowServiceLike,
)
from substitute.presentation.widgets.spin_box import SpinBox
from tests.onboarding_automation.external_comfy_fixture import (
    launch_external_comfy_fixture,
    provision_external_comfy_workspace,
    reset_external_comfy_root,
)
from tests.execution_test_helpers import ExecutionRuntimeStub
from tests.onboarding_automation.install_state import reset_install_state
from tests.onboarding_automation.scenarios import (
    ImmediateSuccessFlowService,
    ScenarioDefinition,
    ScenarioExecutionMode,
    ScenarioOutcome,
    build_draft_state,
)
from tests.onboarding_automation.screenshot_capture import capture_widget


_WIDGET_T = TypeVar("_WIDGET_T", bound=QWidget)
_FORCED_MANAGED_FAILURE_STAGE_ENV = "SUGARSUB_FORCE_MANAGED_FAILURE_STAGE"
_BANNED_FAILURE_TERMS = (
    "remediation",
    "invalid repository state",
    "provisioner",
)


@dataclass(frozen=True)
class ScenarioResult:
    """Capture the observable result of one onboarding automation run."""

    scenario: str
    success: bool
    current_page: str
    status_text: str
    detail_text: str
    launch_command: tuple[str, ...]
    screenshot_dir: str

    def to_json(self) -> str:
        """Return the result as stable JSON."""

        return json.dumps(asdict(self), indent=2)


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
        self._app = _ensure_application()
        self._external_process: ManagedProcessHandle | None = None
        self._prepare_fixture_state()
        flow_service = self._build_flow_service()
        self._controller = OnboardingController(
            initial_install_root=scenario.install_root,
            flow_mode=scenario.flow_mode,
            readiness_assessment=scenario.readiness_assessment,
            flow_service=flow_service,
            submitter_factory=create_onboarding_provisioning_submitter_factory(
                ExecutionRuntimeStub()
            ),
        )
        self._window = OnboardingWindow(controller=self._controller)
        self._window.show()
        self._window.raise_()
        self._process_events(150)

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
                self._process_events(50)
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
                if self._scenario.attached_python_executable is not None:
                    self._set_line_edit(
                        "OnboardingAttachedPythonEdit",
                        self._scenario.attached_python_executable,
                    )
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
            self._wait_for_page("OnboardingFolderSetupPage")
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
                self._clear_forced_failure_stage()
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
            self._clear_forced_failure_stage()
            self._window._emit_close_requested_on_close = False
            self._window.close()
            self._process_events(50)
            if self._external_process is not None:
                kill_managed_comfy(self._external_process)

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
        self._process_events(100)

    def _set_line_edit(self, object_name: str, value: Path | str) -> None:
        """Set one named line edit through its real widget instance."""

        widget = self._widget(LineEdit, object_name)
        widget.setText(str(value))
        self._process_events(50)
        if widget.text() != str(value):
            raise AssertionError(
                f"Line edit {object_name} did not keep the expected value."
            )

    def _set_spin_box(self, object_name: str, value: int) -> None:
        """Set one named spin box through its real widget instance."""

        widget = self._widget(SpinBox, object_name)
        widget.setValue(value)
        self._process_events(50)

    def _select_target_mode(self, mode_value: str) -> None:
        """Select one target-mode card through its radio control."""

        radio = self._widget(RadioButton, f"OnboardingTargetCardRadio_{mode_value}")
        QTest.mouseClick(radio, Qt.MouseButton.LeftButton)
        self._process_events(100)

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

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            self._process_events(50)
            if predicate():
                return
        raise TimeoutError(f"Timed out waiting for {description}.")

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

    def _process_events(self, wait_ms: int) -> None:
        """Flush the Qt event queue and optionally wait a short interval."""

        self._app.processEvents()
        QTest.qWait(wait_ms)
        self._app.processEvents()

    def _build_flow_service(self) -> OnboardingFlowServiceLike:
        """Build the real or synthetic flow service required by the scenario."""

        if self._scenario.execution_mode is ScenarioExecutionMode.SYNTHETIC:
            return ImmediateSuccessFlowService(build_draft_state(self._scenario))
        return OnboardingFlowService(
            service_bundle_factory=build_onboarding_service_bundle,
            managed_workspace_provisioner=ensure_managed_comfy_setup,
            entrypoint_path=resolve_scenario_entrypoint(self._scenario.install_root),
            attached_workspace_provisioner=prepare_attached_comfy_setup,
            attached_python_resolver=resolve_attached_comfy_python,
        )

    def _prepare_fixture_state(self) -> None:
        """Reset and provision any filesystem or external-fixture state required."""

        self._clear_forced_failure_stage()
        if self._scenario.reset_install_state:
            reset_install_state(self._scenario.install_root)
        if self._scenario.reset_external_fixture:
            reset_external_comfy_root()
        if self._scenario.provision_external_fixture:
            provision_external_comfy_workspace()
        if self._scenario.launch_external_fixture:
            self._external_process = launch_external_comfy_fixture()
        if self._scenario.prepare_stale_managed_workspace:
            stale_python = (
                self._scenario.managed_workspace_path
                / ".venv"
                / "Scripts"
                / "python.exe"
            )
            stale_python.parent.mkdir(parents=True, exist_ok=True)
            stale_python.write_text("", encoding="utf-8")
        if self._scenario.managed_failure_stage is not None:
            self._set_forced_failure_stage(self._scenario.managed_failure_stage)

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

    def _set_forced_failure_stage(self, stage: str) -> None:
        """Apply one deterministic managed-install failure stage for the scenario."""

        os.environ[_FORCED_MANAGED_FAILURE_STAGE_ENV] = stage

    def _clear_forced_failure_stage(self) -> None:
        """Remove any forced managed-install failure stage from the environment."""

        os.environ.pop(_FORCED_MANAGED_FAILURE_STAGE_ENV, None)


def resolve_scenario_entrypoint(install_root: Path) -> Path:
    """Resolve the real source or installed entrypoint used by one setup scenario."""

    return resolve_app_layout(install_root).entrypoint_path


def _ensure_application() -> QApplication:
    """Return the active QApplication instance for automation runs."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)
