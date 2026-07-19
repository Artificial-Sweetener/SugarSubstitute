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

"""Construct the autocomplete list management modal for launch surfaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from substitute.application.managed_text_assets import (
    AutocompleteListManagedTextAssetService,
)
from substitute.application.managed_text_assets.prompt_profiles import (
    line_list_prompt_feature_profile,
)
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_autocomplete_lists import (
    PromptAutocompleteListService,
)
from substitute.domain.prompt import PromptWheelAdjustmentMode

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from substitute.application.prompt_editor import PromptSpellcheckService
    from substitute.presentation.editor.panel.service_bundle import (
        EditorPanelExecutionFactories,
    )

    from .autocomplete_list_management_modal import (
        AutocompleteListManagementModal,
    )


class AutocompleteListManagementOpener:
    """Open list management with composition-owned editor dependencies."""

    def __init__(
        self,
        *,
        list_service: PromptAutocompleteListService,
        prompt_autocomplete_gateway: PromptAutocompleteGateway,
        prompt_wildcard_catalog_gateway: PromptWildcardCatalogGateway,
        editor_panel_execution_factories: EditorPanelExecutionFactories,
        prompt_spellcheck_service: PromptSpellcheckService | None = None,
        prompt_wheel_adjustment_mode: Callable[[], PromptWheelAdjustmentMode]
        | None = None,
    ) -> None:
        """Store modal construction dependencies."""

        self._list_service = list_service
        self._prompt_autocomplete_gateway = prompt_autocomplete_gateway
        self._prompt_wildcard_catalog_gateway = prompt_wildcard_catalog_gateway
        self._execution_factories = editor_panel_execution_factories
        self._prompt_spellcheck_service = prompt_spellcheck_service
        self._wheel_adjustment_mode = prompt_wheel_adjustment_mode or (
            lambda: PromptWheelAdjustmentMode.HOVER_DWELL
        )

    def __call__(self, parent: QWidget | None = None) -> None:
        """Open the modal for one caller."""

        self.create_modal(parent).exec()

    def create_modal(
        self, parent: QWidget | None = None
    ) -> AutocompleteListManagementModal:
        """Create a modal for tests and launch surfaces."""

        from .autocomplete_list_management_modal import (
            AutocompleteListManagementModal,
        )
        from .wildcard_management_opener import _top_level_modal_parent

        return AutocompleteListManagementModal(
            service=AutocompleteListManagedTextAssetService(self._list_service),
            prompt_autocomplete_gateway=self._prompt_autocomplete_gateway,
            prompt_wildcard_catalog_gateway=self._prompt_wildcard_catalog_gateway,
            prompt_feature_profile=line_list_prompt_feature_profile(),
            prompt_spellcheck_service=self._prompt_spellcheck_service,
            prompt_task_executor_factory=(
                self._execution_factories.prompt_task_executor_factory
            ),
            danbooru_lookup_dispatcher_factory=(
                self._execution_factories.danbooru_lookup_dispatcher_factory
            ),
            wheel_adjustment_mode=self._wheel_adjustment_mode(),
            parent=_top_level_modal_parent(parent),
        )


__all__ = ["AutocompleteListManagementOpener"]
