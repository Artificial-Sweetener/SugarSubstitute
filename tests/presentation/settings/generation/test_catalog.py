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

"""Verify Generation Settings catalog controls."""

from __future__ import annotations
from pathlib import Path
from typing import cast
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    ComboBox,
)
from substitute.application.civitai import (
    CivitaiPreferenceService,
)
from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputPreferenceService,
)
from substitute.domain.generation import (
    GenerationPreviewMethod,
    JpegOutputSettings,
    JpegSizingMode,
    OutputPersistenceMode,
    OutputPreferences,
    OutputTransferFormat,
)
from substitute.presentation.settings.jpeg_companion_settings import (
    JpegCompanionSettingsControl,
)
from substitute.presentation.localization import LocalizedSwitchButton
from substitute.presentation.settings.generation_preview_settings import (
    GenerationPreviewSettingsControl,
)
from substitute.presentation.settings import settings_catalog_builders
from substitute.presentation.settings.settings_control_group import SettingsControlGroup
from tests.presentation.settings.appearance.support import (
    settings_control,
)
from tests.presentation.settings.generation.support import (
    MemoryOutputPreferenceRepository,
    MemoryPreviewPreferenceRepository,
    RecordingPreviewBackend,
    application,
    immediate_task_runner,
)
from tests.support.qt.lifecycle import activate_widget_layouts


def test_generation_output_catalog_controls_persist_unified_output_policy(
    tmp_path: Path,
) -> None:
    """Generation controls should mutate the authoritative output aggregate."""

    application()
    repository = MemoryOutputPreferenceRepository()
    service = OutputPreferenceService(repository, default_output_root=tmp_path)
    page = settings_catalog_builders.build_generation_settings_page(
        settings_catalog_builders.GenerationSettingsContext(
            generation_preview_service=cast(
                GenerationPreviewPreferenceService,
                object(),
            ),
            output_preference_service=service,
            civitai_preference_service=cast(CivitaiPreferenceService, object()),
            task_runner_factory=immediate_task_runner,
        )
    )
    parent = QWidget()
    output_section = next(
        section
        for section in page.sections
        if section.section_id == "generation.output"
    )

    assert tuple(control.setting_id for control in output_section.controls) == (
        "generation.output.folder",
        "generation.output.pattern",
        "generation.output.preview",
        "generation.output.persistence",
        "generation.output.jpeg",
        "generation.output.transfer",
    )

    persistence_row = settings_control(page, "generation.output.persistence").factory(
        parent
    )
    persistence_combo = persistence_row.findChild(ComboBox)
    assert persistence_combo is not None
    persistence_combo.setCurrentIndex(1)

    jpeg_control = settings_control(page, "generation.output.jpeg").factory(parent)
    assert isinstance(jpeg_control, JpegCompanionSettingsControl)
    assert jpeg_control.is_expanded() is False
    assert jpeg_control.quality_control.value() == 100

    jpeg_control.set_checked(True)
    jpeg_control.mode_combo.setCurrentIndex(1)
    jpeg_control.target_size_control.spinbox.setValue(1.25)

    assert repository.preferences.persistence_mode is OutputPersistenceMode.FINAL_CUBE
    assert repository.preferences.jpeg.enabled is True
    assert repository.preferences.jpeg.sizing_mode is JpegSizingMode.TARGET_SIZE
    assert repository.preferences.jpeg.target_size_kib == 1280
    assert jpeg_control.value_stack.currentWidget() is jpeg_control.target_size_control

    transfer_row = settings_control(page, "generation.output.transfer").factory(parent)
    transfer_switch = transfer_row.findChild(LocalizedSwitchButton)
    assert transfer_switch is not None
    transfer_switch.setChecked(True)

    assert (
        repository.preferences.transfer.preferred_format
        is OutputTransferFormat.COMPANION_JPEG
    )


def test_generation_preview_catalog_uses_one_switch_control_and_persists_state() -> (
    None
):
    """Generation preview settings should disclose and persist one cohesive group."""

    application()
    repository = MemoryPreviewPreferenceRepository()
    page = settings_catalog_builders.build_generation_settings_page(
        settings_catalog_builders.GenerationSettingsContext(
            generation_preview_service=GenerationPreviewPreferenceService(repository),
            output_preference_service=cast(OutputPreferenceService, object()),
            civitai_preference_service=cast(CivitaiPreferenceService, object()),
            task_runner_factory=immediate_task_runner,
        )
    )
    preview_section = next(
        section
        for section in page.sections
        if section.section_id == "generation.preview"
    )

    assert tuple(control.setting_id for control in preview_section.controls) == (
        "generation.preview.configuration",
    )

    parent = QWidget()
    control = preview_section.controls[0].factory(parent)
    assert isinstance(control, GenerationPreviewSettingsControl)
    assert control.is_checked() is True
    assert control.is_expanded() is True
    assert control.selected_method() is GenerationPreviewMethod.LATENT2RGB

    control.set_method(GenerationPreviewMethod.AUTO)
    control.set_checked(False)

    assert control.has_pending_work() is False
    assert control.is_expanded() is False
    assert repository.preferences.enabled is False
    assert repository.preferences.method is GenerationPreviewMethod.AUTO

    control.set_checked(True)

    assert control.is_expanded() is True
    assert repository.preferences.enabled is True
    assert repository.preferences.method is GenerationPreviewMethod.AUTO


def test_generation_preview_control_prepares_taesd_through_async_save_route() -> None:
    """Selecting TAESD should preserve backend preparation and result feedback."""

    application()
    repository = MemoryPreviewPreferenceRepository()
    backend = RecordingPreviewBackend()
    control = GenerationPreviewSettingsControl(
        service=GenerationPreviewPreferenceService(repository, backend),
        task_runner_factory=immediate_task_runner,
    )

    control.set_method(GenerationPreviewMethod.TAESD)

    assert control.has_pending_work() is False
    assert repository.preferences.method is GenerationPreviewMethod.TAESD
    assert backend.ensure_calls == 1
    assert control.status_text() == "TAESD preview files are installed."


def test_jpeg_companion_control_restores_enabled_values_and_preserves_both_modes(
    tmp_path: Path,
) -> None:
    """Persisted JPEG settings should restore disclosure and retain inactive values."""

    application()
    repository = MemoryOutputPreferenceRepository()
    repository.preferences = OutputPreferences(
        jpeg=JpegOutputSettings(
            enabled=True,
            sizing_mode=JpegSizingMode.TARGET_SIZE,
            quality=83,
            target_size_kib=1536,
        )
    )
    service = OutputPreferenceService(repository, default_output_root=tmp_path)
    control = JpegCompanionSettingsControl(service)

    assert control.is_checked() is True
    assert control.is_expanded() is True
    assert control.quality_control.value() == 83
    assert control.target_size_control.value() == 1.5
    assert control.value_stack.currentWidget() is control.target_size_control

    control.mode_combo.setCurrentIndex(0)
    control.quality_control.spinbox.setValue(91)
    control.mode_combo.setCurrentIndex(1)

    assert repository.preferences.jpeg.quality == 91
    assert repository.preferences.jpeg.target_size_kib == 1536
    assert control.value_stack.currentWidget() is control.target_size_control
    control.close()


def test_jpeg_companion_controls_wrap_without_hiding_the_active_editor(
    tmp_path: Path,
) -> None:
    """The compound sizing controls should remain usable on narrow Settings pages."""

    application()
    repository = MemoryOutputPreferenceRepository()
    repository.preferences = OutputPreferences(
        jpeg=JpegOutputSettings(
            enabled=True,
            sizing_mode=JpegSizingMode.TARGET_SIZE,
        )
    )
    host = QWidget()
    layout = QVBoxLayout(host)
    control = JpegCompanionSettingsControl(
        OutputPreferenceService(repository, default_output_root=tmp_path),
        host,
    )
    layout.addWidget(control)
    control_group = control.findChild(SettingsControlGroup)
    assert control_group is not None

    host.resize(900, 320)
    host.show()
    activate_widget_layouts(host, control, control_group)

    assert control_group.layout_mode() == "horizontal"
    assert control.target_size_control.isVisible() is True
    assert (
        control.value_stack.mapTo(control_group, QPoint()).x()
        < control.mode_combo.mapTo(control_group, QPoint()).x()
    )
    assert control.target_size_control.spinbox.maximum() == 20.0
    assert control.target_size_control.spinbox.singleStep() == 0.1

    host.resize(480, 420)
    activate_widget_layouts(host, control, control_group)

    assert control_group.layout_mode() == "vertical"
    assert control.target_size_control.isVisible() is True
    assert (
        control.target_size_control.width()
        >= control.target_size_control.sizeHint().width()
    )
    host.close()
