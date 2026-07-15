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

"""Index item ids by reusable folder route paths."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FolderRouteEntry:
    """Describe one item participating in folder route filtering."""

    item_id: str
    folder_path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FolderRouteChild:
    """Describe one immediate child route displayed by a route bar."""

    route: tuple[str, ...]
    label: str
    item_count: int


class FolderRouteTree:
    """Index item ids by normalized folder route for route filtering."""

    def __init__(self, entries: tuple[FolderRouteEntry, ...]) -> None:
        """Build child and descendant indexes for the supplied item entries."""

        self._entries = tuple(
            FolderRouteEntry(entry.item_id, normalize_folder_route(entry.folder_path))
            for entry in entries
        )
        self._child_routes_by_parent: dict[
            tuple[str, ...], dict[tuple[str, ...], str]
        ] = defaultdict(dict)
        self._item_ids_by_route: dict[tuple[str, ...], list[str]] = defaultdict(list)
        self._build_indexes()

    def children(self, route: tuple[str, ...]) -> tuple[FolderRouteChild, ...]:
        """Return immediate child routes for one normalized route."""

        normalized_route = normalize_folder_route(route)
        child_routes = self._child_routes_by_parent.get(normalized_route, {})
        children = [
            FolderRouteChild(
                route=child_route,
                label=label,
                item_count=len(self._item_ids_by_route.get(child_route, ())),
            )
            for child_route, label in child_routes.items()
        ]
        return tuple(
            sorted(
                children,
                key=lambda child: (child.label.casefold(), child.label, child.route),
            )
        )

    def item_ids_under(self, route: tuple[str, ...]) -> tuple[str, ...]:
        """Return item ids directly or indirectly contained by one route."""

        normalized_route = normalize_folder_route(route)
        return tuple(self._item_ids_by_route.get(normalized_route, ()))

    def breadcrumb_labels(self, route: tuple[str, ...]) -> tuple[str, ...]:
        """Return display labels for a normalized route including the root label."""

        normalized_route = normalize_folder_route(route)
        return ("All", *normalized_route)

    def _build_indexes(self) -> None:
        """Populate route maps while preserving original entry order."""

        for entry in self._entries:
            route = entry.folder_path
            for depth in range(len(route) + 1):
                self._item_ids_by_route[route[:depth]].append(entry.item_id)
            for depth, label in enumerate(route):
                parent_route = route[:depth]
                child_route = route[: depth + 1]
                self._child_routes_by_parent[parent_route].setdefault(
                    child_route,
                    label,
                )


def normalize_folder_route(
    folder_path: str | tuple[str, ...] | None,
) -> tuple[str, ...]:
    """Return a stable route tuple for a folder path."""

    if folder_path is None:
        return ()
    if isinstance(folder_path, tuple):
        segments = folder_path
    else:
        cleaned = folder_path.strip().replace("\\", "/")
        if cleaned in {"", "."}:
            return ()
        segments = tuple(cleaned.split("/"))
    return tuple(
        segment
        for segment in (part.strip() for part in segments)
        if segment and segment != "."
    )


def folder_route_from_item_path(relative_path: str | None) -> tuple[str, ...]:
    """Return folder route segments from a relative item file path."""

    normalized_path = normalize_folder_route(relative_path)
    if not normalized_path:
        return ()
    return normalized_path[:-1]


__all__ = [
    "FolderRouteChild",
    "FolderRouteEntry",
    "FolderRouteTree",
    "folder_route_from_item_path",
    "normalize_folder_route",
]
