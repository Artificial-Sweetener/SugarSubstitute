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

"""Define live node-definition lookup contract for editor option resolution."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from substitute.domain.common import JsonObject


@dataclass(frozen=True, slots=True)
class NodeDefinitionRefreshEvent:
    """Describe one completed live node-definition cache refresh."""

    node_class: str
    available: bool


@dataclass(frozen=True, slots=True)
class NodeDefinitionHydrationResult:
    """Describe foreground node-definition hydration results."""

    requested: tuple[str, ...]
    available: tuple[str, ...]
    unavailable: tuple[str, ...]


@runtime_checkable
class NodeDefinitionGateway(Protocol):
    """Return normalized live Comfy node definitions for one node class."""

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return cached node-class metadata and allow cache misses to refresh later."""

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Synchronously fetch required node-class metadata or return an empty mapping."""


@runtime_checkable
class NodeDefinitionHydrator(Protocol):
    """Fetch missing node definitions before correctness-sensitive projection."""

    def ensure_node_definitions(
        self,
        node_classes: Iterable[str],
    ) -> NodeDefinitionHydrationResult:
        """Synchronously fetch missing node definitions and return availability."""


class NodeDefinitionRefreshObserver(Protocol):
    """Receive live node-definition cache refresh notifications."""

    def __call__(self, event: NodeDefinitionRefreshEvent) -> None:
        """Handle one completed node-definition refresh."""


@runtime_checkable
class ObservableNodeDefinitionGateway(NodeDefinitionGateway, Protocol):
    """Support observer registration for completed node-definition refreshes."""

    def add_refresh_observer(
        self,
        observer: NodeDefinitionRefreshObserver,
    ) -> Callable[[], None]:
        """Register an observer and return an unsubscribe callback."""


__all__ = [
    "NodeDefinitionGateway",
    "NodeDefinitionHydrationResult",
    "NodeDefinitionHydrator",
    "NodeDefinitionRefreshEvent",
    "NodeDefinitionRefreshObserver",
    "ObservableNodeDefinitionGateway",
]
