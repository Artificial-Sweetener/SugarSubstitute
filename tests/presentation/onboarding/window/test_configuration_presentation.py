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

"""Verify one cohesive onboarding-window capability."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from PySide6.QtWidgets import QLineEdit

from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingPageId,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_window import (
    OnboardingWindow,
)

from tests.support.qt.lifecycle import ensure_qt_application

from .controller_double import _FakeController


def test_onboarding_window_renders_folder_and_integration_controls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Folder and integration pages should expose the expected first-run controls."""

    ensure_qt_application()
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

    assert window.folder_setup_page.managed_model_section.isHidden() is True
    window._controller.model_session.answer_existing_folder(True)
    window._show_page(OnboardingPageId.FOLDERS)
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

    ensure_qt_application()
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


def test_model_pages_name_the_active_progress_step_accurately(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Do not label the model decision as a generic confirmation step."""

    ensure_qt_application()
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

    window._show_page(OnboardingPageId.EXISTING_MODELS)

    assert window.progress_title_label.text() == "Choose models"
    assert window.step_items[2].title_label.text() == "Choose models"
    window._show_page(OnboardingPageId.FOLDERS)
    assert window.step_items[2].title_label.text() == "Confirm the details"
    assert window.folder_setup_page.managed_model_section.isHidden()
    window._apply_draft(window._controller.draft)
    assert window.folder_setup_page.managed_model_section.isHidden()
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_hides_managed_model_folder_for_remote(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Remote setup should hide the local ComfyUI models folder field."""

    ensure_qt_application()
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

    ensure_qt_application()
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

    assert window.folder_setup_page.managed_model_section.isHidden() is True
    window._controller.model_session.answer_existing_folder(True)
    window._show_page(OnboardingPageId.FOLDERS)
    assert window.folder_setup_page.managed_model_section.isHidden() is False
    assert window.folder_setup_page.managed_model_root_edit.text() == str(
        attached_workspace / "models"
    )
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_renders_managed_runtime_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed-local onboarding should show the detected runtime summary and toggles."""

    ensure_qt_application()
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
