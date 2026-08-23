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

"""Test Comfy environment package detail projection."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QToolButton, QWidget
from qfluentwidgets.common.smooth_scroll import SmoothMode  # type: ignore[import-untyped]

from substitute.application.comfy_environment import ComfyEnvironmentService
from tests.presentation.settings.comfy_environment.backend import EnvironmentBackend
from tests.presentation.settings.comfy_environment.support import (
    application,
    deliver_queued_events,
    environment_page,
)


def test_environment_page_details_show_claimants_and_summary_source() -> None:
    """Selecting a package should show claimant metadata and summary source."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.select_inventory_item("package:custom-node-helper")

    detail_text = page.detail_text()
    assert "custom-node-helper" in detail_text
    assert '"Helper package from installed metadata."' in detail_text
    assert "Required by:\nComfyUI-VFI" in detail_text
    assert "Direct requirement" not in detail_text
    assert "base-helper\n    ComfyUI-EyeCandy\n    ComfyUI-Manager" in detail_text
    assert "    ComfyUI-EyeCandy" in detail_text
    assert "ComfyUI-VFI" in detail_text
    assert "custom-node-helper>=1.0" not in detail_text
    assert "summary: installed metadata" in detail_text
    assert "requirements.txt" not in detail_text
    assert "Core GPU inference runtime" not in detail_text
    assert "Supported actions: none" not in detail_text


def test_environment_page_dependency_names_elide_with_tooltips() -> None:
    """Transitive dependency labels should not clip into malformed names."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )
    page.resize(720, 800)
    page.show()

    deliver_queued_events(app)
    page.select_inventory_item("package:custom-node-helper")
    deliver_queued_events(app)

    dependency_label = next(
        label
        for label in page.detail_claimants_label.findChildren(QLabel)
        if label.toolTip() == "base-helper"
    )
    group_row = dependency_label.parentWidget()
    assert group_row is not None
    toggle_button = cast(Any, group_row).toggle_button
    constrained_width = dependency_label.fontMetrics().horizontalAdvance("base")
    group_row.setFixedWidth(constrained_width + toggle_button.width() + 4)
    deliver_queued_events(app)

    assert dependency_label.text() == "base-helper"
    assert dependency_label.width() <= constrained_width
    rendered_text = QLabel.text(dependency_label)
    assert rendered_text != "base-"
    assert "\u2026" in rendered_text


def test_environment_page_claimants_reappear_after_empty_package_selection() -> None:
    """Claimant details should recover after selecting a package with no claimants."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.select_inventory_item("package:manual-tool")
    deliver_queued_events(app)
    assert page.detail_claimants_label.height() > 0
    assert "No known extension claimant." in page.detail_text()

    page.select_inventory_item("package:custom-node-helper")
    deliver_queued_events(app)

    claimant_labels = page.detail_claimants_label.findChildren(QLabel)
    visible_text = "\n".join(
        label.text() for label in claimant_labels if not label.isHidden()
    )
    assert page.detail_claimants_label.height() > 0
    assert "Required by:" in visible_text
    assert "ComfyUI-VFI" in visible_text
    assert "base-helper" in visible_text


def test_environment_page_details_labels_wrap_inside_inspector() -> None:
    """Long package details should wrap instead of forcing horizontal overflow."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.select_inventory_item("package:custom-node-helper")
    deliver_queued_events(app)

    labels = (
        page.detail_title_label,
        page.detail_meta_label,
        page.detail_summary_label,
        page.detail_tags_label,
    )
    for label in labels:
        assert label.wordWrap()
        assert label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
        assert label.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
    assert (
        page.detail_scroll.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    scroll_delegate = page.detail_scroll.scrollDelagate
    assert scroll_delegate.useAni is False
    assert scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.vScrollBar.duration == 0
    assert scroll_delegate.hScrollBar.duration == 0
    assert page.detail_panel.minimumWidth() == 0
    assert page.detail_panel.width() <= (page.detail_scroll.viewport().width())
    detail_layout = page.detail_panel.layout()
    assert detail_layout is not None
    assert detail_layout.alignment() == Qt.AlignmentFlag.AlignTop
    margins = detail_layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        12,
        12,
        12,
        12,
    )
    assert detail_layout.count() == 5
    assert page.update_package_button.text() == "Plan update"
    assert page.uninstall_package_button.text() == "Plan uninstall"
    assert page.detail_actions_label.text() == ""
    assert page.detail_actions_label.isHidden()
    assert page.detail_scroll.parentWidget() is (page.detail_container)
    assert page.detail_action_bar.parentWidget() is (page.detail_container)
    action_layout = page.detail_action_bar.layout()
    assert action_layout is not None
    for index in range(action_layout.count()):
        action_item = action_layout.itemAt(index)
        assert action_item is not None
        assert action_item.spacerItem() is None
    assert (
        page.detail_claimants_label.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    assert (
        page.detail_claimants_label.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Preferred
    )
    claimant_buttons = page.detail_claimants_label.findChildren(QToolButton)
    claimant_rows = [
        button.parentWidget()
        for button in claimant_buttons
        if button.parentWidget() is not None
    ]
    claimant_child_groups = page.detail_claimants_label.findChildren(
        QWidget,
        "comfyEnvironmentClaimantChildren",
    )
    assert len(claimant_buttons) == 1
    assert len(claimant_rows) == 1
    assert len(claimant_child_groups) == 1
    claimant_row = claimant_rows[0]
    assert claimant_row is not None
    assert claimant_child_groups[0].isHidden()
    assert claimant_buttons[0].text() == "+"
    assert claimant_buttons[0].width() <= 18
    row_labels = claimant_row.findChildren(QLabel)
    dependency_label = next(
        label for label in row_labels if "base-helper" in label.text()
    )
    assert dependency_label.width() > 0
    row_layout = claimant_row.layout()
    assert row_layout is not None
    label_item = row_layout.itemAt(0)
    button_item = row_layout.itemAt(1)
    assert label_item is not None
    assert button_item is not None
    assert label_item.widget() is dependency_label
    assert button_item.widget() is claimant_buttons[0]
    claimant_buttons[0].click()
    deliver_queued_events(app)
    assert claimant_buttons[0].text() == "-"
    assert not claimant_child_groups[0].isHidden()
    assert page.detail_claimants_label.height() >= (
        page.detail_claimants_label.sizeHint().height()
    )
    child_layout = claimant_child_groups[0].layout()
    assert child_layout is not None
    assert child_layout.spacing() == 0
    assert claimant_child_groups[0].height() >= (
        claimant_child_groups[0].sizeHint().height()
    )
    child_labels = claimant_child_groups[0].findChildren(QLabel)
    assert len(child_labels) == 2
    for child_label in child_labels:
        assert not child_label.wordWrap()
        assert child_label.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert child_labels[1].geometry().top() >= child_labels[0].geometry().bottom()
    claimant_buttons[0].click()
    deliver_queued_events(app)
    assert claimant_buttons[0].text() == "+"
    assert claimant_child_groups[0].isHidden()
    claimant_labels = page.detail_claimants_label.findChildren(QLabel)
    display_text = "\n".join(QLabel.text(label) for label in claimant_labels)
    assert chr(0x200B) in display_text
    assert chr(0x200B) not in page.detail_claimants_label.text()
