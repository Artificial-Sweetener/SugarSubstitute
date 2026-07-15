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

"""Define persisted prompt editor feature preferences."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from substitute.domain.prompt.features import PromptEditorFeature

PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION = "2"


class PromptWheelAdjustmentMode(str, Enum):
    """Define how mouse-wheel value edits are authorized in prompt editors."""

    HOVER_DWELL = "hover_dwell"
    FOCUS_REQUIRED = "focus_required"


@dataclass(frozen=True, slots=True)
class PromptEditorPreferences:
    """Capture user-allowed prompt editor features."""

    schema_version: str
    user_allowed_features: Mapping[PromptEditorFeature, bool]
    wheel_adjustment_mode: PromptWheelAdjustmentMode = (
        PromptWheelAdjustmentMode.HOVER_DWELL
    )

    def user_allows(self, feature: PromptEditorFeature) -> bool:
        """Return whether the user allows one feature when compatible."""

        return bool(self.user_allowed_features.get(feature, False))

    def with_feature_allowed(
        self,
        feature: PromptEditorFeature,
        allowed: bool,
    ) -> PromptEditorPreferences:
        """Return a copy with one feature preference updated."""

        updated = dict(self.user_allowed_features)
        updated[feature] = allowed
        return PromptEditorPreferences(
            schema_version=self.schema_version,
            user_allowed_features=updated,
            wheel_adjustment_mode=self.wheel_adjustment_mode,
        )

    def with_wheel_adjustment_mode(
        self,
        mode: PromptWheelAdjustmentMode,
    ) -> PromptEditorPreferences:
        """Return a copy with the wheel adjustment mode updated."""

        return PromptEditorPreferences(
            schema_version=self.schema_version,
            user_allowed_features=self.user_allowed_features,
            wheel_adjustment_mode=mode,
        )


__all__ = [
    "PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION",
    "PromptEditorPreferences",
    "PromptWheelAdjustmentMode",
]
