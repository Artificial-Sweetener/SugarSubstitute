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
from PySide6.QtCore import Qt
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
    assert window.folder_setup_page.managed_model_root_edit.cursorPosition() == 0
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


def test_existing_folder_action_keeps_computed_default_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Open the folder picker with its useful computed default intact."""

    application = ensure_qt_application()
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

    assert window.primary_button.isHidden()
    assert window.no_models_button.text() == "No, show recommendations"
    assert window.yes_models_button.text() == "Yes, choose folder"
    window.yes_models_button.click()
    application.processEvents()

    assert window._current_page is OnboardingPageId.FOLDERS
    assert window.folder_setup_page.managed_model_root_edit.text() == str(
        tmp_path / "comfyui" / "models"
    )
    assert window.primary_button.isEnabled()
    window._emit_close_requested_on_close = False
    window.close()


def test_sparse_pages_are_centered_in_the_shared_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Center every fitting focal composition without synthetic overflow."""

    application = ensure_qt_application()
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
    window.show()

    for page_id in (
        OnboardingPageId.EXISTING_MODELS,
        OnboardingPageId.MANAGED_LOCAL,
    ):
        window._show_page(page_id)
        window.page_stage.refresh_current_page_height()
        application.processEvents()
        page = window._pages[page_id]
        content_column = page.content_column
        viewport = window.page_stage.viewport()
        content_center = content_column.mapToGlobal(content_column.rect().center())
        viewport_center = viewport.mapToGlobal(viewport.rect().center())
        assert abs(content_center.x() - viewport_center.x()) <= 5
        assert abs(content_center.y() - viewport_center.y()) <= 2
        assert window.page_stage.verticalScrollBar().maximum() == 0
        assert window.page_stack.width() == viewport.width()

    window._show_page(OnboardingPageId.EXISTING_MODELS)
    application.processEvents()
    hero = window.existing_models_question_page.hero_panel
    visible_left = hero.badge.geometry().left()
    visible_right = hero.description_label.geometry().right()
    visible_center = (visible_left + visible_right) // 2
    assert abs(visible_center - hero.rect().center().x()) <= 1

    window._emit_close_requested_on_close = False
    window.close()


def test_integration_page_presents_every_existing_capability_directly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Present every service preference directly without an advanced tier."""

    application = ensure_qt_application()
    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
        danbooru_image_rating_policy="all_ratings",
        civitai_thumbnail_safety_policy="allow_all",
        civitai_api_key_configured=True,
    )
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        )
    )
    window._show_page(OnboardingPageId.INTEGRATIONS)
    window.show()
    application.processEvents()

    page = window.integrations_page
    assert page.danbooru_tag_help_checkbox.isChecked()
    assert page.civitai_model_help_checkbox.isChecked()
    assert page.civitai_downloads_checkbox.isChecked()
    assert not page.danbooru_details.isHidden()
    assert not page.civitai_details.isHidden()
    assert page.danbooru_image_policy_value() == "all_ratings"
    assert page.civitai_thumbnail_policy_value() == "allow_all"
    assert not page.civitai_downloads_checkbox.isHidden()
    assert not page.civitai_api_key_edit.isHidden()
    assert page.civitai_api_key_status.text() == "API key already saved"
    assert page.civitai_api_key_edit.echoMode() is QLineEdit.EchoMode.Password
    assert not hasattr(page, "danbooru_options_button")
    assert not hasattr(page, "civitai_options_button")
    assert window.page_stage.horizontalScrollBarPolicy() is (
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff
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

    assert "Choose models" in window.brand_bar.progress_caption.text()
    window._show_page(OnboardingPageId.FOLDERS)
    assert "Choose folders" in window.brand_bar.progress_caption.text()
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
    """Keep expert runtime controls in a bounded, non-reflowing surface."""

    application = ensure_qt_application()
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

    window._show_page(OnboardingPageId.MANAGED_LOCAL)
    window.show()
    application.processEvents()
    collapsed_height = window.page_stack.height()
    stable_stage_geometry = window.page_stage.geometry()
    stable_footer_geometry = window.footer_row.geometry()
    window.managed_local_page.advanced_button.click()
    application.processEvents()
    dialog = window.managed_local_page.connection_settings_dialog
    assert dialog.isVisible()
    assert window.managed_local_page.advanced_button.text() == "Advanced settings"
    assert window.page_stack.height() == collapsed_height
    assert window.page_stage.geometry() == stable_stage_geometry
    assert window.footer_row.geometry() == stable_footer_geometry
    assert window.page_stage.verticalScrollBar().maximum() == 0
    assert dialog.width() <= window.width()
    assert dialog.height() <= window.height()

    assert (
        "Windows NVIDIA"
        in window.managed_local_page.runtime_summary_panel.target_label.text()
    )
    assert (
        "Nightly"
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
    dialog.accept()
    application.processEvents()
    assert dialog.isHidden()
    assert window.page_stage.verticalScrollBar().maximum() == 0
    assert window.page_stack.height() == collapsed_height
    assert window.page_stage.geometry() == stable_stage_geometry
    assert window.footer_row.geometry() == stable_footer_geometry
    window._emit_close_requested_on_close = False
    window.close()
