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

"""Bind generation-preview settings to asynchronous preference operations."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QWidget
from qfluentwidgets import ComboBox, InfoBar  # type: ignore[import-untyped]

from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    GenerationPreviewSaveResult,
)
from substitute.domain.generation import GenerationPreviewMethod
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskResult,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_control_group import (
    SettingsControlGroup,
    configure_settings_field_width,
)
from substitute.presentation.settings.settings_expander import (
    SettingsExpanderRow,
    SwitchSettingsExpander,
)
from substitute.presentation.settings.settings_row_factories import (
    build_settings_icon_widget,
)
from substitute.shared.logging.logger import get_logger, log_exception

_LOGGER = get_logger("presentation.settings.generation_preview")
_SAVE_TASK_ID = "save_generation_preview"


class GenerationPreviewSettingsControl(SwitchSettingsExpander):
    """Present and persist the complete generation-preview preference group."""

    def __init__(
        self,
        *,
        service: GenerationPreviewPreferenceService,
        task_runner_factory: SettingsAsyncTaskRunnerFactory,
        parent: QWidget | None = None,
    ) -> None:
        """Create one switch-controlled generation-preview settings card."""

        self._service = service
        self._save_generation = 0
        self._active_save_generation: int | None = None
        self._last_status_message = ""
        preferences = service.load_preferences()
        super().__init__(
            title="Generation previews",
            description="Show sampler preview frames while ComfyUI is generating.",
            visual_widget=build_settings_icon_widget(
                AppIcon.IMAGE_SPARKLE_20_REGULAR,
                parent,
            ),
            checked=preferences.enabled,
            parent=parent,
        )
        self.setObjectName("GenerationPreviewSettingsControl")
        self.switch.setObjectName("GenerationPreviewSwitch")
        self.method_combo = self._build_method_combo(preferences.method)
        self.add_widget(
            SettingsExpanderRow(
                title="Preview type",
                description=(
                    "Choose the ComfyUI latent preview method sent with new prompts."
                ),
                trailing_widget=SettingsControlGroup(
                    self.method_combo,
                    parent=self.content_widget(),
                ),
                parent=self.content_widget(),
            )
        )
        self._save_runner = task_runner_factory(
            self,
            owner_id="generation_preview_settings",
        )
        self._save_runner.taskCompleted.connect(self._apply_save_task_result)
        self.checkedChanged.connect(self._save_enabled)
        self.method_combo.currentIndexChanged.connect(self._save_method)

    def status_text(self) -> str:
        """Return the latest preference-operation status for diagnostics."""

        return self._last_status_message

    def has_pending_work(self) -> bool:
        """Return whether a generation-preview save remains unsettled."""

        return self._save_runner.has_pending_work()

    def selected_method(self) -> GenerationPreviewMethod | None:
        """Return the preview method represented by the combo selection."""

        value = self.method_combo.currentData()
        if isinstance(value, GenerationPreviewMethod):
            return value
        if isinstance(value, str):
            try:
                return GenerationPreviewMethod(value)
            except ValueError:
                return None
        return None

    def set_method(self, method: GenerationPreviewMethod) -> None:
        """Select one preview method through the same path used by the user."""

        self._select_method(method)

    def _build_method_combo(self, selected: GenerationPreviewMethod) -> ComboBox:
        """Create the supported ComfyUI preview-method selector."""

        combo = ComboBox(self.content_widget())
        combo.setObjectName("GenerationPreviewMethodCombo")
        configure_settings_field_width(combo, preferred_width=180)
        combo.addItem("Latent RGB", userData=GenerationPreviewMethod.LATENT2RGB)
        combo.addItem("TAESD", userData=GenerationPreviewMethod.TAESD)
        combo.addItem("Auto", userData=GenerationPreviewMethod.AUTO)
        for index in range(combo.count()):
            if combo.itemData(index) is selected:
                combo.setCurrentIndex(index)
                break
        return combo

    def _save_enabled(self, enabled: bool) -> None:
        """Persist generation-preview enablement asynchronously."""

        self._run_save(lambda: self._service.set_enabled(enabled))

    def _save_method(self, _index: int) -> None:
        """Persist the selected preview method asynchronously."""

        method = self.selected_method()
        if method is None:
            return
        self._run_save(lambda: self._service.set_method(method))

    def _run_save(
        self,
        operation: Callable[[], GenerationPreviewSaveResult],
    ) -> None:
        """Submit one preview preference change through the Settings task lane."""

        self._save_generation += 1
        self._active_save_generation = self._save_generation
        self._set_controls_busy(True)
        self._last_status_message = "Saving generation preview settings."
        self._save_runner.run(
            task_id=_SAVE_TASK_ID,
            generation=self._save_generation,
            operation=operation,
            context={"page": "generation"},
        )

    def _apply_save_task_result(self, payload: object) -> None:
        """Apply only the latest completed generation-preview save."""

        if not isinstance(payload, SettingsAsyncTaskResult):
            return
        if payload.task_id != _SAVE_TASK_ID:
            return
        if payload.generation != self._active_save_generation:
            return
        self._active_save_generation = None
        self._set_controls_busy(False)
        if isinstance(payload.value, GenerationPreviewSaveResult):
            self._apply_save_result(payload.value)
            return
        if payload.error is not None:
            log_exception(
                _LOGGER,
                "Failed to save generation preview settings",
                error=payload.error,
            )
        self._restore_persisted_preferences()
        self._last_status_message = "Generation preview settings could not be saved."
        self._show_error(self._last_status_message)

    def _apply_save_result(self, result: GenerationPreviewSaveResult) -> None:
        """Reconcile controls and surface one application save result."""

        self._sync_controls(
            enabled=result.preferences.enabled,
            method=result.preferences.method,
        )
        self._last_status_message = result.message
        if not result.succeeded:
            self._show_error(result.message)
        elif result.taesd_ready is False:
            self._show_warning(result.message)

    def _restore_persisted_preferences(self) -> None:
        """Restore controls after an unexpected asynchronous failure."""

        preferences = self._service.load_preferences()
        self._sync_controls(
            enabled=preferences.enabled,
            method=preferences.method,
        )

    def _sync_controls(
        self,
        *,
        enabled: bool,
        method: GenerationPreviewMethod,
    ) -> None:
        """Apply authoritative preference state without scheduling another save."""

        self.switch.blockSignals(True)
        self.switch.setChecked(enabled)
        self.switch.blockSignals(False)
        self.set_expanded(enabled)
        self.method_combo.blockSignals(True)
        self._select_method(method)
        self.method_combo.blockSignals(False)

    def _select_method(self, method: GenerationPreviewMethod) -> None:
        """Select the combo item representing one preview method."""

        for index in range(self.method_combo.count()):
            if self.method_combo.itemData(index) is method:
                self.method_combo.setCurrentIndex(index)
                return

    def _set_controls_busy(self, busy: bool) -> None:
        """Prevent overlapping user edits while a preference save is active."""

        self.switch.setEnabled(not busy)
        self.method_combo.setEnabled(not busy)

    def _show_warning(self, message: str) -> None:
        """Show non-blocking feedback for unavailable TAESD assets."""

        InfoBar.warning(
            title="Generation previews",
            content=message,
            duration=4000,
            parent=self.window(),
        )

    def _show_error(self, message: str) -> None:
        """Show non-blocking feedback for failed preference operations."""

        InfoBar.error(
            title="Generation previews",
            content=message,
            duration=5000,
            parent=self.window(),
        )


__all__ = ["GenerationPreviewSettingsControl"]
