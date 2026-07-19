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

"""Adapt prompt autocomplete lists to the managed text asset contract."""

from __future__ import annotations

from substitute.application.prompt_autocomplete_lists import (
    PromptAutocompleteList,
    PromptAutocompleteListKind,
    PromptAutocompleteListService,
)

from .models import (
    CreateManagedTextAssetRequest,
    ManagedTextAsset,
    ManagedTextAssetKind,
    RenameManagedTextAssetRequest,
)


class AutocompleteListManagedTextAssetService:
    """Expose custom and censored TXT lists through the shared modal API."""

    def __init__(self, list_service: PromptAutocompleteListService) -> None:
        """Store the authoritative autocomplete list service."""

        self._lists = list_service

    def list_assets(self) -> tuple[ManagedTextAsset, ...]:
        """Return every list grouped by its autocomplete effect."""

        return tuple(_asset_from_list(item) for item in self._lists.list_lists())

    def read_asset_text(self, asset_id: str) -> str:
        """Read one list's line-based content."""

        return self._lists.read_text(asset_id)

    def save_asset_text(self, asset_id: str, text: str) -> ManagedTextAsset:
        """Save one list and return refreshed modal metadata."""

        return _asset_from_list(self._lists.write_text(asset_id, text))

    def create_asset(self, request: CreateManagedTextAssetRequest) -> ManagedTextAsset:
        """Create a custom or censored TXT list from its modal category."""

        if request.kind is not ManagedTextAssetKind.PROMPT_TEXT:
            raise ValueError("Autocomplete lists must be TXT files.")
        try:
            kind = PromptAutocompleteListKind(request.category or "")
        except ValueError as error:
            raise ValueError(
                "Autocomplete list creation requires a list kind."
            ) from error
        return _asset_from_list(
            self._lists.create_list(
                name=request.label,
                kind=kind,
                text=request.content,
            )
        )

    def rename_asset(self, request: RenameManagedTextAssetRequest) -> ManagedTextAsset:
        """Rename one list without changing its effect."""

        return _asset_from_list(
            self._lists.rename_list(request.asset_id, request.label)
        )

    def delete_asset(self, asset_id: str) -> None:
        """Delete one autocomplete list."""

        self._lists.delete_list(asset_id)

    def set_asset_enabled(self, asset_id: str, enabled: bool) -> ManagedTextAsset:
        """Toggle one list's participation in autocomplete."""

        return _asset_from_list(self._lists.set_enabled(asset_id, enabled))

    def refresh(self) -> None:
        """No-op because mutations refresh the configured gateway immediately."""


def _asset_from_list(item: PromptAutocompleteList) -> ManagedTextAsset:
    """Map one autocomplete list into reusable modal metadata."""

    count = len(tuple(line for line in item.text.splitlines() if line.strip()))
    noun = "tag" if count == 1 else "tags"
    return ManagedTextAsset(
        id=item.id,
        label=item.name,
        group=(
            "Custom tag lists"
            if item.kind is PromptAutocompleteListKind.CUSTOM
            else "Censored tag lists"
        ),
        subtitle=f"{count} {noun} · {'Enabled' if item.enabled else 'Disabled'}",
        kind=ManagedTextAssetKind.PROMPT_TEXT,
        editable=True,
        can_rename=True,
        can_delete=True,
        enabled=item.enabled,
        metadata=(("Effect", item.kind.value),),
    )


__all__ = ["AutocompleteListManagedTextAssetService"]
