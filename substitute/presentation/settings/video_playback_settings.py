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

"""Build generated-video settings around the Output preference owner."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QWidget
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.application.generation import (
    OutputPreferenceService,
    VideoHardwareDecoding,
    VideoRenderer,
)
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.settings_row_factories import (
    build_combo_settings_row,
)


def create_video_hardware_decoding_row(
    service: OutputPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the safe Off/Auto hardware-decoding preference row."""

    return build_combo_settings_row(
        parent=parent,
        icon=AppIcon.SETTINGS_20_REGULAR,
        title=app_text("Video hardware decoding"),
        description=app_text(
            "Use safe automatic hardware decoding or always decode in software."
        ),
        options=(
            (app_text("Auto"), VideoHardwareDecoding.AUTO.value),
            (app_text("Off"), VideoHardwareDecoding.OFF.value),
        ),
        selected=service.load_preferences().video.hardware_decoding.value,
        on_changed=lambda value: _save_hardware_decoding(service, value),
    )


def create_video_renderer_row(
    service: OutputPreferenceService,
    parent: QWidget,
) -> SettingsCard:
    """Create the validated libmpv renderer preference row."""

    return build_combo_settings_row(
        parent=parent,
        icon=AppIcon.RECTANGLE_LANDSCAPE_20_REGULAR,
        title=app_text("Video renderer"),
        description=app_text(
            "Choose automatic fallback or a specific supported GPU renderer."
        ),
        options=(
            (app_text("Auto"), VideoRenderer.AUTO.value),
            (app_text("GPU Next"), VideoRenderer.GPU_NEXT.value),
            (app_text("GPU"), VideoRenderer.GPU.value),
        ),
        selected=service.load_preferences().video.renderer.value,
        on_changed=lambda value: _save_renderer(service, value),
    )


def _save_hardware_decoding(
    service: OutputPreferenceService,
    value: object,
) -> object:
    """Persist one validated hardware-decoding choice."""

    preferences = service.load_preferences()
    return service.save_preferences(
        replace(
            preferences,
            video=replace(
                preferences.video,
                hardware_decoding=VideoHardwareDecoding(str(value)),
            ),
        )
    )


def _save_renderer(service: OutputPreferenceService, value: object) -> object:
    """Persist one validated renderer choice."""

    preferences = service.load_preferences()
    return service.save_preferences(
        replace(
            preferences,
            video=replace(
                preferences.video,
                renderer=VideoRenderer(str(value)),
            ),
        )
    )


__all__ = ["create_video_hardware_decoding_row", "create_video_renderer_row"]
