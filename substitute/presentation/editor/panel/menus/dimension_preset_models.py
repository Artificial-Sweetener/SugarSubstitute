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

"""Describe prepared saved-dimension menu state consumed by Qt renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DimensionPresetMenuItem:
    """Describe one saved dimension preset available from the menu."""

    label: str
    short_edge: int
    long_edge: int


@dataclass(frozen=True)
class DimensionPresetMenuSection:
    """Describe one saved-dimension section in the context menu."""

    title: str
    presets: tuple[DimensionPresetMenuItem, ...]


@dataclass(frozen=True)
class DimensionPresetMenuModel:
    """Describe prepared saved dimensions and save actions for one panel state."""

    sections: tuple[DimensionPresetMenuSection, ...] = ()
    model_save_label: str | None = None
    can_save_globally: bool = True


class DimensionPresetMenuSource(Protocol):
    """Provide prepared saved dimension presets and save intents."""

    def prepare_dimension_preset_menu_model(self, *, reason: str) -> None:
        """Refresh prepared dimension menu data outside menu opening."""

    def current_dimension_preset_menu_model(
        self,
    ) -> DimensionPresetMenuModel | None:
        """Return the last prepared dimension menu model."""

    def save_current_dimensions_globally(self, width: int, height: int) -> None:
        """Persist the current dimensions as a global preset."""

    def save_current_dimensions_for_model(self, width: int, height: int) -> None:
        """Persist the current dimensions for the prepared active model family."""


__all__ = [
    "DimensionPresetMenuItem",
    "DimensionPresetMenuModel",
    "DimensionPresetMenuSection",
    "DimensionPresetMenuSource",
]
