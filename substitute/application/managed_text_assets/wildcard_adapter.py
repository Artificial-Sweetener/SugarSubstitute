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

"""Adapt user wildcard files to the managed text asset contract."""

from __future__ import annotations

from pathlib import PurePosixPath

from sugarsubstitute_shared.localization import ApplicationText, app_text

from substitute.application.prompt_wildcards import (
    PromptWildcardFileEntry,
    PromptWildcardFileManagementService,
)

from .models import (
    CreateManagedTextAssetRequest,
    ManagedTextAsset,
    ManagedTextAssetKind,
    RenameManagedTextAssetRequest,
)

_TEXT_GROUP = app_text("TXT Wildcards")
_CSV_GROUP = app_text("CSV Wildcards")
_SUPPORTED_SUFFIXES = frozenset({".txt", ".csv"})


class WildcardManagedTextAssetService:
    """Expose user wildcard files through the managed text asset API."""

    def __init__(
        self,
        wildcard_file_management_service: PromptWildcardFileManagementService,
    ) -> None:
        """Store the wildcard file management service."""

        self._wildcards = wildcard_file_management_service

    def list_assets(self) -> tuple[ManagedTextAsset, ...]:
        """Return managed wildcard files grouped by wildcard file type."""

        assets = tuple(
            _asset_from_entry(
                entry, text=self._wildcards.read_file(entry.relative_path)
            )
            for entry in self._wildcards.list_files()
        )
        return tuple(sorted(assets, key=_asset_sort_key))

    def read_asset_text(self, asset_id: str) -> str:
        """Read one wildcard file by relative path."""

        return self._wildcards.read_file(asset_id)

    def save_asset_text(self, asset_id: str, text: str) -> ManagedTextAsset:
        """Save one wildcard file and return its refreshed asset metadata."""

        self._wildcards.write_file(asset_id, text)
        return self._asset_by_id(asset_id)

    def create_asset(
        self,
        request: CreateManagedTextAssetRequest,
    ) -> ManagedTextAsset:
        """Create one wildcard file and return its asset metadata."""

        identifier = request.label.strip()
        if request.kind is ManagedTextAssetKind.CSV:
            path = self._wildcards.create_csv_file(
                identifier,
                request.content or "value\n",
            )
        elif request.kind is ManagedTextAssetKind.PROMPT_TEXT:
            path = self._wildcards.create_text_file(identifier, request.content)
        else:
            raise ValueError(f"Unsupported managed wildcard asset kind: {request.kind}")
        return self._asset_by_id(
            path.relative_to(self._wildcards.root_path()).as_posix()
        )

    def rename_asset(
        self,
        request: RenameManagedTextAssetRequest,
    ) -> ManagedTextAsset:
        """Rename one wildcard file while preserving its existing suffix."""

        old_path = PurePosixPath(request.asset_id)
        suffix = old_path.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            raise ValueError("Wildcard asset id must end with .txt or .csv.")
        new_relative_path = _file_path_for_label(request.label, suffix)
        path = self._wildcards.rename_file(request.asset_id, new_relative_path)
        return self._asset_by_id(
            path.relative_to(self._wildcards.root_path()).as_posix()
        )

    def delete_asset(self, asset_id: str) -> None:
        """Delete one managed wildcard file."""

        self._wildcards.delete_file(asset_id)

    def set_asset_enabled(self, asset_id: str, enabled: bool) -> ManagedTextAsset:
        """Reject enablement because wildcard files do not expose this state."""

        del asset_id, enabled
        raise ValueError("Wildcard files cannot be enabled or disabled individually.")

    def refresh(self) -> None:
        """Refresh wildcard catalog caches."""

        self._wildcards.refresh_cache()

    def _asset_by_id(self, asset_id: str) -> ManagedTextAsset:
        """Return one refreshed asset or fail when it no longer exists."""

        for asset in self.list_assets():
            if asset.id == asset_id:
                return asset
        raise FileNotFoundError(f"Managed wildcard asset not found: {asset_id}")


def _asset_from_entry(entry: PromptWildcardFileEntry, *, text: str) -> ManagedTextAsset:
    """Map one wildcard file entry into backend-neutral asset metadata."""

    suffix = entry.suffix.lower()
    kind = (
        ManagedTextAssetKind.CSV
        if suffix == ".csv"
        else ManagedTextAssetKind.PROMPT_TEXT
    )
    group = _CSV_GROUP if kind is ManagedTextAssetKind.CSV else _TEXT_GROUP
    return ManagedTextAsset(
        id=entry.relative_path,
        label=entry.identifier,
        group=group,
        subtitle=_wildcard_count_text(_wildcard_line_count(text)),
        kind=kind,
        editable=True,
        can_rename=True,
        can_delete=True,
        metadata=(("Type", suffix.upper().lstrip(".")),),
    )


def _asset_sort_key(asset: ManagedTextAsset) -> tuple[int, str, str]:
    """Return the stable wildcard ordering used by the management modal."""

    group_order = 0 if asset.group == _TEXT_GROUP else 1
    return group_order, asset.label.casefold(), asset.id.casefold()


def _file_path_for_label(label: str, suffix: str) -> str:
    """Return a wildcard relative path for one requested asset label."""

    path = PurePosixPath(label.strip().replace("\\", "/"))
    if path.suffix.lower() in _SUPPORTED_SUFFIXES:
        path = path.with_suffix("")
    return f"{path.as_posix()}{suffix}"


def _wildcard_line_count(text: str) -> int:
    """Return the number of wildcard entries implied by source line count."""

    return len(text.splitlines())


def _wildcard_count_text(count: int) -> ApplicationText:
    """Return row subtitle text for one wildcard count."""

    if count == 1:
        return app_text("%1 wildcard", count)
    return app_text("%1 wildcards", count)


__all__ = ["WildcardManagedTextAssetService"]
