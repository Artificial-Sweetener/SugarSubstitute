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

"""Verify Appearance Settings catalog controls."""

from __future__ import annotations
from typing import cast
import pytest
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    ComboBox,
    PushButton,
)
from substitute.application.appearance import (
    AppearanceRestartCoordinator,
)
from substitute.domain.appearance import (
    AppearanceAccentSource,
    AppearanceBackdropMode,
    AppearanceErrorColorMode,
    AppearanceThemeMode,
    AppearanceWarningColorMode,
)
from substitute.presentation.settings.settings_catalog_builders import (
    AppearanceSettingsContext,
    build_appearance_settings_page,
)
from substitute.presentation.settings import settings_catalog_builders
from substitute.presentation.settings.settings_segmented_card import (
    SettingsSegmentedCard,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_ICON_MAX_SIZE,
    SETTINGS_CARD_PADDING,
)
from tests.presentation.settings.appearance.support import (
    AppearanceRuntime,
    FakeColorDialog,
    RecordingAppearanceRestartCoordinator,
    activate_system_color_layout,
    assert_system_color_controls_aligned,
    label_texts,
    segmented_row_titles,
    segmented_row_with_title,
    segmented_rows,
    settings_control,
)
from tests.presentation.settings.generation.support import (
    application,
)


def test_appearance_catalog_routes_restart_required_settings_to_coordinator() -> None:
    """Appearance rows should route restart and live color settings correctly."""

    application()
    runtime = AppearanceRuntime()
    coordinator = RecordingAppearanceRestartCoordinator()
    restart_dialog_calls: list[str] = []
    page = build_appearance_settings_page(
        AppearanceSettingsContext(
            appearance_runtime=runtime,
            appearance_restart_coordinator=cast(
                AppearanceRestartCoordinator,
                coordinator,
            ),
            show_restart_requirements=lambda: restart_dialog_calls.append("show"),
        )
    )
    parent = QWidget()
    assert tuple(section.title for section in page.sections) == (
        "Theme",
        "Window",
        "System colors",
    )

    theme_row = settings_control(page, "appearance.theme.mode").factory(parent)
    theme_combo = theme_row.findChild(ComboBox)
    assert theme_combo is not None
    theme_combo.setCurrentIndex(0)

    material_row = settings_control(page, "appearance.window.material").factory(parent)
    material_combo = material_row.findChild(ComboBox)
    assert material_combo is not None
    material_combo.setCurrentIndex(1)

    colors_row = settings_control(
        page,
        "appearance.system_colors.palette",
    ).factory(parent)
    assert isinstance(colors_row, SettingsSegmentedCard)
    assert {"Warning color", "Error color"}.issubset(set(label_texts(colors_row)))
    assert [row_title for row_title in segmented_row_titles(colors_row)] == [
        "Accent color",
        "Warning color",
        "Error color",
    ]
    assert colors_row.findChild(QWidget, "AppearanceWarningColorIcon") is not None
    assert colors_row.findChild(QWidget, "AppearanceErrorColorIcon") is not None
    for row in segmented_rows(colors_row):
        row_layout = row.layout()
        assert row_layout is not None
        margins = row_layout.contentsMargins()
        assert margins.left() == SETTINGS_CARD_PADDING.left()
        assert margins.top() == SETTINGS_CARD_PADDING.top()
        assert margins.right() == SETTINGS_CARD_PADDING.right()
        assert margins.bottom() == SETTINGS_CARD_PADDING.bottom()
        assert row.visual_slot.minimumWidth() == SETTINGS_CARD_ICON_MAX_SIZE
        assert row.visual_slot.maximumWidth() == SETTINGS_CARD_ICON_MAX_SIZE
    accent_combo = colors_row.findChild(ComboBox, "AppearanceAccentSourceCombo")
    assert accent_combo is not None
    warning_mode = colors_row.findChild(ComboBox, "AppearanceWarningModeCombo")
    error_mode = colors_row.findChild(ComboBox, "AppearanceErrorModeCombo")
    warning_choose = colors_row.findChild(PushButton, "AppearanceWarningChooseButton")
    error_choose = colors_row.findChild(PushButton, "AppearanceErrorChooseButton")
    assert warning_mode is not None
    assert error_mode is not None
    assert warning_choose is not None
    assert error_choose is not None
    assert warning_mode.itemText(0) == "Derived"
    assert error_mode.itemText(0) == "Derived"
    assert warning_mode.currentData() is AppearanceWarningColorMode.DEFAULT
    assert error_mode.currentData() is AppearanceErrorColorMode.DEFAULT
    assert warning_mode.itemData(1) is AppearanceWarningColorMode.YELLOW
    assert error_mode.itemData(1) is AppearanceErrorColorMode.RED
    assert warning_choose.isEnabled() is False
    assert error_choose.isEnabled() is False
    accent_combo.setCurrentIndex(1)

    assert coordinator.saved == [
        ("theme", AppearanceThemeMode.LIGHT),
        ("backdrop", AppearanceBackdropMode.ACRYLIC),
    ]
    assert runtime.load_preferences().accent_source is AppearanceAccentSource.SYSTEM
    assert restart_dialog_calls == []

    parent.deleteLater()


def test_appearance_system_colors_open_color_pickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System color segment should persist accent, warning, and error picker choices."""

    application()
    runtime = AppearanceRuntime()
    page = build_appearance_settings_page(
        AppearanceSettingsContext(
            appearance_runtime=runtime,
            appearance_restart_coordinator=cast(
                AppearanceRestartCoordinator,
                RecordingAppearanceRestartCoordinator(),
            ),
            show_restart_requirements=None,
        )
    )
    parent = QWidget()
    selected_colors = iter(("#224466", "#FFAA00", "#CC1122"))
    monkeypatch.setattr(
        settings_catalog_builders,
        "LocalizedColorDialog",
        lambda color, title, parent: FakeColorDialog(
            color=next(selected_colors),
            title=title,
            parent=parent,
        ),
    )
    colors_row = settings_control(
        page,
        "appearance.system_colors.palette",
    ).factory(parent)

    accent_button = colors_row.findChild(PushButton, "AppearanceAccentChooseButton")
    warning_mode = colors_row.findChild(ComboBox, "AppearanceWarningModeCombo")
    warning_button = colors_row.findChild(PushButton, "AppearanceWarningChooseButton")
    error_mode = colors_row.findChild(ComboBox, "AppearanceErrorModeCombo")
    error_button = colors_row.findChild(PushButton, "AppearanceErrorChooseButton")
    assert accent_button is not None
    assert warning_mode is not None
    assert warning_button is not None
    assert error_mode is not None
    assert error_button is not None

    assert warning_mode.itemText(0) == "Derived"
    assert error_mode.itemText(0) == "Derived"
    assert warning_mode.currentData() is AppearanceWarningColorMode.DEFAULT
    assert error_mode.currentData() is AppearanceErrorColorMode.DEFAULT
    assert warning_button.isEnabled() is False
    assert error_button.isEnabled() is False

    accent_button.click()
    warning_mode.setCurrentIndex(1)
    error_mode.setCurrentIndex(1)
    assert warning_mode.currentData() is AppearanceWarningColorMode.YELLOW
    assert error_mode.currentData() is AppearanceErrorColorMode.RED
    assert runtime.load_preferences().warning_color_mode is (
        AppearanceWarningColorMode.YELLOW
    )
    assert runtime.load_preferences().error_color_mode is AppearanceErrorColorMode.RED
    assert warning_button.isEnabled() is False
    assert error_button.isEnabled() is False

    warning_mode.setCurrentIndex(2)
    error_mode.setCurrentIndex(2)
    assert warning_mode.currentData() is AppearanceWarningColorMode.CUSTOM
    assert error_mode.currentData() is AppearanceErrorColorMode.CUSTOM
    assert warning_button.isEnabled() is True
    assert error_button.isEnabled() is True
    warning_button.click()
    error_button.click()

    preferences = runtime.load_preferences()
    assert preferences.custom_accent_color == "#224466"
    assert preferences.warning_color_mode is AppearanceWarningColorMode.CUSTOM
    assert preferences.error_color_mode is AppearanceErrorColorMode.CUSTOM
    assert preferences.custom_warning_color == "#FFAA00"
    assert preferences.custom_error_color == "#CC1122"

    warning_mode.setCurrentIndex(0)
    assert warning_mode.currentData() is AppearanceWarningColorMode.DEFAULT
    assert runtime.load_preferences().warning_color_mode is (
        AppearanceWarningColorMode.DEFAULT
    )
    assert warning_button.isEnabled() is False

    parent.deleteLater()


def test_appearance_system_colors_rows_remain_visible_after_resize() -> None:
    """System color rows should remain always-visible static card segments."""

    runtime = AppearanceRuntime()
    page = build_appearance_settings_page(
        AppearanceSettingsContext(
            appearance_runtime=runtime,
            appearance_restart_coordinator=cast(
                AppearanceRestartCoordinator,
                RecordingAppearanceRestartCoordinator(),
            ),
            show_restart_requirements=None,
        )
    )
    parent = QWidget()
    layout = QVBoxLayout(parent)
    colors_row = settings_control(
        page,
        "appearance.system_colors.palette",
    ).factory(parent)
    assert isinstance(colors_row, SettingsSegmentedCard)
    layout.addWidget(colors_row)
    parent.resize(1000, 600)
    parent.show()
    activate_system_color_layout(colors_row, parent)
    assert_system_color_controls_aligned(colors_row)

    wide_height = colors_row.height()
    parent.resize(480, 600)
    activate_system_color_layout(colors_row, parent)
    assert_system_color_controls_aligned(colors_row)

    warning_row = segmented_row_with_title(colors_row, "Warning color")
    error_row = segmented_row_with_title(colors_row, "Error color")
    assert colors_row.height() > wide_height
    assert segmented_row_titles(colors_row) == (
        "Accent color",
        "Warning color",
        "Error color",
    )
    assert warning_row.geometry().bottom() <= colors_row.height()
    assert error_row.geometry().bottom() <= colors_row.height()
    assert error_row.isVisibleTo(colors_row)

    parent.deleteLater()
