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

"""Own the mutable runtime catalog of canvas-tool contributions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from weakref import ReferenceType, ref

from .model import CanvasToolContribution

CanvasToolRegistryListener = Callable[[tuple[CanvasToolContribution, ...]], None]


class CanvasToolRegistrySubscription:
    """Own one removable registry listener without retaining the registry."""

    def __init__(self, registry: CanvasToolRegistry, listener_id: int) -> None:
        """Store a weak registry reference and opaque listener identity."""

        self._registry_ref: ReferenceType[CanvasToolRegistry] = ref(registry)
        self._listener_id: int | None = listener_id

    def close(self) -> None:
        """Remove the listener idempotently."""

        listener_id = self._listener_id
        if listener_id is None:
            return
        self._listener_id = None
        registry = self._registry_ref()
        if registry is not None:
            registry._unsubscribe(listener_id)


class CanvasToolRegistry:
    """Register and remove inert tool contributions while the app is running."""

    def __init__(self) -> None:
        """Initialize an empty contribution catalog and listener set."""

        self._tools: dict[str, CanvasToolContribution] = {}
        self._listeners: dict[int, CanvasToolRegistryListener] = {}
        self._next_listener_id = 1

    def register(self, contribution: CanvasToolContribution) -> None:
        """Add one unique contribution and publish the resulting catalog."""

        self.register_many((contribution,))

    def register_many(
        self,
        contributions: Iterable[CanvasToolContribution],
    ) -> None:
        """Atomically add unique contributions and publish one catalog change."""

        additions = tuple(contributions)
        addition_ids = tuple(item.tool_id for item in additions)
        counts = Counter(addition_ids)
        duplicate_ids = {
            tool_id
            for tool_id, count in counts.items()
            if count > 1 or tool_id in self._tools
        }
        if duplicate_ids:
            joined = ", ".join(sorted(duplicate_ids))
            raise ValueError(f"canvas tool already registered: {joined}")
        if not additions:
            return
        self._tools.update((item.tool_id, item) for item in additions)
        self._notify()

    def unregister(self, tool_id: str) -> bool:
        """Remove one contribution and publish whether the catalog changed."""

        if self._tools.pop(tool_id, None) is None:
            return False
        self._notify()
        return True

    def snapshot(self) -> tuple[CanvasToolContribution, ...]:
        """Return contributions in deterministic host-defined order."""

        return tuple(
            sorted(
                self._tools.values(),
                key=lambda contribution: (
                    contribution.order,
                    contribution.tool_id,
                ),
            )
        )

    def contribution(self, tool_id: str) -> CanvasToolContribution | None:
        """Return one current contribution by stable identity."""

        return self._tools.get(tool_id)

    def subscribe(
        self,
        listener: CanvasToolRegistryListener,
    ) -> CanvasToolRegistrySubscription:
        """Observe future catalog changes through an owned subscription."""

        listener_id = self._next_listener_id
        self._next_listener_id += 1
        self._listeners[listener_id] = listener
        return CanvasToolRegistrySubscription(self, listener_id)

    def _unsubscribe(self, listener_id: int) -> None:
        """Remove one opaque listener identity."""

        self._listeners.pop(listener_id, None)

    def _notify(self) -> None:
        """Publish one immutable snapshot safely across reentrant mutations."""

        snapshot = self.snapshot()
        for listener in tuple(self._listeners.values()):
            listener(snapshot)


__all__ = [
    "CanvasToolRegistry",
    "CanvasToolRegistryListener",
    "CanvasToolRegistrySubscription",
]
