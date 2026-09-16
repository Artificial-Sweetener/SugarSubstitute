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

"""Keep every setup surface accessible inside the desktop's logical work area."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QWidget

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from launcher.sugarsubstitute_launcher.ui.repair_window import RepairWindow
from substitute.presentation.onboarding.onboarding_controller import (
    OnboardingController,
)
from substitute.presentation.onboarding.onboarding_models import (
    OnboardingDraft,
    OnboardingFlowMode,
    OnboardingTargetMode,
)
from substitute.presentation.onboarding.onboarding_window import OnboardingWindow
from tests.launcher.installation_workflow.support import (
    close_and_delete_launcher_window,
    release_source_for_test,
    workflow_factory,
)
from tests.presentation.onboarding.window.controller_double import _FakeController
from tests.support.qt.lifecycle import (
    activate_widget_layouts,
    destroy_qt_object,
    ensure_qt_application,
)
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


@pytest.mark.parametrize("surface", ("installer", "repair", "comfy-setup"))
def test_setup_window_fits_compact_work_area(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    """Keep setup controls on-screen when a remote desktop has less work area."""
    application = ensure_qt_application()
    screen = application.primaryScreen()
    assert screen is not None
    work_area = QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(screen, "availableGeometry", lambda: QRect(work_area))
    window = _window(surface, tmp_path)
    try:
        window.show()
        activate_widget_layouts(window)
        wait_for_queued_qt_turn()
        assert window.width() == 1180
        assert window.height() == 760
        for bounds in (
            QRect(0, 0, 1024, 720),
            QRect(-1024, 120, 1024, 720),
            QRect(0, 0, 1920, 1080),
        ):
            work_area = bounds
            screen.availableGeometryChanged.emit(QRect(bounds))
            activate_widget_layouts(window)
            wait_for_queued_qt_turn()
            assert window.width() <= bounds.width()
            assert window.height() <= bounds.height()
            assert bounds.contains(window.frameGeometry())
        assert window.width() == 1180
        assert window.height() == 760
    finally:
        if isinstance(window, LauncherMainWindow):
            close_and_delete_launcher_window(window)
        else:
            if isinstance(window, OnboardingWindow):
                window._emit_close_requested_on_close = False
            window.close()
            destroy_qt_object(window)


def _window(surface: str, root: Path) -> QWidget:
    """Mount production chrome with inert provisioning boundaries."""
    if surface == "installer":
        return LauncherMainWindow(
            initial_layout=InstallLayout.from_root(root),
            continue_install=False,
            repair=False,
            update_check_enabled=False,
            initial_release_source=release_source_for_test(),
            workflow_factory=workflow_factory(),
        )
    if surface == "repair":
        return RepairWindow()
    draft = OnboardingDraft(
        installation_root=root,
        target_mode=OnboardingTargetMode.MANAGED_LOCAL,
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        managed_workspace_path=root / "comfyui",
        attached_workspace_path=None,
    )
    return OnboardingWindow(
        controller=cast(
            OnboardingController, _FakeController(draft, OnboardingFlowMode.FIRST_RUN)
        )
    )


def test_all_setup_pages_fit_compact_viewport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep page content horizontally reachable without relying on hidden scrolling."""
    application = ensure_qt_application()
    screen = application.primaryScreen()
    assert screen is not None
    monkeypatch.setattr(screen, "availableGeometry", lambda: QRect(0, 0, 1024, 720))
    window = _window("comfy-setup", tmp_path)
    assert isinstance(window, OnboardingWindow)
    try:
        window.show()
        for page_id, page in window._pages.items():
            window.page_stage.show_page(page)
            activate_widget_layouts(window)
            wait_for_queued_qt_turn()
            window.page_stage.refresh_layout()
            viewport = window.page_stage.viewport()
            column = page.findChild(QWidget, "OnboardingContentColumn")
            if column is None:
                continue
            bounds = QRect(column.mapTo(viewport, QPoint(0, 0)), column.size())
            assert bounds.left() >= 0, page_id
            assert bounds.right() < viewport.width(), (page_id, bounds, viewport.size())
    finally:
        window._emit_close_requested_on_close = False
        window.close()
        destroy_qt_object(window)
