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

"""Contract tests for prompt editor Settings icon selection."""

from __future__ import annotations

from substitute.application.prompt_editor import prompt_feature_definitions
from substitute.domain.prompt.features import PromptEditorFeature
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.prompt_editor_icons import (
    PROMPT_DANBOORU_BACKGROUND_REFRESH_SETTINGS_ICON,
    PROMPT_DANBOORU_CACHE_MAINTENANCE_SETTINGS_ICON,
    PROMPT_DANBOORU_CACHE_USAGE_SETTINGS_ICON,
    PROMPT_DANBOORU_IMAGES_SETTINGS_ICON,
    PROMPT_DANBOORU_RATINGS_SETTINGS_ICON,
    PROMPT_FEATURE_SETTINGS_ICONS,
    PROMPT_WHEEL_ADJUSTMENT_SETTINGS_ICON,
    PROMPT_WILDCARD_MANAGEMENT_SETTINGS_ICON,
    PROMPT_WILDCARD_RESOLUTION_SETTINGS_ICON,
    prompt_feature_settings_icon,
)


def test_prompt_feature_settings_icons_cover_every_feature() -> None:
    """Every prompt feature should have a deliberate Settings row icon."""

    defined_features = {
        definition.feature for definition in prompt_feature_definitions()
    }

    assert set(PROMPT_FEATURE_SETTINGS_ICONS) == defined_features


def test_prompt_feature_settings_icons_match_feature_meaning() -> None:
    """Prompt feature rows should use the selected expressive app icons."""

    expected = {
        PromptEditorFeature.EMPHASIS: AppIcon.TEXT_EFFECTS_SPARKLE_20_REGULAR,
        PromptEditorFeature.DANBOORU_URL_IMPORT: AppIcon.LINK_EDIT_20_REGULAR,
        PromptEditorFeature.DANBOORU_WIKI_LOOKUP: AppIcon.BOOK_SEARCH_20_REGULAR,
        PromptEditorFeature.WILDCARD_SYNTAX: AppIcon.BRACES_VARIABLE_20_REGULAR,
        PromptEditorFeature.WILDCARD_AUTOCOMPLETE: (
            AppIcon.TEXT_BULLET_LIST_SQUARE_SPARKLE_20_REGULAR
        ),
        PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT: AppIcon.TEXT_FIELD_20_REGULAR,
        PromptEditorFeature.LORA_SYNTAX: AppIcon.TAG_MULTIPLE_20_REGULAR,
        PromptEditorFeature.LORA_AUTOCOMPLETE: AppIcon.TAG_SEARCH_20_REGULAR,
        PromptEditorFeature.LORA_PICKER: AppIcon.PANEL_RIGHT_CURSOR_20_REGULAR,
        PromptEditorFeature.LORA_TRIGGER_WORDS: AppIcon.TEXT_ASTERISK_20_REGULAR,
        PromptEditorFeature.SEGMENT_REORDER: AppIcon.REORDER_20_REGULAR,
        PromptEditorFeature.SPELLCHECK: AppIcon.TEXT_GRAMMAR_CHECKMARK_20_REGULAR,
        PromptEditorFeature.DUPLICATE_SEGMENT_DIAGNOSTICS: (
            AppIcon.TEXT_BULLET_LIST_SQUARE_WARNING_20_REGULAR
        ),
    }

    for feature, icon in expected.items():
        assert prompt_feature_settings_icon(feature) is icon


def test_prompt_non_feature_settings_icons_are_deliberate() -> None:
    """Prompt-specific Settings rows outside feature toggles should avoid fallbacks."""

    assert PROMPT_WHEEL_ADJUSTMENT_SETTINGS_ICON is AppIcon.CURSOR_HOVER_20_REGULAR
    assert PROMPT_WILDCARD_RESOLUTION_SETTINGS_ICON is AppIcon.WAND_20_REGULAR
    assert PROMPT_WILDCARD_MANAGEMENT_SETTINGS_ICON is AppIcon.FOLDER_OPEN_20_REGULAR
    assert PROMPT_DANBOORU_IMAGES_SETTINGS_ICON is AppIcon.IMAGE_MULTIPLE_20_REGULAR
    assert PROMPT_DANBOORU_RATINGS_SETTINGS_ICON is AppIcon.RATING_MATURE_20_REGULAR
    assert (
        PROMPT_DANBOORU_BACKGROUND_REFRESH_SETTINGS_ICON
        is AppIcon.BOOK_ARROW_CLOCKWISE_20_REGULAR
    )
    assert (
        PROMPT_DANBOORU_CACHE_USAGE_SETTINGS_ICON is AppIcon.DATABASE_SEARCH_20_REGULAR
    )
    assert PROMPT_DANBOORU_CACHE_MAINTENANCE_SETTINGS_ICON is AppIcon.BROOM_20_REGULAR
