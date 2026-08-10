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

"""Resolve Output navigation control visibility from prepared presentation facts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OutputNavigationVisibility:
    """Describe hierarchy controls available for normal Output navigation."""

    show_scene_selector: bool
    show_source_navigation: bool
    show_set_selector: bool

    @property
    def has_visible_control(self) -> bool:
        """Return whether hierarchy visibility contributes any control."""

        return (
            self.show_scene_selector
            or self.show_source_navigation
            or self.show_set_selector
        )


@dataclass(frozen=True, slots=True)
class SourceNavigationDisplay:
    """Describe the selected responsive source-navigation render mode."""

    source_tabs_collapsed: bool
    show_source_tabs: bool
    show_source_selector: bool


@dataclass(frozen=True, slots=True)
class CompareNavigationVisibility:
    """Describe base-control visibility required for comparison navigation."""

    source_tabs_collapsed: bool
    show_scene_selector: bool
    show_set_selector: bool
    show_source_selector: bool


class OutputCanvasNavigationVisibilityPolicy:
    """Own Output hierarchy and responsive-control visibility decisions."""

    @staticmethod
    def normal(
        *,
        scene_count: int,
        source_count: int,
        set_count: int,
        active_scene_overview: bool,
    ) -> OutputNavigationVisibility:
        """Return normal control availability from independent cardinalities."""

        return OutputNavigationVisibility(
            show_scene_selector=scene_count > 1,
            show_source_navigation=source_count > 1 and not active_scene_overview,
            show_set_selector=set_count > 1 and not active_scene_overview,
        )

    @staticmethod
    def source_display(
        *,
        show_source_navigation: bool,
        has_source_selector: bool,
        expanded_width: int,
        available_width: int,
    ) -> SourceNavigationDisplay:
        """Return whether source navigation renders tabs or a compact selector."""

        collapsed = bool(
            show_source_navigation
            and has_source_selector
            and expanded_width > available_width
        )
        return SourceNavigationDisplay(
            source_tabs_collapsed=collapsed,
            show_source_tabs=show_source_navigation and not collapsed,
            show_source_selector=show_source_navigation and collapsed,
        )

    @staticmethod
    def compare(
        *,
        scene_count: int,
        set_count: int,
    ) -> CompareNavigationVisibility:
        """Return base-control visibility required for comparison navigation."""

        return CompareNavigationVisibility(
            source_tabs_collapsed=True,
            show_scene_selector=scene_count > 1,
            show_set_selector=set_count > 1,
            show_source_selector=True,
        )


__all__ = [
    "CompareNavigationVisibility",
    "OutputCanvasNavigationVisibilityPolicy",
    "OutputNavigationVisibility",
    "SourceNavigationDisplay",
]
