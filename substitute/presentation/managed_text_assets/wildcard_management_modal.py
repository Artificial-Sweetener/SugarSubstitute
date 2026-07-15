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

"""Compose the wildcard-specific managed text asset modal."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from substitute.application.managed_text_assets import WildcardManagedTextAssetService
from substitute.application.managed_text_assets.models import ManagedTextAssetKind
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptSpellcheckService,
    PromptWheelAdjustmentMode,
)
from substitute.presentation.editor.prompt_editor.composition import (
    DanbooruWikiLookupDispatcherFactory,
    PromptEditorTaskExecutorFactory,
)

from .managed_text_asset_modal import (
    ManagedTextAssetCreateAction,
    ManagedTextAssetModal,
)


class WildcardManagementModal(ManagedTextAssetModal):
    """Manage user wildcard files through the reusable text asset modal."""

    def __init__(
        self,
        *,
        service: WildcardManagedTextAssetService,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        prompt_feature_profile: PromptEditorFeatureProfile,
        prompt_spellcheck_service: PromptSpellcheckService | None = None,
        prompt_task_executor_factory: PromptEditorTaskExecutorFactory | None = None,
        danbooru_lookup_dispatcher_factory: (
            DanbooruWikiLookupDispatcherFactory | None
        ) = None,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        parent: QWidget | None = None,
    ) -> None:
        """Create the wildcard management modal."""

        super().__init__(
            title="Wildcards",
            asset_title="Wildcard files",
            empty_text="No user wildcard files yet.",
            service=service,
            create_actions=(
                ManagedTextAssetCreateAction(
                    label="New TXT",
                    kind=ManagedTextAssetKind.PROMPT_TEXT,
                ),
                ManagedTextAssetCreateAction(
                    label="New CSV",
                    kind=ManagedTextAssetKind.CSV,
                    default_content="value\n",
                ),
            ),
            prompt_autocomplete_gateway=prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
            prompt_feature_profile=prompt_feature_profile,
            prompt_spellcheck_service=prompt_spellcheck_service,
            prompt_task_executor_factory=prompt_task_executor_factory,
            danbooru_lookup_dispatcher_factory=danbooru_lookup_dispatcher_factory,
            wheel_adjustment_mode=wheel_adjustment_mode,
            parent=parent,
        )


__all__ = ["WildcardManagementModal"]
