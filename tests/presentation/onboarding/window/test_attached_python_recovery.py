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
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QFileDialog

from substitute.application.onboarding.comfy_environment_service import (
    AttachedPythonRecoverySnapshot,
    AttachedPythonRecoveryState,
)
from substitute.domain.onboarding import (
    ComfyPythonBinding,
    ComfyPythonCandidate,
    ComfyPythonDiscoveryResult,
    ComfyPythonProbeResult,
    ComfyPythonSelectionSource,
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

from .controller_double import _ResettingDraftController
from .environment_double import _FakeEnvironmentCoordinator


def test_onboarding_window_reads_attached_workspace_before_draft_reset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Attached-local save should capture the edited workspace before draft_changed resets the form."""

    ensure_qt_application()
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
    expected_workspace = tmp_path / "external-comfyui"

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

    ensure_qt_application()
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
    activate_widget_layouts(window, window.page_stack, window.attached_local_page)

    window._advance()
    assert coordinator.discoveries == [workspace.resolve()]
    assert not window.primary_button.isEnabled()

    coordinator.discovery_finished.emit(
        ComfyPythonDiscoveryResult(binding=None, probes=())
    )
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
    activate_widget_layouts(
        window,
        window.page_stack,
        window.attached_python_process_page,
        window.footer_row,
    )
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
