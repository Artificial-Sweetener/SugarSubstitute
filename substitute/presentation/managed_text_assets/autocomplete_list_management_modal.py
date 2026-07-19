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

"""Compose the custom and censored autocomplete list modal."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from substitute.application.managed_text_assets import (
    AutocompleteListManagedTextAssetService,
    ManagedTextAssetKind,
)
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptWheelAdjustmentMode,
)
from substitute.application.prompt_autocomplete_lists import (
    PromptAutocompleteListKind,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
)

from .managed_text_asset_modal import (
    ManagedTextAssetCreateAction,
    ManagedTextAssetModal,
)


class AutocompleteListManagementModal(ManagedTextAssetModal):
    """Manage line-based custom and censored autocomplete lists."""

    def __init__(
        self,
        *,
        service: AutocompleteListManagedTextAssetService,
        prompt_runtime_services: PromptEditorRuntimeServices,
        prompt_feature_profile: PromptEditorFeatureProfile,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        parent: QWidget | None = None,
    ) -> None:
        """Build the autocomplete list management experience."""

        super().__init__(
            title="Autocomplete Lists",
            asset_title="Tag lists",
            empty_text="No custom or censored tag lists yet.",
            service=service,
            create_actions=(
                ManagedTextAssetCreateAction(
                    label="New custom list",
                    kind=ManagedTextAssetKind.PROMPT_TEXT,
                    category=PromptAutocompleteListKind.CUSTOM.value,
                ),
                ManagedTextAssetCreateAction(
                    label="New censored list",
                    kind=ManagedTextAssetKind.PROMPT_TEXT,
                    category=PromptAutocompleteListKind.CENSORED.value,
                ),
            ),
            prompt_runtime_services=prompt_runtime_services,
            prompt_feature_profile=prompt_feature_profile,
            wheel_adjustment_mode=wheel_adjustment_mode,
            parent=parent,
        )


__all__ = ["AutocompleteListManagementModal"]
