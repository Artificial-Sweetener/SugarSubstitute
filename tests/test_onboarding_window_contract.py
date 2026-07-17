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

"""Tests for the dedicated onboarding window contract."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, QEvent, QRect, Signal, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    LineEdit,
    PrimaryPushButton,
    RadioButton,
    SegmentedWidget,
    Theme,
    setTheme,
)

from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyPythonBinding,
    ComfyPythonCandidate,
    ComfyPythonDiscoveryResult,
    ComfyPythonProbeResult,
    ComfyPythonSelectionSource,
    InstallationContext,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    LocalComfyProcess,
    ReadinessAssessment,
    ReadinessIssue,
    ReadinessIssueCode,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.application.onboarding import OnboardingProvisioningFailure
from substitute.application.onboarding.comfy_environment_service import (
    AttachedPythonRecoverySnapshot,
    AttachedPythonRecoveryState,
    ComfyPreflightSnapshot,
)
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
    ReadinessIssuePresentation,
)
from substitute.presentation.onboarding.comfy_environment_coordinator import (
    ComfyEnvironmentCoordinator,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingCompletion,
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_window import OnboardingWindow
from substitute.presentation.shell.window_frame import (
    ShellBackdropMode,
    SubstituteWindowFrame,
)
from substitute.presentation.widgets.spin_box import SpinBox

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "onboarding window Qt contract tests require non-xdist execution",
        allow_module_level=True,
    )


class _FakeController(QObject):
    """Provide the minimum onboarding controller surface consumed by the window."""

    draft_changed = Signal(object)
    provisioning_started = Signal()
    provisioning_finished = Signal()
    progress_status_changed = Signal(str)
    progress_log_emitted = Signal(str)
    failure_reported = Signal(object)
    completion_ready = Signal(object)

    def __init__(self, draft: OnboardingDraft, flow_mode: OnboardingFlowMode) -> None:
        """Store fixed onboarding state for the window contract tests."""

        super().__init__()
        self._draft = draft
        self._flow_mode = flow_mode
        self._readiness_assessment = ReadinessAssessment(
            route=BootstrapRoute.REPAIR,
            issues=(
                ReadinessIssue(
                    code=ReadinessIssueCode.RUNTIME_PYTHON_MISSING,
                    summary="Runtime Python executable is missing.",
                    detail="Repair the visible runtime before normal launch.",
                ),
            ),
        )
        self.provisioning_calls = 0
        self.last_civitai_api_key = ""

    @property
    def draft(self) -> OnboardingDraft:
        """Return the current onboarding draft."""

        return self._draft

    @property
    def flow_mode(self) -> OnboardingFlowMode:
        """Return the active onboarding mode."""

        return self._flow_mode

    @property
    def readiness_assessment(self) -> ReadinessAssessment:
        """Return the repair-mode readiness assessment."""

        return self._readiness_assessment

    def present_readiness_issues(self) -> tuple[ReadinessIssuePresentation, ...]:
        """Return user-facing repair copy for the fake readiness issue."""

        return (
            ReadinessIssuePresentation(
                headline="Substitute's local setup is incomplete",
                user_message="A required local Python file is missing.",
                technical_detail="Missing runtime Python executable.",
            ),
        )

    def next_page(self, current_page: OnboardingPageId) -> OnboardingPageId:
        """Return the next page in a minimal deterministic sequence."""

        if current_page is OnboardingPageId.WELCOME:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.COMFY_PREFLIGHT:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.TARGET_MODE:
            return OnboardingPageId.MANAGED_LOCAL
        if current_page is OnboardingPageId.MANAGED_LOCAL:
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.FOLDERS:
            return OnboardingPageId.INTEGRATIONS
        if current_page is OnboardingPageId.INTEGRATIONS:
            return OnboardingPageId.PROVISIONING
        return current_page

    def previous_page(self, current_page: OnboardingPageId) -> OnboardingPageId:
        """Return the previous page in the minimal deterministic sequence."""

        if current_page is OnboardingPageId.TARGET_MODE:
            return OnboardingPageId.WELCOME
        if current_page is OnboardingPageId.COMFY_PREFLIGHT:
            return OnboardingPageId.WELCOME
        if current_page is OnboardingPageId.MANAGED_LOCAL:
            return OnboardingPageId.TARGET_MODE
        if current_page is OnboardingPageId.FOLDERS:
            return OnboardingPageId.MANAGED_LOCAL
        if current_page is OnboardingPageId.INTEGRATIONS:
            return OnboardingPageId.FOLDERS
        if current_page is OnboardingPageId.PROVISIONING:
            return OnboardingPageId.INTEGRATIONS
        return current_page

    def set_installation_root(self, installation_root: Path) -> None:
        """Update the fake draft installation root."""

        self._draft = replace(self._draft, installation_root=installation_root)

    def update_target_mode(self, target_mode: OnboardingTargetMode) -> None:
        """Update the fake target mode."""

        self._draft = replace(self._draft, target_mode=target_mode)

    def update_endpoint(self, host: str, port: int) -> None:
        """Accept endpoint updates without side effects."""

        _ = host, port

    def update_managed_workspace(self, workspace_path: Path) -> None:
        """Accept managed workspace updates without side effects."""

        _ = workspace_path

    def update_attached_workspace(self, workspace_path: Path | None) -> None:
        """Accept attached workspace updates without side effects."""

        self._draft = replace(
            self._draft,
            attached_workspace_path=workspace_path,
            attached_python_binding=None,
        )

    def update_attached_python_binding(
        self,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Store a verified attached Python binding."""

        self._draft = replace(self._draft, attached_python_binding=binding)

    def update_managed_runtime_preferences(
        self,
        *,
        force_cpu_mode: bool,
        prefer_edge_torch: bool,
        prefer_edge_comfy_channel: bool,
    ) -> None:
        """Accept managed runtime preference updates without side effects."""

        _ = force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel

    def update_folder_preferences(
        self,
        *,
        managed_model_root: Path | None,
        managed_model_root_uses_default: bool,
        output_root: Path | None,
        output_root_uses_default: bool,
    ) -> None:
        """Update fake folder preferences."""

        self._draft = OnboardingDraft(
            installation_root=self._draft.installation_root,
            target_mode=self._draft.target_mode,
            endpoint_host=self._draft.endpoint_host,
            endpoint_port=self._draft.endpoint_port,
            managed_workspace_path=self._draft.managed_workspace_path,
            attached_workspace_path=self._draft.attached_workspace_path,
            managed_model_root=managed_model_root,
            managed_model_root_uses_default=managed_model_root_uses_default,
            output_root=output_root,
            output_root_uses_default=output_root_uses_default,
        )

    def update_integration_preferences(
        self,
        *,
        danbooru_tag_help_enabled: bool,
        danbooru_safe_previews_enabled: bool,
        danbooru_image_rating_policy: str,
        civitai_model_help_enabled: bool,
        civitai_downloads_enabled: bool,
        civitai_safe_thumbnails_enabled: bool,
        civitai_thumbnail_safety_policy: str,
        civitai_api_key: str = "",
    ) -> None:
        """Update fake integration preferences."""

        self.last_civitai_api_key = civitai_api_key
        self._draft = OnboardingDraft(
            installation_root=self._draft.installation_root,
            target_mode=self._draft.target_mode,
            endpoint_host=self._draft.endpoint_host,
            endpoint_port=self._draft.endpoint_port,
            managed_workspace_path=self._draft.managed_workspace_path,
            attached_workspace_path=self._draft.attached_workspace_path,
            danbooru_tag_help_enabled=danbooru_tag_help_enabled,
            danbooru_safe_previews_enabled=danbooru_safe_previews_enabled,
            danbooru_image_rating_policy=danbooru_image_rating_policy,
            civitai_model_help_enabled=civitai_model_help_enabled,
            civitai_downloads_enabled=civitai_downloads_enabled,
            civitai_safe_thumbnails_enabled=civitai_safe_thumbnails_enabled,
            civitai_thumbnail_safety_policy=civitai_thumbnail_safety_policy,
        )

    def start_provisioning(self) -> None:
        """Emit immediate successful completion for the window contract."""

        self.provisioning_calls += 1
        self.provisioning_started.emit()
        installation = InstallationConfiguration.create_default(
            self._draft.installation_root
        )
        runtime = RuntimeConfiguration(
            runtime_root=installation.runtime_dir,
            python_executable=installation.runtime_dir
            / ".venv"
            / "Scripts"
            / "python.exe",
            bootstrap_status=RuntimeBootstrapStatus.READY,
        )
        target = ComfyTargetConfiguration(
            mode=ComfyTargetMode(self._draft.target_mode.value),
            endpoint=ComfyEndpoint(
                host=self._draft.endpoint_host,
                port=self._draft.endpoint_port,
            ),
            workspace_path=self._draft.managed_workspace_path,
            install_owned=self._draft.target_mode is OnboardingTargetMode.MANAGED_LOCAL,
            launch_owned=self._draft.target_mode is OnboardingTargetMode.MANAGED_LOCAL,
        )
        self.completion_ready.emit(
            OnboardingCompletion(
                context=InstallationContext(
                    installation=installation,
                    runtime=runtime,
                    comfy_target=target,
                ),
                restart_required=self._flow_mode is OnboardingFlowMode.RECONFIGURE,
                launch_command=("python", "main.py"),
            )
        )
        self.provisioning_finished.emit()


class _ResettingDraftController(_FakeController):
    """Mirror the real controller's draft-changed side effects for field-order tests."""

    def update_endpoint(self, host: str, port: int) -> None:
        """Emit a real draft update so the window can accidentally reset other fields."""

        self._draft = OnboardingDraft(
            installation_root=self._draft.installation_root,
            target_mode=self._draft.target_mode,
            endpoint_host=host.strip(),
            endpoint_port=port,
            managed_workspace_path=self._draft.managed_workspace_path,
            attached_workspace_path=self._draft.attached_workspace_path,
        )
        self.draft_changed.emit(self._draft)

    def update_attached_workspace(self, workspace_path: Path | None) -> None:
        """Store the attached workspace like the real controller does."""

        self._draft = replace(
            self._draft,
            attached_workspace_path=workspace_path,
            attached_python_binding=None,
        )
        self.draft_changed.emit(self._draft)

    def update_attached_python_binding(
        self,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Store verified attached Python evidence like the real controller."""

        self._draft = replace(
            self._draft,
            attached_python_binding=binding,
        )
        self.draft_changed.emit(self._draft)


class _FakeEnvironmentCoordinator(QObject):
    """Expose controllable live environment signals to window contract tests."""

    preflight_changed = Signal(object)
    discovery_finished = Signal(object)
    recovery_changed = Signal(object)
    browse_finished = Signal(object)
    termination_finished = Signal(object)
    task_failed = Signal(str)

    def __init__(self) -> None:
        """Record environment actions requested by the window."""

        super().__init__()
        self.preflight_starts = 0
        self.discoveries: list[Path] = []
        self.recoveries: list[tuple[Path, ComfyPythonBinding | None]] = []
        self.validations: list[tuple[Path, Path]] = []
        self.stops = 0
        self.shutdown_calls = 0

    def start_preflight(self) -> None:
        """Record one live preflight request."""

        self.preflight_starts += 1

    def discover_attached_python(self, workspace: Path) -> None:
        """Record one silent attached-Python discovery request."""

        self.discoveries.append(workspace)

    def start_attached_recovery(
        self,
        *,
        workspace: Path,
        binding: ComfyPythonBinding | None,
    ) -> None:
        """Record one live launch-monitor request."""

        self.recoveries.append((workspace, binding))

    def validate_browsed_python(self, *, workspace: Path, executable: Path) -> None:
        """Record one explicit manual Python validation request."""

        self.validations.append((workspace, executable))

    def close_observed_processes(self) -> None:
        """Accept an explicit close request for signal-routing tests."""

    def stop_monitoring(self) -> None:
        """Record one page-owned monitor stop."""

        self.stops += 1

    def shutdown(self) -> None:
        """Record coordinator shutdown with the window."""

        self.shutdown_calls += 1


def _app() -> QApplication:
    """Return the active QApplication instance for widget contract tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_onboarding_window_uses_handoff_geometry(tmp_path: Path) -> None:
    """Installer handoff geometry should place onboarding on the same frame."""

    _app()
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )

    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        ),
        initial_geometry=(20, 30, 1260, 800),
    )

    assert window.geometry().x() == 20
    assert window.geometry().y() == 30
    assert window.width() == 1260
    assert window.height() == 800
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_builds_all_required_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Window should materialize every dedicated onboarding page."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.REPAIR),
        )
    )
    frame_layout = window.layout()
    assert frame_layout is not None
    root_layout = window.root_container.layout()
    assert root_layout is not None

    assert isinstance(window, SubstituteWindowFrame)
    assert window._backdrop_mode is ShellBackdropMode.MICA
    assert window.bodyMaterialSurface is None
    assert window.menuContainer is None
    assert frame_layout.contentsMargins().top() == 0
    assert root_layout.contentsMargins().top() == 0
    assert window.minimumWidth() == window.maximumWidth()
    assert window.minimumHeight() == window.maximumHeight()
    assert window.titleBar.minBtn.isHidden() is True
    assert window.titleBar.maxBtn.isHidden() is True
    assert window.titleBar.closeBtn.isHidden() is False
    assert not window.windowIcon().isNull()
    assert isinstance(window.app_icon, QLabel)
    assert window.app_icon.pixmap() is not None
    assert not window.app_icon.pixmap().isNull()
    close_hit = window.titleBar.closeBtn.mapTo(
        window, window.titleBar.closeBtn.rect().center()
    )
    assert window.childAt(close_hit) is window.titleBar.closeBtn
    assert window.page_stack.count() == 13
    assert window.page_stack.parentWidget() is window.page_stage
    assert (
        window.attached_python_choice_page.objectName()
        == "OnboardingAttachedPythonChoicePage"
    )
    assert (
        window.attached_python_process_page.objectName()
        == "OnboardingAttachedPythonProcessPage"
    )
    assert (
        window.attached_python_manual_page.objectName()
        == "OnboardingAttachedPythonManualPage"
    )
    assert window.folder_setup_page.objectName() == "OnboardingFolderSetupPage"
    assert window.integrations_page.objectName() == "OnboardingIntegrationsPage"


def test_onboarding_pages_fit_fixed_window_layout_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every setup page should remain inside the fixed window and above its footer."""

    app = _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="a-long-but-valid-comfy-hostname.example.internal",
        endpoint_port=65535,
        managed_workspace_path=tmp_path / "managed-comfy-workspace-with-a-long-name",
        attached_workspace_path=tmp_path / "existing-comfy-workspace",
        detected_platform="windows",
        detected_accelerator="nvidia",
        selected_install_target="windows_nvidia",
        selected_python_version="3.13",
        selected_comfy_channel="latest",
        selected_backend_policy="cuda_cu130",
        selected_torch_channel="stable",
        selected_torch_reason=(
            "NVIDIA installs use Comfy's recommended stable CUDA runtime path for "
            "this detected hardware configuration."
        ),
        selected_stability="stable",
        civitai_api_key_configured=True,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )
    window.show()
    app.processEvents()

    try:
        page_height_budget = window.page_stage.contentsRect().height()
        for page_id, page in window._pages.items():
            window._show_page(page_id)
            app.processEvents()

            assert page.sizeHint().height() <= page_height_budget, (
                f"{page_id.value} requests {page.sizeHint().height()}px from a "
                f"{page_height_budget}px page stage"
            )
            assert window.page_stage.contentsRect().contains(
                window.page_stack.geometry()
            ), f"{page_id.value} page stack leaves the fixed page stage"
            assert window.page_stack.contentsRect().contains(page.geometry()), (
                f"{page_id.value} page leaves its stack"
            )

            stack_rect = QRect(
                window.page_stack.mapTo(window.content_panel, QPoint(0, 0)),
                window.page_stack.size(),
            )
            assert stack_rect.bottom() < window.footer_row.geometry().top(), (
                f"{page_id.value} overlaps the fixed footer"
            )
    finally:
        window._emit_close_requested_on_close = False
        window.close()
        window.deleteLater()
        app.processEvents()


def test_onboarding_window_renders_folder_and_integration_controls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Folder and integration pages should expose the expected first-run controls."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
        civitai_api_key_configured=True,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    assert window.folder_setup_page.managed_model_section.isHidden() is False
    assert window.folder_setup_page.managed_model_root_edit.text() == str(
        tmp_path / "comfyui" / "models"
    )
    assert window.folder_setup_page.output_root_edit.text() == str(
        tmp_path / "user" / "outputs"
    )
    assert (
        window.integrations_page.civitai_api_key_edit.echoMode()
        is QLineEdit.EchoMode.Password
    )
    assert window.integrations_page.civitai_api_key_status.text() == (
        "API key already saved"
    )
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_hides_saved_setup_issues_during_first_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """First-run onboarding should not show repair copy before setup exists."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    assert window.issue_banner.isHidden() is True
    assert "saved setup items need repair" not in window.issue_banner.text()
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_hides_managed_model_folder_for_remote(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Remote setup should hide the local ComfyUI models folder field."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.REMOTE,
        endpoint_host="10.0.0.5",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    assert window.folder_setup_page.managed_model_section.isHidden() is True
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_shows_model_folder_for_attached_local(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached-local setup should choose a model root for its ComfyUI workspace."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    attached_workspace = tmp_path / "ExistingComfyUI"
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.ATTACHED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=attached_workspace,
        managed_model_root=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    assert window.folder_setup_page.managed_model_section.isHidden() is False
    assert window.folder_setup_page.managed_model_root_edit.text() == str(
        attached_workspace / "models"
    )
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_stylesheet_refreshes_after_qfluent_theme_switch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Onboarding custom styles should refresh from QFluent theme changes."""

    app = _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    setTheme(Theme.DARK)
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.REPAIR),
        )
    )
    try:
        dark_style = window.styleSheet()

        setTheme(Theme.LIGHT)
        app.processEvents()

        assert window.styleSheet() != dark_style
        assert "rgba(0, 0, 0, 0.74)" in window.styleSheet()
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
    assert isinstance(window.install_root_page.install_root_edit, LineEdit)
    assert hasattr(window, "step_items") is True
    assert len(window.step_items) == 4
    assert window.flow_title_label.text() == "Repair"
    assert window.progress_count_label.text() == "Step 1 of 4"
    assert window.progress_title_label.text() == "Choose a folder"
    assert window.identity_rail.styleSheet() == ""
    assert len(window.target_mode_page.mode_cards) == 3
    assert window.target_mode_page.findChildren(SegmentedWidget) == []
    assert (
        window.target_mode_page.mode_cards[
            OnboardingTargetMode.MANAGED_LOCAL
        ].selection_radio.text()
        == "Selected"
    )
    assert (
        window.target_mode_page.mode_cards[
            OnboardingTargetMode.ATTACHED_LOCAL
        ].selection_radio.text()
        == "Select"
    )
    assert isinstance(
        window.target_mode_page.mode_cards[
            OnboardingTargetMode.MANAGED_LOCAL
        ].selection_radio,
        RadioButton,
    )
    assert (
        window.target_mode_page.mode_cards[
            OnboardingTargetMode.MANAGED_LOCAL
        ].selection_radio.isChecked()
        is True
    )
    assert isinstance(window.managed_local_page.port_spinbox, SpinBox)
    assert isinstance(window.primary_button, PrimaryPushButton)
    assert hasattr(window, "cancel_button") is False
    assert isinstance(window.provisioning_page.details_surface.log_view, QPlainTextEdit)
    assert (
        window.provisioning_page.hero_panel.title_label.text() == "Finishing your setup"
    )
    assert window.provisioning_page.details_surface.log_view.toPlainText() == ""
    assert (
        window.provisioning_page.details_surface.log_view.horizontalScrollBarPolicy()
        is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert hasattr(window.provisioning_page, "progress_bar") is False
    assert window.provisioning_page.details_surface.log_view.maximumHeight() == 390
    assert window.provisioning_page.details_surface.log_view.minimumHeight() == 320
    assert (
        window.integrations_page.danbooru_image_policy_combo.currentData()
        == "safe_only"
    )
    assert (
        window.integrations_page.civitai_thumbnail_policy_combo.currentData()
        == "sfw_only"
    )
    assert not hasattr(window.integrations_page, "danbooru_safe_previews_checkbox")
    assert not hasattr(window.integrations_page, "civitai_safe_thumbnails_checkbox")
    assert window.issue_banner.isHidden() is False
    assert "Runtime Python executable is missing." not in window.issue_banner.text()
    assert "required local Python file is missing" in window.issue_banner.text()
    assert "Missing runtime Python executable." in window.issue_banner.text()
    assert "can't open yet" not in window.issue_banner.text()
    assert (
        "Choose where Substitute should keep its setup"
        == window.install_root_page.hero_panel.title_label.text()
    )
    assert (
        "visible config, state, runtime"
        not in window.install_root_page.hero_panel.description_label.text()
    )
    assert (
        "Choose how Substitute should reach ComfyUI"
        == window.target_mode_page.hero_panel.title_label.text()
    )
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_starts_drag_from_passive_surface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Passive Mica-backed onboarding surfaces should initiate system drag."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    class _FakeHandle:
        def __init__(self) -> None:
            self.started = False

        def startSystemMove(self) -> None:
            self.started = True

    fake_handle = _FakeHandle()
    monkeypatch.setattr(window, "windowHandle", lambda: fake_handle)
    monkeypatch.setattr(window, "childAt", lambda _: window.identity_rail)
    mouse_press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(4.0, 4.0),
        QPointF(4.0, 4.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    handled = window.eventFilter(window.identity_rail, mouse_press)

    assert handled is True
    assert fake_handle.started is True
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_does_not_start_drag_from_content_widgets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Content widgets should not drag even if the event arrives on a drag surface."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    class _FakeHandle:
        def __init__(self) -> None:
            self.started = False

        def startSystemMove(self) -> None:
            self.started = True

    fake_handle = _FakeHandle()
    monkeypatch.setattr(window, "windowHandle", lambda: fake_handle)
    monkeypatch.setattr(window, "childAt", lambda _: window.flow_title_label)
    label_center = window.flow_title_label.rect().center()
    label_point = window.flow_title_label.mapTo(window.identity_rail, label_center)
    mouse_press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(float(label_point.x()), float(label_point.y())),
        QPointF(float(label_point.x()), float(label_point.y())),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    handled = window.eventFilter(window.identity_rail, mouse_press)

    assert handled is False
    assert fake_handle.started is False
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_shows_completion_page_after_provisioning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioning completion should enable the completion review step."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.RECONFIGURE),
        )
    )

    window._show_page(OnboardingPageId.PROVISIONING)

    assert window.primary_button.text() == "Review setup"
    assert window.completion_page.command_surface.isHidden() is False
    assert "python main.py" == window.completion_page.command_label.text()
    assert window.completion_page.hero_panel.title_label.text() == "Substitute is ready"
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_uses_specific_action_labels(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Window should use page-specific action labels instead of generic wizard copy."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    window._show_page(OnboardingPageId.TARGET_MODE)
    assert window.primary_button.text() == "Continue"
    window._show_page(OnboardingPageId.MANAGED_LOCAL)
    assert window.primary_button.text() == "Save and continue"
    window._show_page(OnboardingPageId.FOLDERS)
    assert window.primary_button.text() == "Save and continue"
    window._show_page(OnboardingPageId.INTEGRATIONS)
    assert window.primary_button.text() == "Finish setup"
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_renders_actionable_provisioning_failure_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioning failures should show guidance and preserve technical detail."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    controller = cast(
        OnboardingController,
        _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
    )
    window = OnboardingWindow(controller=controller)

    failure = OnboardingProvisioningFailure(
        headline="The ComfyUI folder needs to be cleared before setup can continue",
        user_message="Substitute found leftover files in the selected ComfyUI folder.",
        technical_detail="invalid ComfyUI repository",
        remediation_steps=(
            f"Delete the incomplete folder at {tmp_path / 'comfyui'}.",
            "Then run setup again.",
        ),
    )

    window._handle_failure(failure)

    assert (
        window.provisioning_page.status_label.text()
        == "The ComfyUI folder needs to be cleared before setup can continue"
    )
    assert "leftover files" in window.provisioning_page.detail_label.text()
    assert (
        "Delete the incomplete folder" in window.provisioning_page.detail_label.text()
    )
    assert (
        "invalid ComfyUI repository"
        in window.provisioning_page.details_surface.log_view.toPlainText()
    )
    assert (
        "REMEDIATION:"
        not in window.provisioning_page.details_surface.log_view.toPlainText()
    )
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_retry_button_restarts_provisioning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioning retry should actually restart work after a failure."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    fake_controller = _FakeController(draft, OnboardingFlowMode.FIRST_RUN)
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            fake_controller,
        )
    )
    monkeypatch.setattr(
        fake_controller,
        "start_provisioning",
        lambda: setattr(
            fake_controller,
            "provisioning_calls",
            fake_controller.provisioning_calls + 1,
        ),
    )

    failure = OnboardingProvisioningFailure(
        headline="Setup needs attention",
        user_message="Fix the reported issue and try again.",
        technical_detail="boom",
        remediation_steps=("Try again after fixing the folder.",),
    )
    window._handle_failure(failure)
    window._current_page = OnboardingPageId.PROVISIONING
    window.primary_button.setEnabled(True)
    fake_controller.provisioning_calls = 0

    window.primary_button.click()

    assert fake_controller.provisioning_calls == 1
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_reenables_back_after_provisioning_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed provisioning step should let the user return to the editable form."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )
    window._current_page = OnboardingPageId.PROVISIONING

    failure = OnboardingProvisioningFailure(
        headline="Setup needs attention",
        user_message="Fix the reported issue and try again.",
        technical_detail="boom",
        remediation_steps=("Try again after fixing the folder.",),
    )

    window._handle_failure(failure)
    window._handle_provisioning_finished()
    window.back_button.click()

    assert window.back_button.isEnabled() is True
    assert window._current_page is OnboardingPageId.INTEGRATIONS
    assert window.managed_local_page.workspace_edit.text() == str(tmp_path / "comfyui")
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_reads_attached_workspace_before_draft_reset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached-local save should capture the edited workspace before draft_changed resets the form."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.ATTACHED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=tmp_path / "comfyui",
    )
    controller = _ResettingDraftController(draft, OnboardingFlowMode.FIRST_RUN)
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            controller,
        )
    )
    monkeypatch.setattr(window, "_show_page", lambda _page_id: None)
    window._current_page = OnboardingPageId.ATTACHED_LOCAL
    expected_workspace = Path(r"E:\ComfyUIExternalTest")

    window.attached_local_page.host_edit.setText("127.0.0.1")
    window.attached_local_page.port_spinbox.setValue(8190)
    window.attached_local_page.workspace_edit.setText(str(expected_workspace))
    window._advance()

    assert controller.draft.endpoint_port == 8190
    assert controller.draft.attached_workspace_path == expected_workspace.resolve()
    assert controller.draft.attached_python_binding is None
    assert not hasattr(window.attached_local_page, "python_edit")
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_clean_preflight_skips_the_warning_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A passing safety check should advance without exposing its warning page."""

    app = _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    coordinator = _FakeEnvironmentCoordinator()
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        ),
        environment_coordinator=cast(ComfyEnvironmentCoordinator, coordinator),
    )
    window.show()
    app.processEvents()

    window._advance()
    assert window._current_page is OnboardingPageId.WELCOME
    assert coordinator.preflight_starts == 1
    assert not window.primary_button.isEnabled()

    coordinator.preflight_changed.emit(ComfyPreflightSnapshot(()))
    app.processEvents()
    assert window.page_stack.currentWidget() is window.target_mode_page
    assert window.comfy_preflight_page.isVisible() is False
    assert window.primary_button.isEnabled()

    window._emit_close_requested_on_close = False
    window.close()


def test_locked_install_root_checks_in_place_without_showing_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Launcher-owned folder setup should check quietly on its first visible page."""

    app = _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    coordinator = _FakeEnvironmentCoordinator()
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        ),
        environment_coordinator=cast(ComfyEnvironmentCoordinator, coordinator),
        install_root_locked=True,
    )
    window.show()
    app.processEvents()

    assert window._current_page is OnboardingPageId.TARGET_MODE
    assert coordinator.preflight_starts == 1
    assert not window.primary_button.isEnabled()
    coordinator.preflight_changed.emit(ComfyPreflightSnapshot(()))
    app.processEvents()
    assert window._current_page is OnboardingPageId.TARGET_MODE
    assert window.comfy_preflight_page.isVisible() is False
    assert window.primary_button.isEnabled()

    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_running_preflight_updates_live_until_comfy_stops(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A detected process should reveal the warning until ComfyUI exits."""

    app = _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    controller = _FakeController(draft, OnboardingFlowMode.FIRST_RUN)
    coordinator = _FakeEnvironmentCoordinator()
    window = OnboardingWindow(
        controller=cast(OnboardingController, controller),
        environment_coordinator=cast(ComfyEnvironmentCoordinator, coordinator),
    )
    window.show()
    app.processEvents()

    window._advance()
    app.processEvents()
    assert window._current_page is OnboardingPageId.WELCOME
    assert coordinator.preflight_starts == 1
    assert not window.primary_button.isEnabled()

    process = LocalComfyProcess(
        pid=123,
        create_time=1.0,
        python_executable=tmp_path / "python.exe",
        workspace=tmp_path / "ComfyUI",
    )
    coordinator.preflight_changed.emit(ComfyPreflightSnapshot((process,)))
    app.processEvents()
    assert window.page_stack.currentWidget() is window.comfy_preflight_page
    assert not window.primary_button.isEnabled()
    assert window.comfy_preflight_page.close_button.isHidden() is False
    running_height = window.comfy_preflight_page.sizeHint().height()
    assert window.page_stack.height() == running_height
    assert running_height <= window.page_stage.contentsRect().height()
    assert (
        window.comfy_preflight_page.close_button.geometry().bottom()
        < window.comfy_preflight_page.explanation_panel.geometry().top()
    )
    explanation_labels = (
        window.comfy_preflight_page.explanation_panel.title_label,
        window.comfy_preflight_page.explanation_panel.description_label,
        *window.comfy_preflight_page.explanation_panel.detail_labels,
    )
    for index, current_label in enumerate(explanation_labels[:-1]):
        next_label = explanation_labels[index + 1]
        assert current_label.geometry().bottom() < next_label.geometry().top()
        required_height = current_label.heightForWidth(current_label.width())
        assert required_height < 0 or current_label.height() >= required_height

    coordinator.preflight_changed.emit(ComfyPreflightSnapshot(()))
    app.processEvents()
    assert window.primary_button.isEnabled()
    assert "closed" in window.comfy_preflight_page.status_label.text().lower()
    assert window.page_stack.height() >= window.comfy_preflight_page.sizeHint().height()
    window._advance()
    assert window.page_stack.currentWidget() is window.target_mode_page

    window._emit_close_requested_on_close = False
    window.close()
    assert coordinator.shutdown_calls == 1


def _show_attached_python_choice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[
    OnboardingWindow,
    _ResettingDraftController,
    _FakeEnvironmentCoordinator,
    Path,
]:
    """Build a rendered window at the attached-Python decision page."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    workspace = tmp_path / "UnusualComfyUI"
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.ATTACHED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=workspace,
    )
    controller = _ResettingDraftController(draft, OnboardingFlowMode.FIRST_RUN)
    coordinator = _FakeEnvironmentCoordinator()
    window = OnboardingWindow(
        controller=cast(OnboardingController, controller),
        environment_coordinator=cast(ComfyEnvironmentCoordinator, coordinator),
    )
    window._show_page(OnboardingPageId.ATTACHED_LOCAL)
    window.show()
    _app().processEvents()

    window._advance()
    assert coordinator.discoveries == [workspace.resolve()]
    assert not window.primary_button.isEnabled()

    coordinator.discovery_finished.emit(
        ComfyPythonDiscoveryResult(binding=None, probes=())
    )
    _app().processEvents()
    assert window._current_page is OnboardingPageId.ATTACHED_PYTHON_CHOICE
    return window, controller, coordinator, workspace


def test_attached_python_process_route_is_guided_and_switches_from_footer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Process recovery should begin only after an equal route choice."""

    window, controller, coordinator, workspace = _show_attached_python_choice(
        monkeypatch,
        tmp_path,
    )
    choice_page = window.attached_python_choice_page
    assert choice_page.process_button.text() == "Detect from running ComfyUI"
    assert choice_page.manual_button.text() == "Select Python executable manually"
    assert choice_page.process_button.width() == choice_page.manual_button.width()
    assert window.route_switch_button.isHidden()
    assert window.primary_button.isHidden()

    choice_page.process_button.click()
    _app().processEvents()
    assert window._current_page is OnboardingPageId.ATTACHED_PYTHON_PROCESS
    assert coordinator.recoveries == [(workspace.resolve(), None)]
    status_panel = window.attached_python_process_page.status_panel
    assert status_panel.title_label.text() == "Open ComfyUI yourself"
    guidance = status_panel.description_label.text()
    assert "Start this ComfyUI installation" in guidance
    assert "shortcut, script, or launcher" in guidance
    assert "detect it automatically" in guidance
    assert window.route_switch_button.text() == "Select Python manually instead"
    assert window.route_switch_button.isHidden() is False
    assert window.primary_button.isHidden()
    footer_right = window.footer_row.mapTo(
        window,
        QPoint(window.footer_row.width(), 0),
    ).x()
    switch_right = window.route_switch_button.mapTo(
        window,
        QPoint(window.route_switch_button.width(), 0),
    ).x()
    footer_top = window.footer_row.mapTo(window, QPoint(0, 0)).y()
    switch_top = window.route_switch_button.mapTo(window, QPoint(0, 0)).y()
    assert abs(switch_right - footer_right) <= 2
    assert switch_top >= footer_top

    process = LocalComfyProcess(
        pid=456,
        create_time=2.0,
        python_executable=workspace / "venv" / "Scripts" / "python.exe",
        workspace=workspace.resolve(),
    )
    binding = ComfyPythonBinding(
        executable=process.python_executable,
        version="3.13",
        architecture="AMD64",
        prefix=process.python_executable.parent.parent,
        base_prefix=process.python_executable.parent.parent,
        source=ComfyPythonSelectionSource.RUNNING_COMFY,
    )
    coordinator.recovery_changed.emit(
        AttachedPythonRecoverySnapshot(
            state=AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN,
            binding=binding,
            processes=(process,),
            detail="Found the Python environment. Close ComfyUI to continue.",
        )
    )
    assert controller.draft.attached_python_binding == binding
    assert window.primary_button.isHidden()
    assert window.route_switch_button.isHidden()
    assert window.attached_python_process_page.close_button.isHidden() is False

    coordinator.recovery_changed.emit(
        AttachedPythonRecoverySnapshot(
            state=AttachedPythonRecoveryState.READY,
            binding=binding,
            processes=(),
            detail="ComfyUI is closed and its Python environment is ready.",
        )
    )
    assert window.primary_button.isEnabled()
    assert window.primary_button.isHidden() is False
    window._advance()
    assert window.page_stack.currentWidget() is window.folder_setup_page

    window._emit_close_requested_on_close = False
    window.close()


def test_attached_python_manual_route_guides_before_opening_picker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manual recovery should open Explorer only from its explicit Browse action."""

    picker_calls: list[tuple[str, str]] = []
    selected_python = tmp_path / "UnusualComfyUI" / "venv" / "Scripts" / "python.exe"

    def choose_python(
        _parent: object,
        title: str,
        directory: str,
        _filter: str,
    ) -> tuple[str, str]:
        """Record the explicit Browse interaction and return a deterministic path."""

        picker_calls.append((title, directory))
        return str(selected_python), ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", choose_python)
    window, controller, coordinator, workspace = _show_attached_python_choice(
        monkeypatch,
        tmp_path,
    )

    window.attached_python_choice_page.manual_button.click()
    _app().processEvents()
    assert window.page_stack.currentWidget() is window.attached_python_manual_page
    assert picker_calls == []
    assert window.attached_python_manual_page.browse_button.isHidden() is False
    assert window.route_switch_button.text() == "Detect from running ComfyUI instead"
    guidance_panel = window.attached_python_manual_page.guidance_panel
    guidance = " ".join(
        (
            guidance_panel.title_label.text(),
            guidance_panel.description_label.text(),
            *(label.text() for label in guidance_panel.detail_labels),
        )
    )
    assert "already checked the usual environment locations" in guidance
    assert "custom shortcut, script, launcher, or environment manager" in guidance
    assert "venv\\Scripts" not in guidance
    assert ".venv\\Scripts" not in guidance
    assert "python_embeded" not in guidance

    window.route_switch_button.click()
    assert window.page_stack.currentWidget() is window.attached_python_process_page
    assert picker_calls == []
    window.route_switch_button.click()
    assert window.page_stack.currentWidget() is window.attached_python_manual_page
    assert picker_calls == []

    window.attached_python_manual_page.browse_button.click()
    assert len(picker_calls) == 1
    assert coordinator.validations == [(workspace.resolve(), selected_python.resolve())]
    binding = ComfyPythonBinding(
        executable=selected_python.resolve(),
        version="3.13",
        architecture="AMD64",
        prefix=selected_python.parent.parent,
        base_prefix=selected_python.parent.parent,
        source=ComfyPythonSelectionSource.USER_SELECTED,
    )
    coordinator.browse_finished.emit(
        ComfyPythonProbeResult(
            candidate=ComfyPythonCandidate(
                executable=selected_python.resolve(),
                evidence="user selected",
                priority=0,
            ),
            binding=binding,
            failure=None,
        )
    )
    assert controller.draft.attached_python_binding == binding
    assert coordinator.recoveries[-1] == (workspace.resolve(), binding)

    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_reads_folder_fields_before_navigation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Folder setup should store custom roots before leaving the page."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    controller = _FakeController(draft, OnboardingFlowMode.FIRST_RUN)
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            controller,
        )
    )
    monkeypatch.setattr(window, "_show_page", lambda _page_id: None)
    window._current_page = OnboardingPageId.FOLDERS
    model_root = tmp_path / "Models"
    output_root = tmp_path / "Images"

    window.folder_setup_page.managed_model_root_edit.setText(str(model_root))
    window.folder_setup_page.output_root_edit.setText(str(output_root))

    window._advance()

    assert controller.draft.managed_model_root == model_root.resolve()
    assert controller.draft.managed_model_root_uses_default is False
    assert controller.draft.output_root == output_root.resolve()
    assert controller.draft.output_root_uses_default is False
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_collects_integration_toggles_and_api_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Integration setup should collect toggles and keep the API key short-lived."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    controller = _FakeController(draft, OnboardingFlowMode.FIRST_RUN)
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            controller,
        )
    )
    monkeypatch.setattr(window, "_show_page", lambda _page_id: None)
    window._current_page = OnboardingPageId.INTEGRATIONS

    window.integrations_page.danbooru_tag_help_checkbox.setChecked(False)
    window.integrations_page.civitai_downloads_checkbox.setChecked(False)
    window.integrations_page.set_danbooru_image_policy("safe_and_questionable")
    window.integrations_page.set_civitai_thumbnail_policy("allow_soft")
    window.integrations_page.civitai_api_key_edit.setText("civitai-secret")

    window._advance()

    assert controller.draft.danbooru_tag_help_enabled is False
    assert controller.draft.danbooru_safe_previews_enabled is True
    assert controller.draft.danbooru_image_rating_policy == "safe_and_questionable"
    assert controller.draft.civitai_downloads_enabled is False
    assert controller.draft.civitai_safe_thumbnails_enabled is True
    assert controller.draft.civitai_thumbnail_safety_policy == "allow_soft"
    assert controller.last_civitai_api_key == "civitai-secret"
    assert window.integrations_page.civitai_api_key_edit.text() == ""
    window._emit_close_requested_on_close = False
    window.close()


def test_provisioning_live_output_stays_inside_status_panel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Setup live output should remain bounded inside the status card."""

    app = _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )
    window.resize(1220, 900)
    window._show_page(OnboardingPageId.PROVISIONING)
    window.provisioning_page.append_log(
        "Downloading torch-2.14.0.dev20260620%2Bcu130-cp312-cp312-win_amd64.whl "
        "(1969.5 MB)"
    )
    window.show()
    app.processEvents()

    status_panel = window.provisioning_page.status_panel
    details_surface = window.provisioning_page.details_surface
    status_layout = status_panel.layout()
    assert status_layout is not None
    status_margins = status_layout.contentsMargins()
    status_contents = status_panel.rect().adjusted(
        status_margins.left(),
        status_margins.top(),
        -status_margins.right(),
        -status_margins.bottom(),
    )

    assert status_contents.contains(details_surface.geometry().topLeft())
    assert status_contents.contains(details_surface.geometry().bottomRight())
    assert details_surface.contentsRect().contains(
        details_surface.log_view.geometry().topLeft()
    )
    assert details_surface.contentsRect().contains(
        details_surface.log_view.geometry().bottomRight()
    )

    window._emit_close_requested_on_close = False
    window.close()
    window.deleteLater()
    app.processEvents()


def test_onboarding_window_renders_managed_runtime_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed-local onboarding should show the detected runtime summary and toggles."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
        detected_platform="windows",
        detected_accelerator="nvidia",
        selected_install_target="windows_nvidia",
        selected_python_version="3.13",
        selected_comfy_channel="latest",
        selected_backend_policy="cuda_nightly_cu130",
        selected_torch_channel="nightly",
        selected_torch_reason="NVIDIA installs default to nightly torch.",
        selected_stability="experimental",
        force_cpu_mode=True,
        prefer_edge_torch=True,
        prefer_edge_comfy_channel=False,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )

    assert (
        "windows_nvidia"
        in window.managed_local_page.runtime_summary_panel.target_label.text()
    )
    assert (
        "nightly"
        in window.managed_local_page.runtime_summary_panel.torch_channel_label.text()
    )
    assert (
        window.managed_local_page.runtime_summary_panel.force_cpu_checkbox.isChecked()
        is True
    )
    assert (
        window.managed_local_page.runtime_summary_panel.edge_torch_checkbox.isChecked()
        is True
    )
    window._emit_close_requested_on_close = False
    window.close()


def test_managed_runtime_preferences_survive_draft_refresh_during_advance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed advanced choices should be captured before controller refreshes."""

    _app()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    controller = _FakeController(draft, OnboardingFlowMode.FIRST_RUN)
    window = OnboardingWindow(controller=cast(OnboardingController, controller))
    window._show_page(OnboardingPageId.MANAGED_LOCAL)
    summary = window.managed_local_page.runtime_summary_panel
    summary.force_cpu_checkbox.setChecked(True)
    summary.edge_torch_checkbox.setChecked(True)
    summary.edge_channel_checkbox.setChecked(True)
    captured: list[tuple[bool, bool, bool]] = []

    def refresh_draft(_host: str, _port: int) -> None:
        """Simulate the production controller's synchronous draft refresh."""

        controller.draft_changed.emit(controller.draft)

    def record_preferences(
        *,
        force_cpu_mode: bool,
        prefer_edge_torch: bool,
        prefer_edge_comfy_channel: bool,
    ) -> None:
        """Record the preferences handed to the controller."""

        captured.append((force_cpu_mode, prefer_edge_torch, prefer_edge_comfy_channel))

    monkeypatch.setattr(controller, "update_endpoint", refresh_draft)
    monkeypatch.setattr(
        controller,
        "update_managed_runtime_preferences",
        record_preferences,
    )

    window._advance()

    assert captured == [(True, True, True)]
    window._emit_close_requested_on_close = False
    window.close()
