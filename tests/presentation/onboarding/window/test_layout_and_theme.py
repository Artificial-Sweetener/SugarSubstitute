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
from PySide6.QtCore import QPoint, QRect
from qfluentwidgets import Theme  # type: ignore[import-untyped]

from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_window import (
    OnboardingWindow,
)

from tests.support.qt.lifecycle import activate_widget_layouts, ensure_qt_application
from tests.support.qt.semantic_wait import wait_for_qt_condition
from tests.presentation.theme.support import fluent_theme

from .controller_double import _FakeController


def test_onboarding_pages_fit_fixed_window_layout_budget(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every setup page should remain inside the fixed window and above its footer."""

    ensure_qt_application()
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
    window.ensurePolished()
    activate_widget_layouts(
        window,
        window.root_container,
        window.content_panel,
        window.page_stage,
        window.page_stack,
    )
    window._provisioning_started = True

    page_height_budget = window.page_stage.contentsRect().height()
    for page_id, page in window._pages.items():
        window._show_page(page_id)

        def page_layout_has_converged() -> bool:
            """Return whether the selected page fits its authoritative stage."""

            activate_widget_layouts(
                window,
                window.page_stage,
                window.page_stack,
                page,
            )
            window.page_stage.refresh_current_page_height()
            return (
                window.page_stack.currentWidget() is page
                and window.page_stack.height() == page.sizeHint().height()
                and window.page_stack.contentsRect().contains(page.geometry())
            )

        wait_for_qt_condition(
            page_layout_has_converged,
            description=f"{page_id.value} layout to converge",
        )

        assert page.sizeHint().height() <= page_height_budget, (
            f"{page_id.value} requests {page.sizeHint().height()}px from a "
            f"{page_height_budget}px page stage"
        )
        assert window.page_stage.verticalScrollBar().maximum() == 0, (
            f"{page_id.value} creates an installer scrollbar"
        )
        stack_rect = QRect(
            window.page_stack.mapTo(window.page_stage.viewport(), QPoint(0, 0)),
            window.page_stack.size(),
        )
        assert window.page_stage.viewport().contentsRect().contains(stack_rect), (
            f"{page_id.value} page stack leaves the fixed page stage"
        )
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


def test_onboarding_window_stylesheet_refreshes_after_qfluent_theme_switch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Onboarding custom styles should refresh from QFluent theme changes."""

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
    with fluent_theme(Theme.DARK):
        window = OnboardingWindow(
            controller=cast(
                OnboardingController,
                _FakeController(draft, OnboardingFlowMode.REPAIR),
            )
        )
        dark_style = window.root_container.styleSheet()

        with fluent_theme(Theme.LIGHT):
            wait_for_qt_condition(
                lambda: window.root_container.styleSheet() != dark_style
            )

            assert window.root_container.styleSheet() != dark_style
            assert "rgba(0, 0, 0, 0.74)" in window.root_container.styleSheet()
