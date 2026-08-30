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

"""Contract tests for onboarding integration with the shared terminal view."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_pages import ProvisioningPage
from substitute.presentation.onboarding.onboarding_window import OnboardingWindow
from substitute.presentation.shell.comfy_output_panel import ComfyOutputPanel
from tests.support.qt.lifecycle import destroy_qt_object, ensure_qt_application


class _TerminalIntegrationController(QObject):
    """Expose only the controller state and signals consumed during window startup."""

    draft_changed = Signal(object)
    provisioning_started = Signal()
    provisioning_finished = Signal()
    progress_status_changed = Signal(str)
    progress_log_emitted = Signal(str)
    failure_reported = Signal(object)
    completion_ready = Signal(object)

    def __init__(self, draft: OnboardingDraft) -> None:
        """Store deterministic first-run state for terminal routing."""

        super().__init__()
        self._draft = draft

    @property
    def draft(self) -> OnboardingDraft:
        """Return the fixed onboarding draft."""

        return self._draft

    @property
    def flow_mode(self) -> OnboardingFlowMode:
        """Return the first-run route used by this integration contract."""

        return OnboardingFlowMode.FIRST_RUN


@pytest.fixture(scope="module", autouse=True)
def onboarding_terminal_qt_application() -> Iterator[QApplication]:
    """Keep one process-local Qt application alive for onboarding terminal tests."""

    application = ensure_qt_application()
    yield application


@pytest.fixture
def owned_qt_objects() -> Iterator[list[QObject]]:
    """Destroy every native Qt owner created by the current test."""

    objects: list[QObject] = []
    yield objects
    for candidate in reversed(objects):
        destroy_qt_object(candidate)


def test_onboarding_window_routes_controller_logs_into_shared_terminal_view(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    owned_qt_objects: list[QObject],
) -> None:
    """Provisioning logs should render through the shared terminal view binding."""

    monkeypatch.setattr(OnboardingWindow, "_center_on_screen", lambda self: None)
    draft = OnboardingDraft(
        installation_root=tmp_path,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=tmp_path / "comfyui",
        attached_workspace_path=None,
    )
    terminal_controller = _TerminalIntegrationController(draft)
    controller = cast(OnboardingController, terminal_controller)
    window = OnboardingWindow(controller=controller)
    owned_qt_objects.append(window)

    terminal_controller.progress_log_emitted.emit("Configured managed ComfyUI.\n")

    output_title = window.provisioning_page.findChild(QWidget, "OnboardingOutputTitle")
    assert output_title is not None
    assert (
        window.provisioning_page.details_surface.log_view.toPlainText()
        == "Configured managed ComfyUI."
    )


def test_onboarding_and_shell_use_same_terminal_surface_style(
    owned_qt_objects: list[QObject],
) -> None:
    """Onboarding and shell should render the same shared terminal color treatment."""

    provisioning_page = ProvisioningPage()
    shell_panel = ComfyOutputPanel()
    owned_qt_objects.extend((provisioning_page, shell_panel))
    shell_panel_terminal = shell_panel.findChild(
        type(provisioning_page.details_surface)
    )

    assert shell_panel_terminal is not None
    assert (
        provisioning_page.details_surface.styleSheet()
        == shell_panel_terminal.styleSheet()
    )
