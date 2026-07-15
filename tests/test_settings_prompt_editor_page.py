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

"""Widget contract tests for prompt editor Settings page."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import SwitchButton  # type: ignore[import-untyped]

from substitute.application.prompt_editor import (
    PromptEditorPreferenceService,
    prompt_feature_definitions,
)
from substitute.application.prompt_wildcards import PromptWildcardPreferenceService
from substitute.domain.prompt import PromptEditorFeature, PromptWheelAdjustmentMode
from substitute.infrastructure.persistence import (
    FilePromptEditorPreferenceRepository,
    FilePromptWildcardPreferenceRepository,
)
from substitute.presentation.settings.prompt_editor_page import PromptEditorSettingsPage
from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_MIN_HEIGHT,
    InteractiveSettingsCard,
)
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_SPACING,
    settings_card_overlay_color,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_prompt_editor_page_exposes_registered_features(tmp_path: Path) -> None:
    """Prompt editor settings should expose registered feature preferences."""

    app = _app()
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(preference_service=service)

    app.processEvents()

    assert page.feature_labels() == tuple(
        definition.label
        for definition in prompt_feature_definitions()
        if definition.feature
        not in {
            PromptEditorFeature.DANBOORU_URL_IMPORT,
            PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
        }
    )
    assert len(page._feature_switches) == len(page.feature_labels())
    assert len(page.findChildren(SwitchButton)) == len(page.feature_labels()) + 1
    assert "Autocomplete ghost text" in page.feature_labels()
    assert "LoRA syntax" in page.feature_labels()
    assert "LoRA autocomplete" in page.feature_labels()


def test_prompt_editor_page_exposes_wheel_hover_adjustment_switch(
    tmp_path: Path,
) -> None:
    """Prompt editor settings should expose the wheel interaction policy."""

    app = _app()
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(preference_service=service)

    app.processEvents()

    assert page._wheel_hover_adjust_row is not None
    assert page._wheel_hover_adjust_row.title_label.text() == "Wheel adjust after hover"
    assert page.is_wheel_hover_adjustment_enabled() is True


def test_prompt_editor_page_hides_danbooru_feature_rows(tmp_path: Path) -> None:
    """Prompt editor settings should leave Danbooru controls to the dedicated page."""

    app = _app()
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(preference_service=service)

    app.processEvents()

    assert "Danbooru URL import" not in page.feature_labels()
    assert "Danbooru wiki lookup" not in page.feature_labels()
    assert PromptEditorFeature.DANBOORU_URL_IMPORT not in page._feature_rows
    assert PromptEditorFeature.DANBOORU_WIKI_LOOKUP not in page._feature_rows


def test_prompt_editor_page_toggle_persists_preference_and_notifies(
    tmp_path: Path,
) -> None:
    """Toggling one prompt feature should persist and notify the shell callback."""

    app = _app()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.set_feature_allowed(PromptEditorFeature.LORA_PICKER, False)
    app.processEvents()

    assert (
        service.load_preferences().user_allows(PromptEditorFeature.LORA_PICKER) is False
    )
    assert calls == ["changed"]


def test_prompt_editor_page_toggles_ghost_text_preference(
    tmp_path: Path,
) -> None:
    """Toggling ghost text should persist through the standard feature path."""

    app = _app()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.set_feature_allowed(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT, False)
    app.processEvents()

    assert (
        service.load_preferences().user_allows(
            PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT
        )
        is False
    )
    assert page.is_feature_allowed(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT) is False
    assert calls == ["changed"]


def test_prompt_editor_page_persists_wheel_hover_adjustment_mode_and_notifies(
    tmp_path: Path,
) -> None:
    """Toggling wheel hover adjustment should persist and notify the shell callback."""

    app = _app()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.set_wheel_hover_adjustment_enabled(False)
    app.processEvents()

    assert (
        service.load_preferences().wheel_adjustment_mode
        is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    assert page.is_wheel_hover_adjustment_enabled() is False
    assert calls == ["changed"]


def test_prompt_editor_page_row_click_toggles_preference_and_notifies(
    tmp_path: Path,
) -> None:
    """Clicking a prompt feature row should toggle the row switch."""

    app = _app()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.show()
    app.processEvents()

    QTest.mouseClick(
        page._feature_rows[PromptEditorFeature.LORA_PICKER],
        Qt.MouseButton.LeftButton,
    )
    app.processEvents()

    assert (
        service.load_preferences().user_allows(PromptEditorFeature.LORA_PICKER) is False
    )
    assert page.is_feature_allowed(PromptEditorFeature.LORA_PICKER) is False
    assert calls == ["changed"]


def test_prompt_editor_page_row_click_toggles_ghost_text(
    tmp_path: Path,
) -> None:
    """Clicking the ghost text row should toggle and notify like other features."""

    app = _app()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.show()
    app.processEvents()

    QTest.mouseClick(
        page._feature_rows[PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT],
        Qt.MouseButton.LeftButton,
    )
    app.processEvents()

    assert (
        service.load_preferences().user_allows(
            PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT
        )
        is False
    )
    assert page.is_feature_allowed(PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT) is False
    assert calls == ["changed"]


def test_prompt_editor_page_row_click_toggles_wheel_hover_adjustment(
    tmp_path: Path,
) -> None:
    """Clicking the wheel adjustment row should toggle the interaction switch."""

    app = _app()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.show()
    app.processEvents()
    assert page._wheel_hover_adjust_row is not None

    QTest.mouseClick(page._wheel_hover_adjust_row, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert (
        service.load_preferences().wheel_adjustment_mode
        is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )
    assert page.is_wheel_hover_adjustment_enabled() is False
    assert calls == ["changed"]


def test_prompt_editor_page_reload_reflects_wheel_adjustment_mode(
    tmp_path: Path,
) -> None:
    """Reload should sync wheel adjustment switch state from persisted preferences."""

    app = _app()
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(preference_service=service)
    service.set_wheel_adjustment_mode(PromptWheelAdjustmentMode.FOCUS_REQUIRED)

    page.reload()
    app.processEvents()

    assert page.is_wheel_hover_adjustment_enabled() is False


def test_prompt_editor_page_switch_click_toggles_without_row_interference(
    tmp_path: Path,
) -> None:
    """Clicking a prompt feature switch should keep the switch in control."""

    app = _app()
    calls: list[str] = []
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(
        preference_service=service,
        preferences_changed=lambda: calls.append("changed"),
    )

    page.show()
    app.processEvents()

    switch = page._feature_switches[PromptEditorFeature.LORA_PICKER]
    QTest.mouseClick(switch.indicator, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert (
        service.load_preferences().user_allows(PromptEditorFeature.LORA_PICKER) is False
    )
    assert page.is_feature_allowed(PromptEditorFeature.LORA_PICKER) is False
    assert calls == ["changed"]


def test_prompt_editor_page_uses_grouped_settings_cards(tmp_path: Path) -> None:
    """Prompt editor rows should use grouped interactive Settings cards."""

    app = _app()
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )
    page = PromptEditorSettingsPage(preference_service=service)

    app.processEvents()

    row = page._feature_rows[PromptEditorFeature.LORA_PICKER]
    row_parent = row.parentWidget()
    assert row_parent is not None
    parent_layout = row_parent.layout()
    groups = page.findChildren(SettingsCardGroup)

    assert isinstance(row, InteractiveSettingsCard)
    assert row.minimumHeight() == SETTINGS_CARD_MIN_HEIGHT
    assert tuple(group.title_label.text() for group in groups) == (
        "Interaction",
        "Editor features",
    )
    assert parent_layout is not None
    assert parent_layout.spacing() == SETTINGS_CARD_GROUP_SPACING


def test_prompt_editor_page_updates_wildcard_preference_service(
    tmp_path: Path,
) -> None:
    """Wildcard Settings controls should persist through the wildcard service."""

    app = _app()
    editor_service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path / "editor")
    )
    wildcard_service = PromptWildcardPreferenceService(
        FilePromptWildcardPreferenceRepository(tmp_path / "wildcards")
    )
    page = PromptEditorSettingsPage(
        preference_service=editor_service,
        wildcard_preference_service=wildcard_service,
    )

    page.set_wildcard_resolution_enabled(False)
    app.processEvents()

    preferences = wildcard_service.load_preferences()
    assert preferences.resolve_on_generation is False


def test_prompt_editor_page_invokes_wildcard_management_opener(
    tmp_path: Path,
) -> None:
    """Wildcard Settings management should call the supplied reusable opener."""

    app = _app()
    editor_service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path / "editor")
    )
    calls: list[QWidget | None] = []
    page = PromptEditorSettingsPage(
        preference_service=editor_service,
        open_wildcard_management_modal=lambda parent: calls.append(parent),
    )

    page._open_wildcard_management()
    app.processEvents()

    assert calls == [page]


def test_prompt_editor_rows_use_windows_list_item_state_colors() -> None:
    """Prompt row hover and press colors should match Windows SDK list resources."""

    assert (
        settings_card_overlay_color(
            pressed=False,
            hovered=True,
        ).alpha()
        == 0x19
    )
    assert (
        settings_card_overlay_color(
            pressed=True,
            hovered=True,
        ).alpha()
        == 0x33
    )


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])
