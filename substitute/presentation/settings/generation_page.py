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

"""Render generation preview and output organization preferences in Settings."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    ComboBox,
    IndicatorPosition,
    IconWidget,
    LineEdit,
    PushButton,
    SwitchButton,
)

from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    GenerationPreviewSaveResult,
    OutputOrganizationPreferences,
    OutputOrganizationPreferenceService,
)
from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_ICON_MAX_SIZE,
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskResult,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_TOP_MARGIN,
)
from substitute.presentation.settings.path_pattern_token_autocomplete import (
    PathPatternTokenAutocomplete,
    PathPatternTokenSuggestion,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.settings.generation_page")
_COMBO_WIDTH = 180
_PREVIEW_TYPE_DESCRIPTION = (
    "Choose the ComfyUI latent preview method sent with new prompts."
)
_PREVIEW_METHOD_LATENT2RGB = "latent2rgb"
_PREVIEW_METHOD_TAESD = "taesd"
_PREVIEW_METHOD_AUTO = "auto"
_OUTPUT_PATTERN_WIDTH = 360
_OUTPUT_ROOT_WIDTH = 420


class GenerationSettingsPage(QWidget):
    """Expose generation controls backed by persisted preferences."""

    saveCompleted = Signal(object)

    def __init__(
        self,
        *,
        preference_service: GenerationPreviewPreferenceService,
        output_organization_service: OutputOrganizationPreferenceService | None = None,
        parent: QWidget | None = None,
        task_runner_factory: SettingsAsyncTaskRunnerFactory,
    ) -> None:
        """Build the generation settings page."""

        super().__init__(parent)
        self._preference_service = preference_service
        self._output_organization_service = output_organization_service
        self._is_loading = False
        self._output_root_uses_default = True
        self._save_generation = 0
        self._save_runner = task_runner_factory(
            self,
            owner_id="generation_settings",
        )
        self.preview_switch = SwitchButton(
            "Off",
            self,
            indicatorPos=IndicatorPosition.RIGHT,
        )
        self.preview_type_combo = self._preview_type_combo()
        self.preview_type_row_widget: SettingsCard | None = None
        self.output_root_edit = self._output_root_edit()
        self.output_path_pattern_edit = self._output_pattern_edit(
            "OutputPathPatternEdit"
        )
        self.output_preview_edit = self._output_preview_edit()
        self.output_token_autocomplete: PathPatternTokenAutocomplete | None = None
        self._last_status_message = ""
        self._install_output_token_autocomplete()
        self._save_runner.taskCompleted.connect(self._apply_save_task_result)
        self.saveCompleted.connect(self._apply_save_result)
        self._build_layout()
        self.reload()

    def reload(self) -> None:
        """Reload visible controls from persisted preview preferences."""

        preferences = self._preference_service.load_preferences()
        self._is_loading = True
        try:
            self.preview_switch.setChecked(preferences.enabled)
            self._set_combo_data(self.preview_type_combo, preferences.method.value)
            self._reload_output_organization_controls()
            self._refresh_controls_enabled()
            self._set_status("")
        finally:
            self._is_loading = False
        self._refresh_output_preview()

    def is_generation_preview_enabled(self) -> bool:
        """Return whether the preview toggle is checked."""

        return bool(self.preview_switch.isChecked())

    def set_generation_preview_enabled(self, enabled: bool) -> None:
        """Set preview enablement through the same path a user click uses."""

        self.preview_switch.setChecked(enabled)

    def selected_preview_method(self) -> str | None:
        """Return the selected preview method, if recognized."""

        return self._selected_combo_data(self.preview_type_combo)

    def set_preview_method(self, method: str) -> None:
        """Set preview method through the same path a user selection uses."""

        self._set_combo_data(self.preview_type_combo, method)

    def set_output_root_text(self, path_text: str) -> None:
        """Set output root text and refresh the live preview."""

        self.output_root_edit.setText(path_text)
        self._refresh_output_preview()

    def set_output_path_pattern(self, pattern: str) -> None:
        """Set output path pattern and refresh the live preview."""

        self.output_path_pattern_edit.setText(pattern)
        self._refresh_output_preview()

    def output_preview_text(self) -> str:
        """Return the current output organization preview text."""

        return str(self.output_preview_edit.text())

    def status_text(self) -> str:
        """Return the latest save status for tests and diagnostics."""

        return self._last_status_message

    def has_pending_work(self) -> bool:
        """Return whether asynchronous preference saves are still running."""

        return self._save_runner.has_pending_work()

    def _build_layout(self) -> None:
        """Create the generation settings controls layout."""

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)
        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SETTINGS_CARD_GROUP_TOP_MARGIN)
        preview_cards: list[SettingsCard] = [self._enabled_row()]
        self.preview_type_row_widget = self._preview_type_row()
        preview_cards.append(self.preview_type_row_widget)
        content_layout.addWidget(
            SettingsCardGroup("Preview", cards=tuple(preview_cards), parent=self)
        )
        if self._output_organization_service is not None:
            content_layout.addWidget(
                SettingsCardGroup(
                    "Output",
                    cards=(
                        self._output_root_row(),
                        self._output_path_pattern_row(),
                        self._output_preview_row(),
                    ),
                    parent=self,
                )
            )
        content_layout.addStretch(1)
        page_layout.addWidget(content)
        page_layout.addStretch(1)

    def _enabled_row(self) -> InteractiveSettingsCard:
        """Create the generation preview toggle row."""

        self.preview_switch.setOnText("On")
        self.preview_switch.setOffText("Off")
        self.preview_switch.checkedChanged.connect(self._set_preview_enabled)
        row = InteractiveSettingsCard(
            visual_widget=self._icon_widget(AppIcon.IMAGE_SPARKLE_20_REGULAR),
            title="Generation previews",
            description="Show sampler preview frames while ComfyUI is generating.",
            trailing_widget=self.preview_switch,
            reserve_visual_space=True,
            parent=self,
        )
        row.activated.connect(
            lambda: self.preview_switch.setChecked(not self.preview_switch.isChecked())
        )
        return row

    def _preview_type_row(self) -> SettingsCard:
        """Create the preview type selection row."""

        self.preview_type_combo.currentIndexChanged.connect(self._set_preview_method)
        row = SettingsCard(
            visual_widget=self._icon_widget(AppIcon.IMAGE_SPARKLE_20_REGULAR),
            title="Preview type",
            description=_PREVIEW_TYPE_DESCRIPTION,
            trailing_widget=self.preview_type_combo,
            reserve_visual_space=True,
            parent=self,
        )
        return row

    def _preview_type_combo(self) -> ComboBox:
        """Create a fixed-width preview method combo box."""

        combo = ComboBox(self)
        configure_settings_field_width(combo, preferred_width=_COMBO_WIDTH)
        combo.addItem("Latent RGB", userData=_PREVIEW_METHOD_LATENT2RGB)
        combo.addItem("TAESD", userData=_PREVIEW_METHOD_TAESD)
        combo.addItem("Auto", userData=_PREVIEW_METHOD_AUTO)
        return combo

    def _output_root_edit(self) -> LineEdit:
        """Create the output root path field."""

        edit = LineEdit(self)
        edit.setObjectName("OutputRootEdit")
        configure_settings_field_width(edit, preferred_width=_OUTPUT_ROOT_WIDTH)
        edit.textChanged.connect(self._on_output_root_text_changed)
        edit.editingFinished.connect(self._save_output_organization_preferences)
        return edit

    def _output_pattern_edit(self, object_name: str) -> LineEdit:
        """Create one output pattern field."""

        edit = LineEdit(self)
        edit.setObjectName(object_name)
        configure_settings_field_width(edit, preferred_width=_OUTPUT_PATTERN_WIDTH)
        edit.textChanged.connect(lambda _text: self._refresh_output_preview())
        edit.editingFinished.connect(self._save_output_organization_preferences)
        return edit

    def _output_preview_edit(self) -> LineEdit:
        """Create read-only output preview field."""

        edit = LineEdit(self)
        edit.setObjectName("OutputPreviewEdit")
        edit.setReadOnly(True)
        configure_settings_field_width(edit, preferred_width=_OUTPUT_ROOT_WIDTH)
        return edit

    def _output_root_row(self) -> SettingsCard:
        """Create the output root folder row."""

        browse_button = PushButton("Browse", self)
        browse_button.clicked.connect(self._browse_output_root)
        reset_button = PushButton("Default", self)
        reset_button.clicked.connect(self._clear_output_root)
        trailing = SettingsControlGroup(
            self.output_root_edit,
            browse_button,
            reset_button,
            spacing=6,
            parent=self,
        )
        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.SAVE_IMAGE_20_REGULAR),
            title="Output folder",
            description="Choose where generated images are saved.",
            trailing_widget=trailing,
            reserve_visual_space=True,
            wrap_threshold=720,
            parent=self,
        )

    def _output_path_pattern_row(self) -> SettingsCard:
        """Create the output path pattern row."""

        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.DOCUMENT_TEXT_20_REGULAR),
            title="Output pattern",
            description="Compose relative folders and filename without the .png extension.",
            trailing_widget=SettingsControlGroup(
                self.output_path_pattern_edit,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=640,
            parent=self,
        )

    def _output_preview_row(self) -> SettingsCard:
        """Create the rendered output path preview row."""

        return SettingsCard(
            visual_widget=self._icon_widget(AppIcon.SAVE_IMAGE_20_REGULAR),
            title="Output preview",
            description="Shows an example path using the current settings.",
            trailing_widget=SettingsControlGroup(
                self.output_preview_edit,
                parent=self,
            ),
            reserve_visual_space=True,
            wrap_threshold=680,
            parent=self,
        )

    def _install_output_token_autocomplete(self) -> None:
        """Attach token autocomplete to the output pattern field when available."""

        service = self._output_organization_service
        if service is None:
            return
        suggestions = tuple(
            PathPatternTokenSuggestion(
                token=token.placeholder,
                description=token.description,
            )
            for token in service.supported_token_descriptions()
        )
        self.output_token_autocomplete = PathPatternTokenAutocomplete(
            self.output_path_pattern_edit,
            suggestions,
        )

    def _icon_widget(self, icon: Any) -> IconWidget:
        """Create one fixed-size Settings card icon."""

        widget = IconWidget(icon, self)
        widget.setFixedSize(SETTINGS_CARD_ICON_MAX_SIZE, SETTINGS_CARD_ICON_MAX_SIZE)
        return widget

    def _set_preview_enabled(self, enabled: bool) -> None:
        """Persist whether generation previews are enabled."""

        if self._is_loading:
            return
        self._run_save(lambda: self._preference_service.set_enabled(enabled))

    def _set_preview_method(self, _index: int) -> None:
        """Persist the selected preview type."""

        if self._is_loading:
            return
        method = self.selected_preview_method()
        if method is None:
            return
        self._run_save(lambda: self._preference_service.set_method_value(method))

    def _run_save(self, operation: Callable[[], GenerationPreviewSaveResult]) -> None:
        """Run one preference save off the Qt UI thread."""

        self._set_controls_busy(True)
        self._set_status("Saving generation preview settings.")
        self._save_generation += 1
        self._save_runner.run(
            task_id="generation_preview_save",
            generation=self._save_generation,
            operation=operation,
            context={"page": "generation"},
        )

    def _reload_output_organization_controls(self) -> None:
        """Load output organization controls from persisted preferences."""

        service = self._output_organization_service
        if service is None:
            return
        preferences = service.load_preferences()
        self._output_root_uses_default = preferences.output_root is None
        self.output_root_edit.setText(
            self._display_output_root_for_preferences(preferences)
        )
        self.output_path_pattern_edit.setText(preferences.path_pattern)
        self._refresh_output_preview()

    def _display_output_root_for_preferences(
        self,
        preferences: OutputOrganizationPreferences,
    ) -> str:
        """Return the root path text shown for saved output preferences."""

        service = self._output_organization_service
        if service is None:
            return ""
        output_root = preferences.output_root or service.effective_output_root(
            preferences
        )
        return str(output_root)

    def _on_output_root_text_changed(self, _text: str) -> None:
        """Track manual output-root edits while refreshing the live preview."""

        if not self._is_loading:
            self._output_root_uses_default = False
        self._refresh_output_preview()

    def _browse_output_root(self) -> None:
        """Open a folder picker for the output root."""

        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Output Folder",
            self.output_root_edit.text().strip(),
        )
        if selected:
            self.output_root_edit.setText(selected)
            self._save_output_organization_preferences()

    def _clear_output_root(self) -> None:
        """Use the default output root for future saves."""

        service = self._output_organization_service
        if service is None:
            return
        self._output_root_uses_default = True
        self._is_loading = True
        try:
            self.output_root_edit.setText(str(service.effective_output_root()))
        finally:
            self._is_loading = False
        self._refresh_output_preview()
        self._save_output_organization_preferences()

    def _current_output_preferences(self) -> OutputOrganizationPreferences:
        """Build output organization preferences from visible controls."""

        root_text = self.output_root_edit.text().strip()
        return OutputOrganizationPreferences(
            output_root=(
                None
                if self._output_root_uses_default or not root_text
                else Path(root_text)
            ),
            path_pattern=self.output_path_pattern_edit.text(),
        )

    def _refresh_output_preview(self) -> None:
        """Render output preview or validation text for visible controls."""

        if self._is_loading:
            return
        service = self._output_organization_service
        if service is None:
            return
        try:
            preview = service.render_preview(self._current_output_preferences())
        except Exception as error:
            self.output_preview_edit.setText(str(error))
            return
        self.output_preview_edit.setText(preview.display_path)

    def _save_output_organization_preferences(self) -> None:
        """Persist output organization settings and show non-blocking feedback."""

        service = self._output_organization_service
        if service is None:
            return
        result = service.save_preferences(self._current_output_preferences())
        self._set_status(result.message)
        if result.succeeded:
            self._is_loading = True
            try:
                self._output_root_uses_default = result.preferences.output_root is None
                self.output_root_edit.setText(
                    self._display_output_root_for_preferences(result.preferences)
                )
                self.output_path_pattern_edit.setText(result.preferences.path_pattern)
            finally:
                self._is_loading = False
            if result.preview is not None:
                self.output_preview_edit.setText(result.preview.display_path)
            return
        self.output_preview_edit.setText(result.message)

    def _apply_save_result(self, result: object) -> None:
        """Apply a completed preference save result to visible controls."""

        self._set_controls_busy(False)
        if not isinstance(result, GenerationPreviewSaveResult):
            message = "Generation preview settings could not be saved."
            self._set_status(message)
            self._show_error(message)
            return
        self._is_loading = True
        try:
            self.preview_switch.setChecked(result.preferences.enabled)
            self._set_combo_data(
                self.preview_type_combo,
                result.preferences.method.value,
            )
            self._refresh_controls_enabled()
            self._set_status(result.message)
            if not result.succeeded:
                self._show_error(result.message)
            elif result.taesd_ready is False:
                self._show_warning(result.message)
        finally:
            self._is_loading = False

    def _apply_save_task_result(self, result: object) -> None:
        """Convert one settings execution result into generation save feedback."""

        if not isinstance(result, SettingsAsyncTaskResult):
            return
        if result.task_id != "generation_preview_save":
            return
        if isinstance(result.value, GenerationPreviewSaveResult):
            self.saveCompleted.emit(result.value)
            return
        if result.error is not None:
            log_exception(
                _LOGGER,
                "Failed to save generation preview settings",
                error=result.error,
            )
        self.saveCompleted.emit(
            GenerationPreviewSaveResult(
                preferences=self._preference_service.load_preferences(),
                succeeded=False,
                message="Generation preview settings could not be saved.",
            )
        )

    def _set_controls_busy(self, busy: bool) -> None:
        """Disable editable controls while a save is in progress."""

        self.preview_switch.setEnabled(not busy)
        self.preview_type_combo.setEnabled(
            not busy and bool(self.preview_switch.isChecked())
        )

    def _refresh_controls_enabled(self) -> None:
        """Enable the type combo only when previews are enabled."""

        self.preview_type_combo.setEnabled(bool(self.preview_switch.isChecked()))

    def _set_status(self, text: str) -> None:
        """Remember save feedback without changing settings-row layout."""

        self._last_status_message = text

    def _show_warning(self, message: str) -> None:
        """Show non-blocking feedback for recoverable preview setup issues."""

        from qfluentwidgets import InfoBar

        InfoBar.warning(
            title="Generation previews",
            content=message,
            duration=4000,
            parent=self.window(),
        )

    def _show_error(self, message: str) -> None:
        """Show non-blocking feedback for failed preview preference saves."""

        from qfluentwidgets import InfoBar

        InfoBar.error(
            title="Generation previews",
            content=message,
            duration=5000,
            parent=self.window(),
        )

    def _set_combo_data(self, combo: ComboBox, value: object) -> None:
        """Set one combo item by user data."""

        index = self._combo_index_for_data(combo, value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _combo_index_for_data(self, combo: ComboBox, value: object) -> int:
        """Return the first combo index whose user data matches one value."""

        for index in range(combo.count()):
            if combo.itemData(index) == value:
                return index
        return -1

    def _selected_combo_data(
        self,
        combo: ComboBox,
    ) -> str | None:
        """Return selected combo data when it is a preview method."""

        value = combo.currentData()
        if isinstance(value, str):
            return value
        return None


__all__ = ["GenerationSettingsPage"]
