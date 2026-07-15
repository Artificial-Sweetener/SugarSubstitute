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

"""Describe ordered Settings pages, sections, and controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtWidgets import QWidget
from qfluentwidgets.common.icon import FluentIconBase  # type: ignore[import-untyped]


class SettingsControlFactory(Protocol):
    """Create a fresh Settings control widget for one parent."""

    def __call__(self, parent: QWidget) -> QWidget:
        """Return a new control widget bound to the relevant services."""


@dataclass(frozen=True, slots=True)
class SettingsControlEntry:
    """Describe one ordered, searchable Settings control."""

    setting_id: str
    title: str
    description: str
    keywords: tuple[str, ...]
    order: int
    factory: SettingsControlFactory
    is_visible: Callable[[], bool] | None = None

    def visible(self) -> bool:
        """Return whether this control should render in Settings."""

        return self.is_visible is None or self.is_visible()


@dataclass(frozen=True, slots=True)
class SettingsSectionEntry:
    """Describe one ordered Settings section."""

    section_id: str
    title: str
    subtitle: str
    order: int
    controls: tuple[SettingsControlEntry, ...]

    def visible_controls(self) -> tuple[SettingsControlEntry, ...]:
        """Return visible controls in deterministic order."""

        return tuple(
            sorted(
                (control for control in self.controls if control.visible()),
                key=lambda control: control.order,
            )
        )


@dataclass(frozen=True, slots=True)
class SettingsPageEntry:
    """Describe one user-facing Settings page."""

    page_id: str
    title: str
    subtitle: str
    icon: FluentIconBase | str | None
    order: int
    sections: tuple[SettingsSectionEntry, ...]

    def visible_sections(self) -> tuple[SettingsSectionEntry, ...]:
        """Return sections with at least one visible control."""

        return tuple(
            section
            for section in sorted(self.sections, key=lambda item: item.order)
            if section.visible_controls()
        )


def ordered_settings_pages(
    pages: tuple[SettingsPageEntry, ...],
) -> tuple[SettingsPageEntry, ...]:
    """Return Settings pages in navigation order."""

    return tuple(sorted(pages, key=lambda page: page.order))


__all__ = [
    "SettingsControlEntry",
    "SettingsControlFactory",
    "SettingsPageEntry",
    "SettingsSectionEntry",
    "ordered_settings_pages",
]
