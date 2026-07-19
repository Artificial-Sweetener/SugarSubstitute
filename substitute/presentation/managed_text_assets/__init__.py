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

"""Expose widgets for managed text asset editing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .autocomplete_list_management_modal import AutocompleteListManagementModal
    from .autocomplete_list_management_opener import AutocompleteListManagementOpener
    from .managed_text_asset_modal import (
        ManagedTextAssetCreateAction,
        ManagedTextAssetModal,
    )
    from .numbered_prompt_editor_frame import NumberedPromptEditorFrame
    from .wildcard_management_modal import WildcardManagementModal
    from .wildcard_management_opener import WildcardManagementOpener

_EXPORTS = {
    "AutocompleteListManagementModal": (
        "substitute.presentation.managed_text_assets.autocomplete_list_management_modal"
    ),
    "AutocompleteListManagementOpener": (
        "substitute.presentation.managed_text_assets.autocomplete_list_management_opener"
    ),
    "ManagedTextAssetCreateAction": (
        "substitute.presentation.managed_text_assets.managed_text_asset_modal"
    ),
    "ManagedTextAssetModal": (
        "substitute.presentation.managed_text_assets.managed_text_asset_modal"
    ),
    "NumberedPromptEditorFrame": (
        "substitute.presentation.managed_text_assets.numbered_prompt_editor_frame"
    ),
    "WildcardManagementModal": (
        "substitute.presentation.managed_text_assets.wildcard_management_modal"
    ),
    "WildcardManagementOpener": (
        "substitute.presentation.managed_text_assets.wildcard_management_opener"
    ),
}


def __getattr__(name: str) -> Any:
    """Load managed-text UI exports only when a caller asks for them."""

    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)

    from importlib import import_module

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = [
    "AutocompleteListManagementModal",
    "AutocompleteListManagementOpener",
    "ManagedTextAssetCreateAction",
    "ManagedTextAssetModal",
    "NumberedPromptEditorFrame",
    "WildcardManagementModal",
    "WildcardManagementOpener",
]
