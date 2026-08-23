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

"""Provide narrow tab-stack doubles for loaded-cube surface tests."""

from __future__ import annotations


class _PresentationTab:
    """Expose a route key for stack presentation tests."""

    def __init__(self, route_key: str) -> None:
        """Store the route key."""

        self._route_key = route_key

    def routeKey(self) -> str:
        """Return the cube alias route key."""

        return self._route_key

    def setRouteKey(self, route_key: str) -> None:
        """Replace the cube alias route key."""

        self._route_key = route_key


class _PresentationStack:
    """Collect tab presentation updates for one stack tab."""

    def __init__(self, *route_keys: str) -> None:
        """Create route-keyed tab items."""

        self._items = [_PresentationTab(route_key) for route_key in route_keys]
        self.itemMap: dict[str, _PresentationTab] = {
            item.routeKey(): item for item in self._items
        }
        self.presentations: list[dict[str, object]] = []
        self.icons: list[tuple[int, object]] = []
        self.issue_severities: list[tuple[str, str | None]] = []
        self.bypassed: list[tuple[int, bool]] = []

    def count(self) -> int:
        """Return the number of test tabs."""

        return len(self._items)

    def tabItem(self, index: int) -> _PresentationTab:
        """Return one tab item by index."""

        return self._items[index]

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Record a tab presentation update."""

        self.presentations.append(
            {
                "index": index,
                "primary_text": primary_text,
                "secondary_text": secondary_text,
                "tooltip_text": tooltip_text,
            }
        )

    def setTabIcon(self, index: int, icon: object) -> None:
        """Record a tab icon update."""

        self.icons.append((index, icon))

    def setTabIssueSeverity(self, route_key: str, severity: str | None) -> None:
        """Record a tab issue severity update."""

        self.issue_severities.append((route_key, severity))

    def setTabBypassed(self, index: int, bypassed: bool) -> None:
        """Record cube bypass presentation state."""

        self.bypassed.append((index, bypassed))
