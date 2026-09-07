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
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QPlainTextEdit, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    LineEdit,
    PrimaryPushButton,
    RadioButton,
    SegmentedWidget,
)

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
from substitute.presentation.shell.window_effects import ShellBackdropMode
from substitute.presentation.shell.window_frame import SubstituteWindowFrame
from substitute.presentation.widgets.spin_box import SpinBox
from sugarsubstitute_shared.presentation.installer_surface import (
    INSTALLER_BRAND_BAR_HEIGHT,
    INSTALLER_WORDMARK_OPTICAL_Y_OFFSET,
    InstallerBodyMaterialSurface,
    InstallerBrandBar,
)

from tests.support.qt.lifecycle import ensure_qt_application

from .controller_double import _FakeController


def test_onboarding_window_uses_handoff_geometry(tmp_path: Path) -> None:
    """Installer handoff geometry should place onboarding on the same frame."""

    ensure_qt_application()
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
        ),
        initial_geometry=(20, 30, 1260, 800),
    )

    assert window.geometry().x() == 20
    assert window.geometry().y() == 30
    assert window.width() == 1180
    assert window.height() == 760
    window._emit_close_requested_on_close = False
    window.close()


def test_onboarding_window_builds_all_required_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Window should materialize every dedicated onboarding page."""

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
            _FakeController(draft, OnboardingFlowMode.REPAIR),
        )
    )
    window.show()
    application.processEvents()
    frame_layout = window.layout()
    assert frame_layout is not None
    root_layout = window.root_container.layout()
    assert root_layout is not None

    assert isinstance(window, SubstituteWindowFrame)
    assert window._backdrop_mode is ShellBackdropMode.MICA_ALT
    assert "background: transparent" in window.root_container.styleSheet()
    assert window.bodyMaterialSurface is None
    assert window.menuContainer is None
    assert frame_layout.contentsMargins().top() == 0
    assert root_layout.contentsMargins().top() == 0
    assert window.minimumWidth() == window.maximumWidth()
    assert window.minimumHeight() == window.maximumHeight()
    assert window.titleBar.minBtn.isHidden() is True
    assert window.titleBar.maxBtn.isHidden() is True
    assert window.titleBar.closeBtn.isHidden() is False
    assert window.titleBar.height() == INSTALLER_BRAND_BAR_HEIGHT
    assert window.titleBar.closeBtn.geometry().top() == 0
    assert window.titleBar.closeBtn.geometry().right() == window.titleBar.rect().right()
    for drag_point in (
        QPoint(80, 20),
        QPoint(180, INSTALLER_BRAND_BAR_HEIGHT // 2),
        QPoint(600, INSTALLER_BRAND_BAR_HEIGHT - 8),
        QPoint(980, INSTALLER_BRAND_BAR_HEIGHT // 2),
    ):
        assert window.titleBar.canDrag(drag_point)
    assert not window.windowIcon().isNull()
    assert window.brand_bar.wordmark.renderer().isValid()
    wordmark_top = window.brand_bar.wordmark.mapTo(
        window.brand_bar,
        QPoint(0, 0),
    ).y()
    centered_wordmark_top = (
        window.brand_bar.height() - window.brand_bar.wordmark.height()
    ) // 2
    assert wordmark_top == centered_wordmark_top + INSTALLER_WORDMARK_OPTICAL_Y_OFFSET
    close_hit = window.titleBar.closeBtn.mapTo(
        window, window.titleBar.closeBtn.rect().center()
    )
    assert window.childAt(close_hit) is window.titleBar.closeBtn
    assert window.page_stack.count() == 16
    assert window.page_stack.parentWidget() is window.page_scroll_content
    assert (
        window.attached_python_choice_page.objectName()
        == "OnboardingAttachedPythonChoicePage"
    )
    assert (
        window.attached_python_process_page.objectName()
        == "OnboardingAttachedPythonProcessPage"
    )
    assert (
        window.attached_python_manual_page.objectName()
        == "OnboardingAttachedPythonManualPage"
    )
    assert window.folder_setup_page.objectName() == "OnboardingFolderSetupPage"
    assert window.integrations_page.objectName() == "OnboardingIntegrationsPage"
    assert isinstance(window.install_root_page.install_root_edit, LineEdit)
    assert isinstance(window.brand_bar, InstallerBrandBar)
    assert isinstance(window.content_panel, InstallerBodyMaterialSurface)
    assert window.brand_bar.progress_caption.text() == "Step 2 of 5 · Choose a folder"
    assert window.findChild(QWidget, "OnboardingRailTitle") is None
    assert window.findChild(QWidget, "OnboardingStepItem") is None
    assert window.findChildren(QWidget, "OnboardingHeroEyebrow") == []
    assert window.identity_rail.styleSheet() == ""
    assert window.root_container.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert window.content_surface.testAttribute(
        Qt.WidgetAttribute.WA_NoSystemBackground
    )
    assert window.identity_rail.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert window.brand_bar.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    header_pixel = window.root_container.grab().toImage().pixelColor(600, 60)
    body_pixel = window.root_container.grab().toImage().pixelColor(600, 300)
    assert header_pixel.alpha() == 0
    assert body_pixel.alpha() > 0
    assert len(window.target_mode_page.mode_cards) == 3
    assert window.target_mode_page.findChildren(SegmentedWidget) == []
    managed_card = window.target_mode_page.mode_cards[
        OnboardingTargetMode.MANAGED_LOCAL
    ]
    attached_card = window.target_mode_page.mode_cards[
        OnboardingTargetMode.ATTACHED_LOCAL
    ]
    assert managed_card.selection_radio.text() == "Selected"
    assert attached_card.selection_radio.text() == "Select"
    assert isinstance(managed_card.selection_radio, RadioButton)
    assert managed_card.selection_radio.isChecked() is True
    assert isinstance(window.managed_local_page.port_spinbox, SpinBox)
    assert isinstance(window.primary_button, PrimaryPushButton)
    assert not hasattr(window, "cancel_button")
    log_view = window.provisioning_page.details_surface.log_view
    assert isinstance(log_view, QPlainTextEdit)
    assert window.provisioning_page.hero_panel.title_label.text() == (
        "Finishing your setup"
    )
    assert log_view.toPlainText() == ""
    assert log_view.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert not hasattr(window.provisioning_page, "progress_bar")
    assert window.provisioning_page.details_container.isHidden() is True
    assert window.provisioning_page.overall_progress_bar.maximum() == 100
    assert log_view.maximumHeight() == 280
    assert log_view.minimumHeight() == 220
    assert (
        window.integrations_page.danbooru_image_policy_combo.currentData()
        == "safe_only"
    )
    assert (
        window.integrations_page.civitai_thumbnail_policy_combo.currentData()
        == "sfw_only"
    )
    assert not hasattr(window.integrations_page, "danbooru_safe_previews_checkbox")
    assert not hasattr(window.integrations_page, "civitai_safe_thumbnails_checkbox")
    assert window.issue_banner.isHidden() is False
    assert "Runtime Python executable is missing." not in window.issue_banner.text()
    assert "required local Python file is missing" in window.issue_banner.text()
    assert "Missing runtime Python executable." in window.issue_banner.text()
    assert "can't open yet" not in window.issue_banner.text()
    assert window.install_root_page.hero_panel.title_label.text() == (
        "Choose where Substitute should keep its setup"
    )
    assert "visible config, state, runtime" not in (
        window.install_root_page.hero_panel.description_label.text()
    )
    assert window.target_mode_page.hero_panel.title_label.text() == (
        "Choose how Substitute should reach ComfyUI"
    )
