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

"""Own the authoritative ordered state of canvas pages hosted by the shell."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from sugarsubstitute_shared.localization import ApplicationText

from substitute.presentation.canvas.host.floating_canvas_window import (
    FloatingCanvasChrome,
)

if TYPE_CHECKING:
    from substitute.presentation.canvas.host.floating_canvas_window import (
        FloatingCanvasWindow,
    )


FloatingChromeFactory = Callable[[], FloatingCanvasChrome | None]


@dataclass(frozen=True, slots=True)
class CanvasHostPage:
    """Describe one canvas page and its host-level lifecycle policy."""

    route_key: str
    title: ApplicationText
    widget: QWidget
    floating_chrome_factory: FloatingChromeFactory | None = None
    default_available: bool = True
    unavailable_reason: ApplicationText = ""
    fallback_route_key: str | None = None


@dataclass(slots=True)
class CanvasHostEntry:
    """Store all mutable host state for one configured canvas page."""

    page: CanvasHostPage
    wrapper: QWidget
    available: bool
    floating_window: FloatingCanvasWindow | None = None

    @property
    def route_key(self) -> str:
        """Return the stable route key owned by the page definition."""

        return self.page.route_key

    @property
    def attached(self) -> bool:
        """Return whether the page currently belongs to the docked host."""

        return self.floating_window is None

    @property
    def selectable(self) -> bool:
        """Return whether the page can appear in the docked selector and stack."""

        return self.attached and self.available


class CanvasHostState:
    """Own canvas ordering, availability, attachment, and docked selection."""

    def __init__(self, entries: Sequence[CanvasHostEntry]) -> None:
        """Create state from unique entries in their durable display order."""

        self._entries: dict[str, CanvasHostEntry] = {}
        for entry in entries:
            route_key = entry.route_key
            if route_key in self._entries:
                raise ValueError(f"Duplicate canvas route key: {route_key}")
            self._entries[route_key] = entry
        selectable_entries = self.selectable_entries()
        first_selectable = selectable_entries[0] if selectable_entries else None
        self._active_route_key = (
            first_selectable.route_key if first_selectable is not None else None
        )

    @property
    def active_route_key(self) -> str | None:
        """Return the active docked canvas route key, if one exists."""

        return self._active_route_key

    def __iter__(self) -> Iterator[CanvasHostEntry]:
        """Iterate canvas entries in their authoritative durable order."""

        return iter(self._entries.values())

    def entry(self, route_key: str) -> CanvasHostEntry | None:
        """Return the entry for a route key when it is configured."""

        return self._entries.get(route_key)

    def require_entry(self, route_key: str) -> CanvasHostEntry:
        """Return a configured entry or raise for an invalid internal route."""

        entry = self.entry(route_key)
        if entry is None:
            raise KeyError(route_key)
        return entry

    def selectable_entries(self) -> tuple[CanvasHostEntry, ...]:
        """Return attached and available entries in durable display order."""

        return tuple(entry for entry in self if entry.selectable)

    def select(self, route_key: str) -> bool:
        """Select an attached available canvas and report whether it changed."""

        entry = self.entry(route_key)
        if entry is None or not entry.selectable:
            return False
        changed = self._active_route_key != route_key
        self._active_route_key = route_key
        return changed

    def select_fallback(
        self,
        *,
        preferred_route_key: str | None = None,
        excluded_route_key: str | None = None,
    ) -> str | None:
        """Select the preferred or first remaining docked canvas."""

        candidates = tuple(
            entry
            for entry in self.selectable_entries()
            if entry.route_key != excluded_route_key
        )
        preferred = self.entry(preferred_route_key) if preferred_route_key else None
        if (
            preferred is not None
            and preferred.selectable
            and preferred.route_key != excluded_route_key
        ):
            self._active_route_key = preferred.route_key
        elif candidates:
            self._active_route_key = candidates[0].route_key
        else:
            self._active_route_key = None
        return self._active_route_key

    def set_available(
        self,
        route_key: str,
        available: bool,
        *,
        fallback_route_key: str | None = None,
    ) -> bool:
        """Apply availability and keep the docked selection valid."""

        entry = self.entry(route_key)
        if entry is None:
            return False
        changed = entry.available != available
        entry.available = available
        if not available and self._active_route_key == route_key:
            self.select_fallback(
                preferred_route_key=fallback_route_key,
                excluded_route_key=route_key,
            )
        elif available and self._active_route_key is None and entry.attached:
            self._active_route_key = route_key
        return changed

    def prepare_detach(self, route_key: str) -> bool:
        """Move selection away from a page before it leaves the docked host."""

        entry = self.entry(route_key)
        if entry is None or not entry.selectable:
            return False
        if self._active_route_key == route_key:
            self.select_fallback(excluded_route_key=route_key)
        return True

    def complete_detach(
        self,
        route_key: str,
        floating_window: FloatingCanvasWindow,
    ) -> None:
        """Record the floating window as the page's sole attachment owner."""

        entry = self.require_entry(route_key)
        if entry.floating_window is not None:
            raise ValueError(f"Canvas is already detached: {route_key}")
        entry.floating_window = floating_window

    def complete_attach(self, route_key: str) -> bool:
        """Clear floating ownership and activate an available redocked page."""

        entry = self.entry(route_key)
        if entry is None or entry.floating_window is None:
            return False
        entry.floating_window = None
        if not entry.available:
            return False
        self._active_route_key = route_key
        return True

    def release_floating_window(
        self,
        route_key: str,
        floating_window: FloatingCanvasWindow,
    ) -> bool:
        """Clear one exact floating owner without changing docked selection."""

        entry = self.entry(route_key)
        if entry is None or entry.floating_window is not floating_window:
            return False
        entry.floating_window = None
        return True

    def insertion_index(self, route_key: str) -> int:
        """Return the stack position for a selectable route in durable order."""

        selectable_keys = tuple(entry.route_key for entry in self.selectable_entries())
        try:
            return selectable_keys.index(route_key)
        except ValueError:
            return -1


__all__ = [
    "CanvasHostEntry",
    "CanvasHostPage",
    "CanvasHostState",
    "FloatingChromeFactory",
]
