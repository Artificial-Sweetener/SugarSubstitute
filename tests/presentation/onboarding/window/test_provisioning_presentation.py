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

from substitute.application.onboarding import OnboardingProvisioningFailure
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

from tests.support.qt.lifecycle import activate_widget_layouts, ensure_qt_application

from .controller_double import _FakeController


def test_onboarding_window_shows_completion_page_after_provisioning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioning completion should enable the completion review step."""

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


def test_provisioning_live_output_stays_inside_status_panel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Setup live output should remain bounded inside the status card."""

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
    window.resize(1220, 900)
    window._show_page(OnboardingPageId.PROVISIONING)
    window.provisioning_page.append_log(
        "Downloading torch-2.14.0.dev20260620%2Bcu130-cp312-cp312-win_amd64.whl "
        "(1969.5 MB)"
    )
    window.show()
    activate_widget_layouts(
        window,
        window.page_stack,
        window.provisioning_page,
        window.provisioning_page.status_panel,
        window.provisioning_page.details_surface,
    )

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
