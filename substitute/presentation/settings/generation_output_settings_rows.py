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

from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget
from qfluentwidgets import LineEdit, PushButton  # type: ignore[import-untyped]

from substitute.application.generation import (
    JpegSizingMode,
    OutputPersistenceMode,
    OutputPreferenceService,
    OutputPreferences,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.path_pattern_token_autocomplete import (
    PathPatternTokenAutocomplete,
    PathPatternTokenSuggestion,
)
from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_row_factories import (
    build_combo_settings_row,
    build_settings_icon_widget,
    build_switch_settings_row,
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
        browse_button = PushButton("Browse", parent)
        reset_button = PushButton("Default", parent)

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
                "Choose output folder",
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
            title="Output folder",
            description="Choose where generated images are saved.",
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
            title="Output pattern",
            description="Compose relative folders and filename without the .png extension.",
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
            title="Output preview",
            description="Shows an example path using the current settings.",
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
            title="Saved cube outputs",
            description="Save every cube output or only the final active cube.",
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

    def jpeg_enabled(self, parent: QWidget) -> SettingsCard:
        """Create the optional JPEG companion switch."""

        service = self._service
        return build_switch_settings_row(
            parent=parent,
            icon=AppIcon.SAVE_IMAGE_20_REGULAR,
            title="JPEG companions",
            description="Also save a JPEG beside each canonical recipe PNG.",
            checked=service.load_preferences().jpeg.enabled,
            on_changed=lambda enabled: service.save_preferences(
                replace(
                    service.load_preferences(),
                    jpeg=replace(
                        service.load_preferences().jpeg,
                        enabled=enabled,
                    ),
                )
            ),
        )

    def jpeg_sizing_mode(self, parent: QWidget) -> SettingsCard:
        """Create the JPEG quality-versus-target-size selector."""

        service = self._service
        return build_combo_settings_row(
            parent=parent,
            icon=AppIcon.IMAGE_SPARKLE_20_REGULAR,
            title="JPEG sizing",
            description="Choose fixed quality or an approximate target file size.",
            options=(
                ("Fixed quality", JpegSizingMode.QUALITY.value),
                ("Target size", JpegSizingMode.TARGET_SIZE.value),
            ),
            selected=service.load_preferences().jpeg.sizing_mode.value,
            on_changed=lambda value: service.save_preferences(
                replace(
                    service.load_preferences(),
                    jpeg=replace(
                        service.load_preferences().jpeg,
                        sizing_mode=JpegSizingMode(str(value)),
                    ),
                )
            ),
        )

    def jpeg_quality(self, parent: QWidget) -> SettingsCard:
        """Create the fixed-quality number field."""

        return self._jpeg_number(parent, target_size=False)

    def jpeg_target_size(self, parent: QWidget) -> SettingsCard:
        """Create the target-size number field."""

        return self._jpeg_number(parent, target_size=True)

    def _jpeg_number(self, parent: QWidget, *, target_size: bool) -> SettingsCard:
        """Create one validated JPEG quality or target-size number field."""

        service = self._service
        settings = service.load_preferences().jpeg
        edit = LineEdit(parent)
        edit.setObjectName("JpegTargetSizeEdit" if target_size else "JpegQualityEdit")
        configure_settings_field_width(edit, preferred_width=180)
        edit.setText(str(settings.target_size_kib if target_size else settings.quality))

        def save_value() -> None:
            """Parse and persist the edited numeric setting."""

            try:
                value = int(edit.text().strip())
            except ValueError:
                return
            loaded = service.load_preferences()
            jpeg = (
                replace(loaded.jpeg, target_size_kib=value)
                if target_size
                else replace(loaded.jpeg, quality=value)
            )
            result = service.save_preferences(replace(loaded, jpeg=jpeg))
            if result.succeeded:
                normalized = (
                    result.preferences.jpeg.target_size_kib
                    if target_size
                    else result.preferences.jpeg.quality
                )
                edit.setText(str(normalized))

        edit.editingFinished.connect(save_value)
        return SettingsCard(
            visual_widget=build_settings_icon_widget(
                AppIcon.SAVE_IMAGE_20_REGULAR, parent
            ),
            title="JPEG target size" if target_size else "JPEG quality",
            description=(
                "Approximate target size in KiB."
                if target_size
                else "Fixed JPEG quality from 1 to 100."
            ),
            trailing_widget=SettingsControlGroup(edit, parent=parent),
            reserve_visual_space=True,
            parent=parent,
        )


__all__ = ["GenerationOutputSettingsRows"]
