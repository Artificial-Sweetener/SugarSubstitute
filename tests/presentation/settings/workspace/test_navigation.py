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

"""Verify Settings navigation behavior."""

from __future__ import annotations
from substitute.presentation.motion import (
    SETTINGS_NAV_INDICATOR_DURATION_MS,
)
from substitute.presentation.settings.settings_navigation import (
    SettingsNavigationDescriptor,
    SettingsNavigationPane,
)
from tests.presentation.settings.generation.support import (
    application,
)


def test_settings_navigation_emits_user_page_selection() -> None:
    """Settings navigation should expose ordered non-workflow page selection."""

    application()
    navigation = SettingsNavigationPane()
    selected: list[str] = []
    navigation.pageSelected.connect(selected.append)
    navigation.set_pages(
        (
            SettingsNavigationDescriptor("appearance", "Appearance", "Theme"),
            SettingsNavigationDescriptor(
                "prompt_editing", "Prompt Editing", "Features"
            ),
        )
    )

    navigation._on_item_activated("prompt_editing")

    assert navigation.page_ids() == ("appearance", "prompt_editing")
    assert navigation.selected_page_id() == "prompt_editing"
    assert selected == ["prompt_editing"]


def test_settings_navigation_slides_indicator_between_pages() -> None:
    """Settings navigation should animate the selected-page accent rail."""

    app = application()
    navigation = SettingsNavigationPane()
    navigation.set_pages(
        (
            SettingsNavigationDescriptor("appearance", "Appearance", "Theme"),
            SettingsNavigationDescriptor(
                "prompt_editing", "Prompt Editing", "Features"
            ),
        )
    )
    navigation.show()
    app.processEvents()
    navigation.select_page("appearance", animated=False)
    app.processEvents()
    initial_y = navigation.indicatorY

    navigation.select_page("prompt_editing", animated=True)

    assert (
        navigation._indicator_animation.duration() == SETTINGS_NAV_INDICATOR_DURATION_MS
    )
    assert navigation._indicator_animation.endValue() != initial_y
