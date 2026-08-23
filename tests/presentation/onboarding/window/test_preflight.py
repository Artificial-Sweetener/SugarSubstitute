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
from PySide6.QtWidgets import QLabel

from substitute.application.onboarding.comfy_environment_service import (
    ComfyPreflightSnapshot,
)
from substitute.domain.onboarding import (
    LocalComfyProcess,
)
from substitute.presentation.onboarding.comfy_environment_coordinator import (
    ComfyEnvironmentCoordinator,
)
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
from tests.support.qt.semantic_wait import wait_for_qt_condition

from .controller_double import _FakeController
from .environment_double import _FakeEnvironmentCoordinator


def test_onboarding_clean_preflight_skips_the_warning_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A passing safety check should advance without exposing its warning page."""

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
    coordinator = _FakeEnvironmentCoordinator()
    window = OnboardingWindow(
        controller=cast(
            OnboardingController,
            _FakeController(draft, OnboardingFlowMode.FIRST_RUN),
        ),
        environment_coordinator=cast(ComfyEnvironmentCoordinator, coordinator),
    )
    window.show()

    window._advance()
    assert window._current_page is OnboardingPageId.WELCOME
    assert coordinator.preflight_starts == 1
    assert not window.primary_button.isEnabled()

    coordinator.preflight_changed.emit(ComfyPreflightSnapshot(()))
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

    assert window._current_page is OnboardingPageId.TARGET_MODE
    assert coordinator.preflight_starts == 1
    assert not window.primary_button.isEnabled()
    coordinator.preflight_changed.emit(ComfyPreflightSnapshot(()))
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
    coordinator = _FakeEnvironmentCoordinator()
    window = OnboardingWindow(
        controller=cast(OnboardingController, controller),
        environment_coordinator=cast(ComfyEnvironmentCoordinator, coordinator),
    )
    window.show()

    window._advance()
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

    def running_preflight_layout_has_converged() -> bool:
        """Return whether the live warning owns its requested stack height."""

        activate_widget_layouts(
            window,
            window.page_stage,
            window.page_stack,
            window.comfy_preflight_page,
            window.comfy_preflight_page.explanation_panel,
        )
        return (
            window.page_stack.height()
            == window.comfy_preflight_page.sizeHint().height()
        )

    wait_for_qt_condition(running_preflight_layout_has_converged)
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
        current_widget = cast(QLabel, current_label)
        next_label = cast(QLabel, explanation_labels[index + 1])
        assert current_widget.geometry().bottom() < next_label.geometry().top()
        required_height = current_widget.heightForWidth(current_widget.width())
        assert required_height < 0 or current_widget.height() >= required_height

    coordinator.preflight_changed.emit(ComfyPreflightSnapshot(()))
    activate_widget_layouts(window.page_stack, window.comfy_preflight_page)
    assert window.primary_button.isEnabled()
    assert "closed" in window.comfy_preflight_page.status_label.text().lower()
    assert window.page_stack.height() >= window.comfy_preflight_page.sizeHint().height()
    window._advance()
    assert window.page_stack.currentWidget() is window.target_mode_page

    window._emit_close_requested_on_close = False
    window.close()
    assert coordinator.shutdown_calls == 1
