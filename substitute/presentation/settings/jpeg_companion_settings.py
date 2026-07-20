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

"""Bind cohesive JPEG companion settings to generated-output preferences."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import (
    LocalizedComboItem,
    app_text,
    set_localized_combo_items,
)


from dataclasses import replace

from PySide6.QtWidgets import QStackedWidget, QWidget
from qfluentwidgets import ComboBox  # type: ignore[import-untyped]

from substitute.application.generation import (
    JpegSizingMode,
    OutputPreferenceService,
)
from substitute.presentation.resources.app_icon import AppIcon
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
from substitute.presentation.widgets import (
    DecimalSpinnerSlider,
    IntegerSpinnerSlider,
)

_KIB_PER_DISPLAY_MB = 1024
_MINIMUM_TARGET_SIZE_MB = 0.1
_MAXIMUM_TARGET_SIZE_MB = 20.0
_TARGET_SIZE_STEP_MB = 0.1


class JpegCompanionSettingsControl(SwitchSettingsExpander):
    """Present and persist the complete JPEG companion preference group."""

    def __init__(
        self,
        service: OutputPreferenceService,
        parent: QWidget | None = None,
    ) -> None:
        """Create the switch-controlled JPEG settings card."""

        self._service = service
        settings = service.load_preferences().jpeg
        super().__init__(
            title=app_text("JPEG companions"),
            description=app_text("Also save a JPEG beside each canonical recipe PNG."),
            visual_widget=build_settings_icon_widget(
                AppIcon.SAVE_IMAGE_20_REGULAR,
                parent,
            ),
            checked=settings.enabled,
            parent=parent,
        )
        self.setObjectName("JpegCompanionSettingsControl")
        self.switch.setObjectName("JpegCompanionsSwitch")
        self.mode_combo = self._build_mode_combo(settings.sizing_mode)
        self.quality_control = IntegerSpinnerSlider(
            minimum=1,
            maximum=100,
            step=1,
            value=settings.quality,
            parent=self.content_widget(),
        )
        self.quality_control.setObjectName("JpegQualitySpinnerSlider")
        self.quality_control.spinbox.setObjectName("JpegQualitySpinBox")
        self.quality_control.slider.setObjectName("JpegQualitySlider")
        self.target_size_control = DecimalSpinnerSlider(
            minimum=_MINIMUM_TARGET_SIZE_MB,
            maximum=_MAXIMUM_TARGET_SIZE_MB,
            step=_TARGET_SIZE_STEP_MB,
            value=_target_size_mb(settings.target_size_kib),
            decimals=2,
            spinbox_width=96,
            suffix=" MB",
            parent=self.content_widget(),
        )
        self.target_size_control.setObjectName("JpegTargetSizeSpinnerSlider")
        self.target_size_control.spinbox.setObjectName("JpegTargetSizeSpinBox")
        self.target_size_control.slider.setObjectName("JpegTargetSizeSlider")
        self.value_stack = self._build_value_stack(settings.sizing_mode)
        controls = SettingsControlGroup(
            self.value_stack,
            self.mode_combo,
            spacing=8,
            parent=self.content_widget(),
        )
        self.add_widget(
            SettingsExpanderRow(
                title=app_text("JPEG sizing"),
                description=app_text(
                    "Choose fixed quality or an approximate target file size."
                ),
                trailing_widget=controls,
                parent=self.content_widget(),
            )
        )
        self.checkedChanged.connect(self._save_enabled)
        self.mode_combo.currentIndexChanged.connect(self._save_sizing_mode)
        self.quality_control.valueChanged.connect(self._save_quality)
        self.target_size_control.valueChanged.connect(self._save_target_size)

    def _build_mode_combo(self, selected: JpegSizingMode) -> ComboBox:
        """Create the mutually exclusive JPEG sizing selector."""

        combo = ComboBox(self.content_widget())
        combo.setObjectName("JpegSizingModeCombo")
        configure_settings_field_width(combo, preferred_width=140)
        set_localized_combo_items(
            combo,
            (
                LocalizedComboItem(JpegSizingMode.QUALITY, app_text("Quality")),
                LocalizedComboItem(
                    JpegSizingMode.TARGET_SIZE,
                    app_text("Target size"),
                ),
            ),
        )
        for index in range(combo.count()):
            if combo.itemData(index) is selected:
                combo.setCurrentIndex(index)
                break
        return combo

    def _build_value_stack(self, selected: JpegSizingMode) -> QStackedWidget:
        """Create one stable host that preserves both sizing values."""

        stack = QStackedWidget(self.content_widget())
        stack.setObjectName("JpegSizingValueStack")
        stack.addWidget(self.quality_control)
        stack.addWidget(self.target_size_control)
        configure_settings_field_width(
            stack,
            preferred_width=224,
            minimum_width=224,
        )
        self._show_sizing_mode(selected, stack=stack)
        return stack

    def _save_enabled(self, enabled: bool) -> None:
        """Persist whether JPEG companions are generated."""

        self._save_jpeg_settings(enabled=enabled)

    def _save_sizing_mode(self, _index: int) -> None:
        """Display and persist the selected sizing constraint."""

        mode = self._selected_sizing_mode()
        if mode is None:
            return
        self._show_sizing_mode(mode)
        self._save_jpeg_settings(sizing_mode=mode)

    def _save_quality(self, quality: int) -> None:
        """Persist the fixed JPEG quality value."""

        self._save_jpeg_settings(quality=quality)

    def _save_target_size(self, target_size_mb: float) -> None:
        """Convert displayed megabytes and persist the encoder's KiB value."""

        self._save_jpeg_settings(
            target_size_kib=max(1, round(target_size_mb * _KIB_PER_DISPLAY_MB))
        )

    def _save_jpeg_settings(
        self,
        *,
        enabled: bool | None = None,
        sizing_mode: JpegSizingMode | None = None,
        quality: int | None = None,
        target_size_kib: int | None = None,
    ) -> None:
        """Persist one partial JPEG update through the aggregate service."""

        preferences = self._service.load_preferences()
        updated = preferences.jpeg
        if enabled is not None:
            updated = replace(updated, enabled=enabled)
        if sizing_mode is not None:
            updated = replace(updated, sizing_mode=sizing_mode)
        if quality is not None:
            updated = replace(updated, quality=quality)
        if target_size_kib is not None:
            updated = replace(updated, target_size_kib=target_size_kib)
        self._service.save_preferences(replace(preferences, jpeg=updated))

    def _selected_sizing_mode(self) -> JpegSizingMode | None:
        """Return the sizing mode represented by the current combo item."""

        value = self.mode_combo.currentData()
        if isinstance(value, JpegSizingMode):
            return value
        if isinstance(value, str):
            try:
                return JpegSizingMode(value)
            except ValueError:
                return None
        return None

    def _show_sizing_mode(
        self,
        mode: JpegSizingMode,
        *,
        stack: QStackedWidget | None = None,
    ) -> None:
        """Show the numeric editor owned by the selected sizing mode."""

        target = self.value_stack if stack is None else stack
        target.setCurrentWidget(
            self.quality_control
            if mode is JpegSizingMode.QUALITY
            else self.target_size_control
        )


def _target_size_mb(target_size_kib: int) -> float:
    """Return the persisted KiB value in the requested MB presentation unit."""

    return target_size_kib / _KIB_PER_DISPLAY_MB


__all__ = ["JpegCompanionSettingsControl"]
