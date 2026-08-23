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

"""Test Comfy environment responsive layout and theme behavior."""

from __future__ import annotations


from qfluentwidgets import (  # type: ignore[import-untyped]
    Theme,
    setTheme,
)

from substitute.application.comfy_environment import ComfyEnvironmentService
from substitute.presentation.settings.settings_style import settings_card_border_color
from tests.presentation.settings.comfy_environment.backend import EnvironmentBackend
from tests.presentation.settings.comfy_environment.support import (
    application,
    css_color,
    deliver_queued_events,
    environment_page,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_environment_page_workbench_layout_does_not_overlap_at_minimum_width() -> None:
    """The package browser, detail inspector, and review shelf should not overlap."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )
    page.resize(1100, 520)
    page.show()

    deliver_queued_events(app)

    list_geometry = page.package_list.geometry()
    search_geometry = page.inventory_filter.geometry()
    selector_geometry = page.package_selector.geometry()
    detail_geometry = page.detail_container.geometry()
    plan_geometry = page.planned_changes_panel.geometry()
    assert selector_geometry.right() < detail_geometry.left()
    assert plan_geometry.top() > detail_geometry.bottom()
    assert detail_geometry.left() - selector_geometry.right() >= 8
    assert plan_geometry.top() - detail_geometry.bottom() >= 8
    assert search_geometry.width() <= list_geometry.width()
    assert detail_geometry.height() == selector_geometry.height()
    assert page.detail_action_bar.geometry().top() >= (
        page.detail_scroll.geometry().bottom()
    )
    assert page.restart_button.parentWidget() is not page
    assert "background: transparent" in page.inventory_panel.styleSheet()

    page.close()
    destroy_qt_object(page)


def test_environment_page_adapts_inventory_layout_by_width() -> None:
    """Environment inventory should change layout modes instead of clipping."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )
    page.show()

    page.resize(960, 620)
    deliver_queued_events(app)
    assert page.layout_mode() == "wide"
    assert (
        page.package_selector.geometry().right()
        < page.detail_container.geometry().left()
    )
    assert (
        page.planned_changes_panel.geometry().top()
        > page.detail_container.geometry().bottom()
    )

    page.resize(700, 720)
    deliver_queued_events(app)
    assert page.layout_mode() == "medium"
    assert (
        page.package_selector.geometry().right()
        < page.detail_container.geometry().left()
    )
    assert (
        page.planned_changes_panel.geometry().top()
        > page.detail_container.geometry().bottom()
    )

    page.resize(500, 860)
    deliver_queued_events(app)
    assert page.layout_mode() == "narrow"
    assert (
        page.detail_container.geometry().top()
        > page.package_selector.geometry().bottom()
    )
    assert page.package_selector.geometry().width() >= (
        page.inventory_body.geometry().width() - 4
    )
    assert (
        page.planned_changes_panel.geometry().top()
        > page.detail_container.geometry().bottom()
    )
    assert page.minimumSizeHint().width() <= page.width()

    page.resize(360, 920)
    deliver_queued_events(app)
    page._sync_layout_mode(360)
    assert page.layout_mode() == "compact"
    assert page.package_selector.minimumWidth() == 0
    assert page.package_list.minimumWidth() == 0
    assert page.detail_container.minimumWidth() == 0
    assert page.planned_changes_panel.minimumWidth() == 0

    page.close()
    destroy_qt_object(page)


def test_environment_page_keeps_planned_changes_accessible_when_narrow() -> None:
    """Planned changes should remain visible after narrow-mode reflow."""

    app = application()
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: object(),
    )
    page.resize(500, 860)
    page.show()
    deliver_queued_events(app)

    page.select_inventory_item("package:torch")
    page.update_package_button.click()
    deliver_queued_events(app)

    assert page.layout_mode() == "narrow"
    assert page.planned_changes_panel.isVisible()
    assert page.planned_changes_panel.plan_list.count() == 3
    assert (
        page.planned_changes_panel.geometry().top()
        > page.detail_container.geometry().bottom()
    )

    page.close()
    destroy_qt_object(page)


def test_environment_page_stylesheet_refreshes_after_qfluent_theme_switch() -> None:
    """Comfy environment custom panel styles should refresh from QFluent theme changes."""

    app = application()
    setTheme(Theme.DARK)
    page = environment_page(
        comfy_environment_service=ComfyEnvironmentService(EnvironmentBackend()),
        open_reconfigure_window=lambda: None,
    )
    try:
        dark_style = page.styleSheet()

        setTheme(Theme.LIGHT)
        app.processEvents()

        assert page.styleSheet() != dark_style
        assert css_color(settings_card_border_color()) in page.styleSheet()
    finally:
        page.close()
        destroy_qt_object(page)
