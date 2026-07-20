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

"""Build generated-output Settings rows around one preference owner."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import translate_application_text

from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.localization import LocalizedPushButton

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]

from substitute.application.generation import (
    OutputPersistenceMode,
    OutputPreferenceService,
    OutputPreferences,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.path_pattern_token_autocomplete import (
    PathPatternTokenAutocomplete,
    PathPatternTokenSuggestion,
)
from substitute.presentation.settings.jpeg_companion_settings import (
    JpegCompanionSettingsControl,
)
from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_row_factories import (
    build_combo_settings_row,
    build_settings_icon_widget,
)


class GenerationOutputSettingsRows:
    """Own output preference controls and their persistence bindings."""

    def __init__(self, service: OutputPreferenceService) -> None:
        """Store the authoritative output preference service."""

        self._service = service

    def folder(self, parent: QWidget) -> SettingsCard:
        """Create the generated output folder row."""

        service = self._service
        preferences = service.load_preferences()
        default_root = service.effective_output_root(service.default_preferences())
        edit = LineEdit(parent)
        edit.setObjectName("OutputRootEdit")
        configure_settings_field_width(edit, preferred_width=420)
        edit.setText(str(preferences.organization.output_root or default_root))
        browse_button = LocalizedPushButton(app_text("Browse"), parent)
        reset_button = LocalizedPushButton(app_text("Default"), parent)

        def current_preferences() -> OutputPreferences:
            """Return current aggregate with the edited root applied."""

            root_text = edit.text().strip()
            loaded = service.load_preferences()
            return replace(
                loaded,
                organization=replace(
                    loaded.organization,
                    output_root=(
                        None
                        if not root_text or Path(root_text) == default_root
                        else Path(root_text)
                    ),
                ),
            )

        def save_preferences() -> None:
            """Persist the edited output root."""

            service.save_preferences(current_preferences())

        def browse_output_folder() -> None:
            """Choose and persist an output root."""

            selected = QFileDialog.getExistingDirectory(
                parent,
                translate_application_text("Choose output folder"),
                edit.text().strip() or str(default_root),
            )
            if not selected:
                return
            edit.setText(selected)
            save_preferences()

        def reset_output_folder() -> None:
            """Restore default-root semantics without persisting its concrete path."""

            edit.setText(str(default_root))
            loaded = service.load_preferences()
            service.save_preferences(
                replace(
                    loaded,
                    organization=replace(loaded.organization, output_root=None),
                )
            )

        reset_button.clicked.connect(reset_output_folder)
        browse_button.clicked.connect(browse_output_folder)
        edit.editingFinished.connect(save_preferences)
        return SettingsCard(
            visual_widget=build_settings_icon_widget(
                AppIcon.SAVE_IMAGE_20_REGULAR, parent
            ),
            title=app_text("Output folder"),
            description=app_text("Choose where generated images are saved."),
            trailing_widget=SettingsControlGroup(
                edit,
                browse_button,
                reset_button,
                spacing=6,
                parent=parent,
            ),
            reserve_visual_space=True,
            wrap_threshold=720,
            parent=parent,
        )

    def pattern(self, parent: QWidget) -> SettingsCard:
        """Create the generated output path pattern row."""

        service = self._service
        edit = LineEdit(parent)
        edit.setObjectName("OutputPathPatternEdit")
        configure_settings_field_width(edit, preferred_width=360)
        edit.setText(service.load_preferences().organization.path_pattern)
        PathPatternTokenAutocomplete(
            edit,
            tuple(
                PathPatternTokenSuggestion(
                    token=token.placeholder,
                    description=token.description,
                )
                for token in service.supported_token_descriptions()
            ),
        )

        def save_preferences() -> None:
            """Persist the edited path pattern."""

            loaded = service.load_preferences()
            service.save_preferences(
                replace(
                    loaded,
                    organization=replace(
                        loaded.organization,
                        path_pattern=edit.text(),
                    ),
                )
            )

        edit.editingFinished.connect(save_preferences)
        return SettingsCard(
            visual_widget=build_settings_icon_widget(
                AppIcon.DOCUMENT_TEXT_20_REGULAR, parent
            ),
            title=app_text("Output pattern"),
            description=app_text(
                "Compose relative folders and filename without the .png extension."
            ),
            trailing_widget=SettingsControlGroup(edit, parent=parent),
            reserve_visual_space=True,
            wrap_threshold=640,
            parent=parent,
        )

    def preview(self, parent: QWidget) -> SettingsCard:
        """Create the generated output preview row."""

        service = self._service
        edit = LineEdit(parent)
        edit.setObjectName("OutputPreviewEdit")
        edit.setReadOnly(True)
        configure_settings_field_width(edit, preferred_width=420)
        try:
            edit.setText(
                service.render_preview(service.load_preferences()).display_path
            )
        except Exception as error:
            edit.setText(str(error))
        return SettingsCard(
            visual_widget=build_settings_icon_widget(
                AppIcon.SAVE_IMAGE_20_REGULAR, parent
            ),
            title=app_text("Output preview"),
            description=app_text("Shows an example path using the current settings."),
            trailing_widget=SettingsControlGroup(edit, parent=parent),
            reserve_visual_space=True,
            wrap_threshold=680,
            parent=parent,
        )

    def persistence_mode(self, parent: QWidget) -> SettingsCard:
        """Create the global all-versus-final persistence selector."""

        service = self._service
        return build_combo_settings_row(
            parent=parent,
            icon=AppIcon.SAVE_IMAGE_20_REGULAR,
            title=app_text("Saved cube outputs"),
            description=app_text(
                "Save every cube output or only the final active cube."
            ),
            options=(
                ("Every cube", OutputPersistenceMode.ALL.value),
                ("Final cube only", OutputPersistenceMode.FINAL_CUBE.value),
            ),
            selected=service.load_preferences().persistence_mode.value,
            on_changed=lambda value: service.save_preferences(
                replace(
                    service.load_preferences(),
                    persistence_mode=OutputPersistenceMode(str(value)),
                )
            ),
        )

    def jpeg_companions(self, parent: QWidget) -> JpegCompanionSettingsControl:
        """Create the cohesive JPEG companion settings group."""

        return JpegCompanionSettingsControl(self._service, parent)


__all__ = ["GenerationOutputSettingsRows"]
