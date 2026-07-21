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

from sugarsubstitute_shared.presentation.localization import app_text

from PySide6.QtWidgets import QWidget

from substitute.application.managed_text_assets import WildcardManagedTextAssetService
from substitute.application.managed_text_assets.wildcard_csv_document_semantics import (
    WildcardCsvDocumentSemantics,
)
from substitute.application.managed_text_assets.wildcard_text_document_semantics import (
    WildcardTextDocumentSemantics,
)
from substitute.application.managed_text_assets.models import ManagedTextAsset
from substitute.application.managed_text_assets.models import ManagedTextAssetKind
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptWheelAdjustmentMode,
)
from substitute.application.prompt_editor.prompt_document_semantics import (
    PromptDocumentSemantics,
)
from substitute.presentation.editor.prompt_editor.runtime_services import (
    PromptEditorRuntimeServices,
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
        prompt_runtime_services: PromptEditorRuntimeServices,
        prompt_feature_profile: PromptEditorFeatureProfile,
        wheel_adjustment_mode: PromptWheelAdjustmentMode = (
            PromptWheelAdjustmentMode.HOVER_DWELL
        ),
        parent: QWidget | None = None,
    ) -> None:
        """Create the wildcard management modal."""

        super().__init__(
            title=app_text("Wildcards"),
            asset_title="Wildcard files",
            empty_text="No user wildcard files yet.",
            service=service,
            create_actions=(
                ManagedTextAssetCreateAction(
                    label=app_text("New TXT"),
                    kind=ManagedTextAssetKind.PROMPT_TEXT,
                ),
                ManagedTextAssetCreateAction(
                    label=app_text("New CSV"),
                    kind=ManagedTextAssetKind.CSV,
                    default_content="value\n",
                ),
            ),
            prompt_runtime_services=prompt_runtime_services,
            prompt_feature_profile=prompt_feature_profile,
            document_semantics_for_asset=_wildcard_document_semantics,
            wheel_adjustment_mode=wheel_adjustment_mode,
            parent=parent,
        )


__all__ = ["WildcardManagementModal"]


def _wildcard_document_semantics(asset: ManagedTextAsset) -> PromptDocumentSemantics:
    """Return source semantics matching one wildcard asset's persisted format."""

    if asset.kind is ManagedTextAssetKind.CSV:
        return WildcardCsvDocumentSemantics()
    return WildcardTextDocumentSemantics()
