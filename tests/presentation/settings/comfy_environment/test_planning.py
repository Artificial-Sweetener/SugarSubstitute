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

"""Test Comfy environment maintenance planning interactions."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

from PySide6.QtCore import QEvent, QTranslator, Qt
from PySide6.QtWidgets import QSizePolicy

from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.domain.comfy_environment import ComfyMaintenancePlanIssue
from substitute.presentation.settings.planned_changes_panel import (
    PlanQueueItemWidget,
    PlannedChangesPanel,
)
from tests.presentation.settings.comfy_environment.backend import EnvironmentBackend
from tests.presentation.settings.comfy_environment.builders import (
    maintenance_plan,
    plan_item,
)
from tests.presentation.settings.comfy_environment.support import (
    application,
    deliver_queued_events,
    environment_page,
)


def test_environment_page_requests_mouse_driven_operation_plan() -> None:
    """Package actions should add visible items to the planned changes queue."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.select_inventory_item("package:torch")
    page.update_package_button.click()
    deliver_queued_events(app)

    detail_text = page.detail_text()
    assert "required compatibility follow-ups" in detail_text
    assert page.planned_changes_panel.plan_list.count() == 3
    parent_row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(0)
        ),
    )
    triton_row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(1)
        ),
    )
    sage_row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(2)
        ),
    )
    assert parent_row.title_label.text() == "Update PyTorch runtime"
    assert not hasattr(parent_row, "drag_handle")
    assert triton_row.title_label.text() == "Reinstall Triton"
    assert sage_row.title_label.text() == "Reinstall SageAttention"
    assert parent_row.target_label.text() == "torch, torchvision, torchaudio"
    assert "triton from triton-windows" in triton_row.target_label.text()
    assert sage_row.target_label.text() == ""
    assert sage_row.target_label.isHidden()
    assert triton_row.height() == 40
    assert sage_row.height() == 40
    assert triton_row.move_down_button.isHidden()
    assert triton_row.remove_button.isHidden()
    assert triton_row.badges == ()
    assert sage_row.badges == ()
    assert not hasattr(page.planned_changes_panel, "count_badge")
    assert page.planned_changes_panel.plan_list.item(0).sizeHint().height() == 44
    assert page.planned_changes_panel.plan_list.item(1).sizeHint().height() == 40
    assert page.planned_changes_panel.plan_list.spacing() == 0
    assert page.planned_changes_panel.item_ids() == (
        "plan-item-1",
        "plan-item-2",
        "plan-item-3",
    )
    page.planned_changes_panel.plan_list.setCurrentRow(0)
    deliver_queued_events(app)
    assert page.planned_changes_panel.summary_label.text() == (
        "3 changes planned; blocked until issues are resolved."
    )
    assert page.planned_changes_panel.validation_label.text() == ""
    assert not page.planned_changes_panel.summary_label.isHidden()
    assert page.planned_changes_panel.validation_label.isHidden()
    assert page.planned_changes_panel.selected_detail_label.isHidden()
    assert not page.planned_changes_panel.apply_button.isEnabled()


def test_plan_badges_retranslate_and_resize_without_recreating_row() -> None:
    """Keep compact plan state badges current across live locale changes."""

    app = application()
    resource_root = (
        Path(__file__).resolve().parents[4]
        / "substitute"
        / "presentation"
        / "resources"
        / "i18n"
    )
    chinese = QTranslator()
    japanese = QTranslator()
    assert chinese.load(str(resource_root / "sugarsubstitute_zh_CN.qm"))
    assert japanese.load(str(resource_root / "sugarsubstitute_ja_JP.qm"))
    assert app.installTranslator(chinese)
    base_item = plan_item(
        item_id="required",
        title="Required runtime repair",
        operation="install",
        affected=("runtime",),
        install_requirements=("runtime-wheel",),
        generated=True,
    )
    item = replace(
        base_item,
        blockers=(
            ComfyMaintenancePlanIssue(
                code="blocked",
                message="Backend-owned blocker",
                item_id=base_item.item_id,
            ),
        ),
    )
    row = PlanQueueItemWidget(item)
    panel = PlannedChangesPanel()
    panel.render_plan(maintenance_plan(items=(base_item,), blocked=False))
    try:
        assert [badge.text() for badge in row.badges] == ["必需", "受阻"]
        assert row.badges[0].toolTip() == "必需操作"
        assert row.target_label.text() == "runtime-wheel 中的 runtime"
        assert panel.summary_label.text() == "计划进行 1 项更改"
        assert all(
            badge.width() >= badge.fontMetrics().horizontalAdvance(badge.text()) + 18
            for badge in row.badges
        )

        assert app.removeTranslator(chinese)
        assert app.installTranslator(japanese)
        for badge in row.badges:
            app.sendEvent(badge, QEvent(QEvent.Type.LanguageChange))

        assert [badge.text() for badge in row.badges] == ["必須", "ブロック中"]
        assert row.badges[0].toolTip() == "必要な操作"
        app.sendEvent(row, QEvent(QEvent.Type.LanguageChange))
        assert row.target_label.text() == "runtime-wheel の runtime"
        app.sendEvent(panel, QEvent(QEvent.Type.LanguageChange))
        assert panel.summary_label.text() == "予定されている変更：1 件"
        assert all(
            badge.width() >= badge.fontMetrics().horizontalAdvance(badge.text()) + 18
            for badge in row.badges
        )
    finally:
        app.removeTranslator(japanese)
        app.removeTranslator(chinese)
        row.close()
        panel.close()


def test_environment_page_adds_uninstall_and_clears_plan() -> None:
    """Package uninstall actions should be queued and clearable."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.select_inventory_item("package:manual-tool")
    page.uninstall_package_button.click()
    deliver_queued_events(app)

    row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(0)
        ),
    )
    assert row.title_label.text() == "Uninstall manual-tool"
    assert row.target_label.text() == ""
    assert row.target_label.isHidden()
    assert page.planned_changes_panel.selected_detail_label.isHidden()

    page.planned_changes_panel.clear_button.click()
    deliver_queued_events(app)

    assert page.planned_changes_panel.plan_list.count() == 0
    assert page.planned_changes_panel.plan_list.isHidden()
    assert not page.planned_changes_panel.empty_label.isHidden()
    assert page.planned_changes_panel.item_ids() == ()
    assert page.planned_changes_panel.empty_label.text() == ("No changes planned.")
    assert page.planned_changes_panel.empty_label.alignment() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    assert (
        page.planned_changes_panel.empty_label.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Expanding
    )
    assert (
        page.planned_changes_panel.empty_label.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Fixed
    )
    assert page.planned_changes_panel.summary_label.text() == ""


def test_environment_page_plan_queue_removes_and_reorders_items() -> None:
    """Planned changes should support removal and backend-normalized ordering."""

    app = application()
    backend = EnvironmentBackend()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(backend),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.select_inventory_item("package:torch")
    page.update_package_button.click()
    deliver_queued_events(app)
    page.select_inventory_item("package:manual-tool")
    page.uninstall_package_button.click()
    deliver_queued_events(app)

    parent_row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(0)
        ),
    )
    parent_row.move_down_button.click()
    deliver_queued_events(app)

    assert backend.reorder_requests == [
        (2, ("plan-item-4", "plan-item-1", "plan-item-2", "plan-item-3"))
    ]
    assert page.planned_changes_panel.item_ids() == (
        "plan-item-4",
        "plan-item-1",
        "plan-item-2",
        "plan-item-3",
    )

    page.planned_changes_panel.reorder_requested.emit(
        ("plan-item-2", "plan-item-1", "plan-item-3", "plan-item-4")
    )
    deliver_queued_events(app)

    assert backend.reorder_requests == [
        (2, ("plan-item-4", "plan-item-1", "plan-item-2", "plan-item-3")),
        (3, ("plan-item-2", "plan-item-1", "plan-item-3", "plan-item-4")),
    ]
    assert page.planned_changes_panel.item_ids()[0] == "plan-item-1"
    assert "Order adjusted" in page.detail_text()

    page.planned_changes_panel.remove_item_requested.emit("plan-item-1")
    deliver_queued_events(app)

    assert page.planned_changes_panel.plan_list.count() == 1
    assert not page.planned_changes_panel.plan_list.isHidden()
    assert page.planned_changes_panel.empty_label.isHidden()
    assert page.planned_changes_panel.item_ids() == ("plan-item-4",)


def test_environment_page_disables_actions_when_planning_is_unavailable() -> None:
    """Package action buttons should reflect backend planning capability."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(
            EnvironmentBackend(planning_supported=False)
        ),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.select_inventory_item("package:torch")

    assert not page.update_package_button.isEnabled()
    assert not page.uninstall_package_button.isEnabled()
    assert "Operation planning is not available" in page.detail_text()
