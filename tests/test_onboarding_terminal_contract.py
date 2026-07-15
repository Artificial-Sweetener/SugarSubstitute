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

import os
from pathlib import Path
from typing import cast

from PySide6.QtWidgets import QApplication, QWidget
import pytest

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real onboarding terminal tests require non-xdist execution on Windows",
        allow_module_level=True,
    )

from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_window import OnboardingWindow
from substitute.presentation.shell.comfy_output_panel import ComfyOutputPanel
from tests.test_onboarding_window_contract import _FakeController


def _app() -> QApplication:
    """Return the shared QApplication used by onboarding terminal tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_onboarding_window_routes_controller_logs_into_shared_terminal_view(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Provisioning logs should render through the shared terminal view binding."""

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

    controller.progress_log_emitted.emit("Configured managed ComfyUI.\n")
    QApplication.processEvents()

    output_title = window.provisioning_page.findChild(QWidget, "OnboardingOutputTitle")
    assert output_title is not None
    assert (
        window.provisioning_page.details_surface.log_view.toPlainText()
        == "Configured managed ComfyUI."
    )
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_and_shell_use_same_terminal_surface_style(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Onboarding and shell should render the same shared terminal color treatment."""

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
    shell_panel = ComfyOutputPanel()
    shell_panel_terminal = shell_panel.findChild(
        type(window.provisioning_page.details_surface)
    )

    assert shell_panel_terminal is not None
    assert (
        window.provisioning_page.details_surface.styleSheet()
        == shell_panel_terminal.styleSheet()
    )
    window._emit_close_requested_on_close = False
    window.close()
    shell_panel.close()
