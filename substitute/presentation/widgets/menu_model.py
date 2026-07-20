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

"""Define toolkit-neutral menu models for presentation context menus."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TypeAlias

from sugarsubstitute_shared.localization import ApplicationText


@dataclass(frozen=True, slots=True)
class MenuItem:
    """Describe one executable menu row independent of Qt widgets."""

    action_id: str
    label: ApplicationText
    callback: Callable[[], None] | None = None
    enabled: bool = True
    checkable: bool = False
    checked: bool = False
    checked_callback: Callable[[bool], None] | None = None
    shortcut: str | None = None
    tooltip: ApplicationText | None = None
    icon: object | None = None
    properties: Mapping[str, object] = field(default_factory=dict)
    data: object | None = None


@dataclass(frozen=True, slots=True)
class MenuSeparator:
    """Describe a visual separator between menu groups."""


@dataclass(frozen=True, slots=True)
class MenuSection:
    """Describe an optional disabled header followed by menu entries."""

    entries: tuple[MenuEntry, ...]
    title: ApplicationText | None = None


@dataclass(frozen=True, slots=True)
class MenuSubmenu:
    """Describe an eagerly populated submenu."""

    label: ApplicationText
    entries: tuple[MenuEntry, ...]
    enabled: bool = True
    icon: object | None = None


@dataclass(frozen=True, slots=True)
class LazyMenuSubmenu:
    """Describe a submenu whose rows are populated only when opened."""

    label: ApplicationText
    entries_factory: Callable[[], tuple[MenuEntry, ...]]
    enabled: bool = True
    icon: object | None = None
    cache_entries: bool = True


MenuEntry: TypeAlias = (
    MenuItem | MenuSeparator | MenuSection | MenuSubmenu | LazyMenuSubmenu
)


@dataclass(frozen=True, slots=True)
class MenuModel:
    """Describe one complete context menu independent of Qt widgets."""

    entries: tuple[MenuEntry, ...]
    title: ApplicationText = ""
    object_name: str | None = None


__all__ = [
    "LazyMenuSubmenu",
    "MenuEntry",
    "MenuItem",
    "MenuModel",
    "MenuSection",
    "MenuSeparator",
    "MenuSubmenu",
]
