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

"""Describe prepared saved dimensions independently from their Qt renderer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DimensionPresetItem:
    """Describe one saved dimension preset."""

    label: str
    short_edge: int
    long_edge: int


@dataclass(frozen=True, slots=True)
class DimensionPresetSection:
    """Group saved dimensions under one localized scope title."""

    title: str
    presets: tuple[DimensionPresetItem, ...]


@dataclass(frozen=True, slots=True)
class DimensionPresetCatalog:
    """Describe prepared presets and available save scopes."""

    sections: tuple[DimensionPresetSection, ...] = ()
    model_save_label: str | None = None
    can_save_globally: bool = True


class DimensionPresetCatalogSource(Protocol):
    """Provide prepared saved dimensions and persistence intents."""

    def prepare_dimension_preset_catalog(self, *, reason: str) -> None:
        """Refresh prepared dimension state outside interaction rendering."""

    def current_dimension_preset_catalog(self) -> DimensionPresetCatalog | None:
        """Return the latest prepared catalog."""

    def save_current_dimensions_globally(self, width: int, height: int) -> None:
        """Persist dimensions as a global preset."""

    def save_current_dimensions_for_model(self, width: int, height: int) -> None:
        """Persist dimensions for the prepared active model family."""


__all__ = [
    "DimensionPresetCatalog",
    "DimensionPresetCatalogSource",
    "DimensionPresetItem",
    "DimensionPresetSection",
]
