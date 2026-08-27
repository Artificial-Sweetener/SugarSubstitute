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

"""Test Comfy environment package search and sorting."""

from __future__ import annotations


from PySide6.QtWidgets import QLabel

from substitute.application.comfy_environment import ComfyEnvironmentService
from tests.presentation.settings.comfy_environment.backend import EnvironmentBackend
from tests.presentation.settings.comfy_environment.backend_variants import (
    SearchSortEnvironmentBackend,
)
from tests.presentation.settings.comfy_environment.support import (
    application,
    deliver_queued_events,
    environment_page,
)


def test_environment_page_filter_uses_package_metadata() -> None:
    """Filtering should search package names, claimants, summaries, and tags."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)
    page.inventory_filter.setText("ComfyUI-VFI")
    deliver_queued_events(app)

    assert page.visible_inventory_item_names() == ("custom-node-helper",)
    assert "ComfyUI-VFI" in page.detail_text()

    page.inventory_filter.setText("requirements.txt")
    deliver_queued_events(app)

    assert page.visible_inventory_item_names() == ()


def test_environment_page_search_ranks_name_matches_and_supports_sorting() -> None:
    """Search should favor package names while sort state remains available."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(
            SearchSortEnvironmentBackend()
        ),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)

    assert page.visible_inventory_item_names()[0] == "beta-package"
    assert page.detail_title_label.text() == "beta-package  1.0.0"
    raw_title_text = QLabel.text(page.detail_title_label)
    assert '<span style="font-size: 12px; font-weight: 400;">' in raw_title_text
    assert "1.0.0" in raw_title_text.replace(chr(0x200B), "")
    assert "3 extension claimants" in page.detail_meta_label.text()

    page.inventory_filter.setText("helper")
    deliver_queued_events(app)

    assert page.visible_inventory_item_names() == (
        "alpha-helper",
        "beta-package",
    )
    assert page.package_list.currentRow() == 0
    assert page.detail_title_label.text() == "alpha-helper  0.1.0"
    assert page.package_list.rowCount() == 2

    page.inventory_filter.clear()
    page._change_inventory_sort(0)
    deliver_queued_events(app)

    assert page.visible_inventory_item_names() == (
        "alpha-helper",
        "beta-package",
        "gamma-tool",
    )

    page._change_inventory_sort(2)
    deliver_queued_events(app)

    assert page.visible_inventory_item_names()[0] == "beta-package"


def test_environment_package_list_skips_identical_row_rebuilds() -> None:
    """Inventory rendering should not rebuild table rows when row data is unchanged."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(
            SearchSortEnvironmentBackend()
        ),
        open_reconfigure_window=lambda: object(),
    )

    deliver_queued_events(app)

    initial_generation = page.package_list.render_generation()
    page._render_filtered_packages()

    assert page.package_list.render_generation() == initial_generation

    page.inventory_filter.setText("helper")
    deliver_queued_events(app)
    filtered_generation = page.package_list.render_generation()

    page._render_filtered_packages(select_first=True)

    assert page.package_list.render_generation() == filtered_generation
