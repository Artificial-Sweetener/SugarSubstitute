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

"""Expose application services for user-created presets."""

from __future__ import annotations

from substitute.application.user_presets.service import (
    DimensionPresetListing,
    DimensionPresetSection,
    NodeInputPresetListing,
    NodeInputPresetSection,
    PromptStringPresetListing,
    PromptStringPresetSection,
    UserPresetRepository,
    UserPresetService,
)
from substitute.domain.user_presets import (
    GLOBAL_PRESET_ASSOCIATION,
    DimensionPresetPayload,
    NodeInputPresetPayload,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
    UserPresetPayload,
)

__all__ = [
    "DimensionPresetListing",
    "DimensionPresetSection",
    "DimensionPresetPayload",
    "GLOBAL_PRESET_ASSOCIATION",
    "NodeInputPresetListing",
    "NodeInputPresetPayload",
    "NodeInputPresetSection",
    "PromptStringPresetListing",
    "PromptStringPresetPayload",
    "PromptStringPresetSection",
    "UserPreset",
    "UserPresetAssociation",
    "UserPresetAssociationScope",
    "UserPresetKind",
    "UserPresetPayload",
    "UserPresetRepository",
    "UserPresetService",
]
