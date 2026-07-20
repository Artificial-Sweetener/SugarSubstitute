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

"""Own the live application-language control in Settings."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon, InfoBar  # type: ignore[import-untyped]

from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsSectionEntry,
)
from substitute.presentation.settings.settings_control_group import (
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_row_factories import (
    build_settings_icon_widget,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import TranslationManager
from sugarsubstitute_shared.presentation.localization.language_selector import (
    ManifestLanguageComboBox,
)


class LanguageSettingsCard(SettingsCard):
    """Select and atomically apply one manifest-backed application language."""

    def __init__(
        self,
        manager: TranslationManager,
        *,
        failure_presenter: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the selector from the process-owned translation manager."""

        self._failure_presenter = failure_presenter
        self.language_combo = ManifestLanguageComboBox(
            manager,
            failure_presenter=self._show_failure,
            parent=parent,
        )
        configure_settings_field_width(self.language_combo, preferred_width=210)
        super().__init__(
            visual_widget=build_settings_icon_widget(FluentIcon.LANGUAGE, parent),
            title=app_text("Language"),
            description=app_text(
                "Choose the language used by SugarSubstitute. Changes apply "
                "immediately."
            ),
            trailing_widget=self.language_combo,
            reserve_visual_space=True,
            wrap_threshold=640,
            parent=parent,
        )

    def _show_failure(self, title: str, content: str) -> None:
        """Show localized non-blocking feedback for a rejected locale switch."""

        if self._failure_presenter is not None:
            self._failure_presenter(title, content)
            return
        InfoBar.error(
            title=title,
            content=content,
            duration=5000,
            parent=self.window(),
        )


def build_language_settings_section(
    manager: TranslationManager,
) -> SettingsSectionEntry:
    """Build the focused language section contributed to Appearance Settings."""

    return SettingsSectionEntry(
        section_id="appearance.language",
        title=app_text("Language and region"),
        subtitle=app_text("Choose how SugarSubstitute presents text."),
        order=-100,
        controls=(
            SettingsControlEntry(
                setting_id="appearance.language.application_language",
                title=app_text("Language"),
                description=app_text(
                    "Choose the language used by SugarSubstitute. Changes apply "
                    "immediately."
                ),
                keywords=("language", "locale", "region", "中文", "日本語"),
                order=0,
                factory=lambda parent: LanguageSettingsCard(manager, parent=parent),
            ),
        ),
    )


__all__ = [
    "LanguageSettingsCard",
    "build_language_settings_section",
]
