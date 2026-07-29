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

"""Bind output drag-and-copy representation preference to Settings."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QWidget
from sugarsubstitute_shared.localization import app_text

from substitute.application.generation import OutputPreferenceService
from substitute.domain.generation import OutputTransferFormat
from substitute.presentation.resources.app_icon import AppIcon
from substitute.presentation.settings.settings_card import InteractiveSettingsCard
from substitute.presentation.settings.settings_row_factories import (
    build_switch_settings_row,
)


def create_output_transfer_settings_row(
    service: OutputPreferenceService,
    parent: QWidget,
) -> InteractiveSettingsCard:
    """Create the companion-JPEG transfer preference control."""

    preferences = service.load_preferences()
    row = build_switch_settings_row(
        parent=parent,
        icon=AppIcon.SAVE_IMAGE_20_REGULAR,
        title=app_text("Use companion JPEG for drag and Copy"),
        description=app_text(
            "When JPEG companions are enabled, drag and Copy export the companion JPEG."
        ),
        checked=(
            preferences.transfer.preferred_format is OutputTransferFormat.COMPANION_JPEG
        ),
        on_changed=lambda checked: _save_transfer_preference(service, checked),
    )
    row.setObjectName("OutputTransferSettingsRow")
    return row


def _save_transfer_preference(
    service: OutputPreferenceService,
    use_companion_jpeg: bool,
) -> None:
    """Persist the selected transfer representation without changing JPEG generation."""

    preferences = service.load_preferences()
    service.save_preferences(
        replace(
            preferences,
            transfer=replace(
                preferences.transfer,
                preferred_format=(
                    OutputTransferFormat.COMPANION_JPEG
                    if use_companion_jpeg
                    else OutputTransferFormat.CANONICAL_PNG
                ),
            ),
        )
    )


__all__ = ["create_output_transfer_settings_row"]
