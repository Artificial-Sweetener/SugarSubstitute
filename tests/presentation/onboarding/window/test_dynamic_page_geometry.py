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

"""Verify dynamic setup content remains readable inside the scrolling stage."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
from tests.support.qt.semantic_wait import (
    wait_for_qt_condition,
    wait_for_queued_qt_turn,
)

from substitute.presentation.onboarding.onboarding_completion_pages import (
    ProvisioningPage,
)
from substitute.presentation.onboarding.onboarding_folder_setup_page import (
    FolderSetupPage,
)
from substitute.presentation.onboarding.onboarding_page_stage import OnboardingPageStage
from sugarsubstitute_shared.localization import app_text


def test_scan_feedback_resizes_the_page_without_overlapping_fields() -> None:
    """Let the geometry owner react when an existing page reveals scan feedback."""
    window = QWidget()
    layout = QVBoxLayout(window)
    stage = OnboardingPageStage(window)
    layout.addWidget(stage)
    page = FolderSetupPage()
    stage.add_page(page)
    window.resize(1000, 650)
    window.show()
    stage.show_page(page)
    wait_for_qt_condition(lambda: page.isVisible() and page.height() > 0)
    wait_for_queued_qt_turn()
    original_height = stage.page_stack.height()

    page.set_scan_status(app_text("Scanning for SDXL and Anima…"))
    wait_for_qt_condition(lambda: stage.page_stack.height() > original_height)
    scan = page.model_scan_status.geometry()
    field = page.model_path_block.geometry()
    assert scan.top() >= field.bottom()
    assert page.managed_model_section.rect().contains(scan)

    scan_height = stage.page_stack.height()
    page.set_scan_status(app_text("\n".join(["Scanning models"] * 30)))
    wait_for_qt_condition(lambda: stage.page_stack.height() > scan_height)
    wait_for_qt_condition(
        lambda: stage.verticalScrollBar().maximum() > 0,
        state=lambda: (
            page.sizeHint().height(),
            page.minimumSizeHint().height(),
            stage.page_stack.height(),
            stage.viewport().height(),
            page.model_scan_status.sizeHint().height(),
        ),
    )
    assert page.managed_model_section.rect().contains(page.model_scan_status.geometry())

    page.reset_scan_status()
    wait_for_qt_condition(lambda: stage.page_stack.height() == original_height)


def test_visible_model_progress_retains_item_counts_and_completion_copy() -> None:
    """Keep progress copy independent of whether its widgets just became visible."""
    page = ProvisioningPage()
    page.show()
    wait_for_qt_condition(page.isVisible)
    for completed in (25, 50):
        page.set_model_download_progress(
            completed_bytes=completed,
            total_bytes=100,
            current_item="model.safetensors",
            current_item_index=2,
            total_items=3,
        )
        assert "2 of 3" in page.model_progress_label.text()
    page.set_model_download_progress(
        completed_bytes=100,
        total_bytes=100,
        current_item="model.safetensors",
        complete=True,
    )
    assert "Downloading" not in page.model_progress_label.text()
