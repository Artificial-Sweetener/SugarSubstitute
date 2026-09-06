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


def test_onboarding_window_reads_folder_fields_before_navigation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Folder setup should store custom roots before leaving the page."""

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
    controller = _FakeController(draft, OnboardingFlowMode.FIRST_RUN)
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            controller,
        )
    )
    monkeypatch.setattr(window, "_show_page", lambda _page_id: None)
    window._current_page = OnboardingPageId.FOLDERS
    model_root = tmp_path / "WebUI" / "models"
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


def test_managed_runtime_preferences_survive_draft_refresh_during_advance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Managed advanced choices should be captured before controller refreshes."""

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
