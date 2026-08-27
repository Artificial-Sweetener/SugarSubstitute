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

"""Test Comfy environment package inventory presentation."""

from __future__ import annotations


from qfluentwidgets import (  # type: ignore[import-untyped]
    ListWidget,
    SearchLineEdit,
    TableWidget,
)

from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.presentation.settings.comfy_environment_package_list import (
    PackageInventoryList,
)
from tests.presentation.settings.comfy_environment.backend import EnvironmentBackend
from tests.presentation.settings.comfy_environment.support import (
    application,
    deliver_queued_events,
    environment_page,
)


def test_environment_page_renders_package_inventory_without_synthetic_rows() -> None:
    """Settings page should expose installed packages without fake dependency rows."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)

    item_names = page.inventory_item_names()
    assert item_names == (
        "torch",
        "torchvision",
        "torchaudio",
        "triton",
        "sageattention",
        "custom-node-helper",
        "manual-tool",
    )
    assert "ComfyUI-VFI dependencies" not in item_names
    assert "PyTorch" not in item_names
    assert "more" not in page.inventory_label.text()
    assert "Python packages installed" not in page.inventory_label.text()
    package_selector_layout = page.package_selector.layout()
    assert package_selector_layout is not None
    header_item = package_selector_layout.itemAt(0)
    assert header_item is not None
    assert header_item.widget() is page.inventory_label


def test_environment_page_uses_package_browser_as_primary_surface() -> None:
    """Package inventory should use a compact selectable package browser."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)

    assert isinstance(page.inventory_filter, SearchLineEdit)
    assert isinstance(page.package_list, PackageInventoryList)
    assert isinstance(page.package_list, TableWidget)
    assert page.package_list.alternatingRowColors()
    assert page.package_list.minimumHeight() <= 140
    assert page.package_list.minimumWidth() >= 380
    assert page.package_list.maximumWidth() >= 440
    assert page.package_list.rowCount() == 7
    assert isinstance(page.planned_changes_panel.plan_list, ListWidget)
    headers = tuple(
        page.package_list.horizontalHeaderItem(column).text()
        for column in range(page.package_list.columnCount())
    )
    assert headers == ("Package", "Version", "Required by")
    assert page.package_list.item(0, 0).text() == "custom-node-helper"
    assert page.package_list.item(0, 1).text() == "1.4.0"
    assert page.package_list.item(0, 2).text() == "3"
    assert page.package_list.columnWidth(2) >= 88
    page._change_inventory_sort(0)
    deliver_queued_events(app)
    assert page.package_list.item(0, 0).text() == "custom-node-helper"
