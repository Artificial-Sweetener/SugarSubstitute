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

"""Own process-local pending restart requirement deltas."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from substitute.application.restart_requirements.models import (
    RestartRequirementItem,
    RestartRequirementSnapshot,
    RestartScope,
)

RestartRequirementObserver = Callable[[RestartRequirementSnapshot], None]


class RestartRequirementService:
    """Collect saved settings that need a restart to become active."""

    def __init__(self) -> None:
        """Initialize an empty process-local restart cart."""

        self._items: OrderedDict[str, RestartRequirementItem] = OrderedDict()
        self._observers: list[RestartRequirementObserver] = []

    def add_observer(self, observer: RestartRequirementObserver) -> None:
        """Register a callback that receives every changed restart snapshot."""

        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: RestartRequirementObserver) -> None:
        """Remove a previously registered snapshot observer."""

        if observer in self._observers:
            self._observers.remove(observer)

    def register_delta(
        self,
        *,
        key: str,
        label: str,
        active_value: str,
        saved_value: str,
        scope: RestartScope,
        detail: str | None = None,
    ) -> RestartRequirementSnapshot:
        """Add, update, or clear one restart delta from active and saved values."""

        normalized_key = key.strip()
        if saved_value == active_value:
            return self.clear(normalized_key)
        item = RestartRequirementItem(
            key=normalized_key,
            label=label.strip(),
            active_value=active_value,
            saved_value=saved_value,
            scope=scope,
            detail=detail.strip() if detail is not None and detail.strip() else None,
        )
        self._items[normalized_key] = item
        return self._changed_snapshot()

    def clear(self, key: str) -> RestartRequirementSnapshot:
        """Remove one pending restart delta when it is resolved."""

        self._items.pop(key.strip(), None)
        return self._changed_snapshot()

    def snapshot(self) -> RestartRequirementSnapshot:
        """Return the current pending restart cart."""

        items = tuple(self._items.values())
        required_scope = max(
            (item.scope for item in items),
            default=RestartScope.NONE,
        )
        return RestartRequirementSnapshot(
            items=items,
            required_scope=required_scope,
        )

    def _changed_snapshot(self) -> RestartRequirementSnapshot:
        """Return and publish the current snapshot after a mutation."""

        snapshot = self.snapshot()
        for observer in tuple(self._observers):
            observer(snapshot)
        return snapshot
