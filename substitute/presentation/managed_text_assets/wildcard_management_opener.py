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

"""Provide a reusable caller-neutral wildcard management modal opener."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.domain.prompt import PromptWheelAdjustmentMode
from substitute.application.prompt_wildcards import PromptWildcardFileManagementService

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from substitute.application.prompt_editor import PromptSpellcheckService
    from substitute.presentation.editor.panel.service_bundle import (
        EditorPanelExecutionFactories,
    )

    from .wildcard_management_modal import WildcardManagementModal


class WildcardManagementOpener:
    """Construct and execute wildcard management modals for any launch surface."""

    def __init__(
        self,
        *,
        wildcard_file_management_service: PromptWildcardFileManagementService,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        editor_panel_execution_factories: EditorPanelExecutionFactories,
        prompt_spellcheck_service: PromptSpellcheckService | None = None,
        prompt_wheel_adjustment_mode: Callable[
            [],
            PromptWheelAdjustmentMode,
        ]
        | None = None,
    ) -> None:
        """Store modal construction dependencies supplied by composition."""

        self._wildcard_file_management_service = wildcard_file_management_service
        self._prompt_autocomplete_gateway = prompt_autocomplete_gateway
        self._prompt_wildcard_catalog_gateway = prompt_wildcard_catalog_gateway
        self._prompt_spellcheck_service = prompt_spellcheck_service
        self._editor_panel_execution_factories = editor_panel_execution_factories
        self._prompt_wheel_adjustment_mode = (
            prompt_wheel_adjustment_mode
            if prompt_wheel_adjustment_mode is not None
            else lambda: PromptWheelAdjustmentMode.HOVER_DWELL
        )

    def __call__(self, parent: QWidget | None = None) -> None:
        """Open the wildcard management modal with the supplied caller parent."""

        modal = self.create_modal(parent)
        modal.exec()

    def create_modal(self, parent: QWidget | None = None) -> WildcardManagementModal:
        """Create a wildcard management modal for tests and launch surfaces."""

        from substitute.application.managed_text_assets import (
            WildcardManagedTextAssetService,
        )
        from substitute.application.prompt_editor.prompt_feature_profile_service import (
            wildcard_management_prompt_feature_profile,
        )

        from .wildcard_management_modal import WildcardManagementModal

        modal_parent = _top_level_modal_parent(parent)
        return WildcardManagementModal(
            service=WildcardManagedTextAssetService(
                self._wildcard_file_management_service
            ),
            prompt_autocomplete_gateway=self._prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=self._prompt_wildcard_catalog_gateway,
            prompt_feature_profile=wildcard_management_prompt_feature_profile(),
            prompt_spellcheck_service=self._prompt_spellcheck_service,
            prompt_task_executor_factory=(
                self._editor_panel_execution_factories.prompt_task_executor_factory
            ),
            danbooru_lookup_dispatcher_factory=(
                self._editor_panel_execution_factories.danbooru_lookup_dispatcher_factory
            ),
            wheel_adjustment_mode=self._prompt_wheel_adjustment_mode(),
            parent=modal_parent,
        )


__all__ = ["WildcardManagementOpener"]


def _top_level_modal_parent(parent: QWidget | None) -> QWidget | None:
    """Return the top-level widget that should own the modal mask."""

    if parent is None:
        return None
    from PySide6.QtWidgets import QWidget

    top_level = parent.window()
    if isinstance(top_level, QWidget):
        return top_level
    return parent
