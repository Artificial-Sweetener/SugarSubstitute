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

"""Define storage-neutral editable text asset models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sugarsubstitute_shared.localization import ApplicationText


class ManagedTextAssetKind(StrEnum):
    """Classify editable text assets by authoring surface needs."""

    PROMPT_TEXT = "prompt_text"
    CSV = "csv"


@dataclass(frozen=True, slots=True)
class ManagedTextAsset:
    """Describe one editable text asset without exposing its storage backend."""

    id: str
    label: str
    group: ApplicationText
    subtitle: ApplicationText
    kind: ManagedTextAssetKind
    editable: bool
    can_rename: bool
    can_delete: bool
    enabled: bool | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CreateManagedTextAssetRequest:
    """Request creation of one managed text asset."""

    label: str
    kind: ManagedTextAssetKind
    content: str = ""
    category: str | None = None


@dataclass(frozen=True, slots=True)
class RenameManagedTextAssetRequest:
    """Request a label change for one managed text asset."""

    asset_id: str
    label: str


__all__ = [
    "CreateManagedTextAssetRequest",
    "ManagedTextAsset",
    "ManagedTextAssetKind",
    "RenameManagedTextAssetRequest",
]
