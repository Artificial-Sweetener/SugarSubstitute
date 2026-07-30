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

"""Own runtime canvas-tool contributions and one-shot action execution."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol, TYPE_CHECKING

from substitute.shared.logging.logger import get_logger, log_exception

from .model import CanvasToolContribution, CanvasToolKind
from .palette import CanvasToolPalette
from .registry import CanvasToolRegistry

CanvasToolAction = Callable[[], bool]
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

CanvasToolOptionsFactory = Callable[["QWidget"], "QWidget"]
_LOGGER = get_logger("presentation.canvas.tools.runtime")


@dataclass(frozen=True, slots=True)
class CanvasToolProviderSnapshot:
    """Declare one provider's contributions and collaborators atomically."""

    contributions: tuple[CanvasToolContribution, ...]
    actions: Mapping[str, CanvasToolAction] = field(default_factory=dict)
    options: Mapping[str, CanvasToolOptionsFactory] = field(default_factory=dict)


class CanvasToolProvider(Protocol):
    """Describe a future host provider through inert declarative registration."""

    def canvas_tool_snapshot(self) -> CanvasToolProviderSnapshot:
        """Return one atomic provider snapshot."""


class CanvasToolRuntime:
    """Pair a live contribution catalog with action handlers atomically."""

    def __init__(self) -> None:
        """Create an empty registry, palette, and action-handler catalog."""

        self.registry = CanvasToolRegistry()
        self.palette = CanvasToolPalette(self.registry)
        self._actions: dict[str, CanvasToolAction] = {}
        self._options_factories: dict[str, CanvasToolOptionsFactory] = {}

    def register_mode(self, contribution: CanvasToolContribution) -> None:
        """Register one persistent mode contribution without parallel execution."""

        if contribution.kind is not CanvasToolKind.MODE:
            raise ValueError("register_mode requires a mode contribution")
        self.registry.register(contribution)

    def register_modes(
        self,
        contributions: Iterable[CanvasToolContribution],
    ) -> None:
        """Atomically register persistent mode contributions."""

        modes = tuple(contributions)
        if any(item.kind is not CanvasToolKind.MODE for item in modes):
            raise ValueError("register_modes requires only mode contributions")
        self.registry.register_many(modes)

    def register_action(
        self,
        contribution: CanvasToolContribution,
        action: CanvasToolAction,
    ) -> None:
        """Atomically register one visible action and its execution owner."""

        if contribution.kind is not CanvasToolKind.ACTION:
            raise ValueError("register_action requires an action contribution")
        self.registry.register(contribution)
        self._actions[contribution.tool_id] = action

    def register_options(
        self,
        options_id: str,
        factory: CanvasToolOptionsFactory,
    ) -> None:
        """Register one unique contextual options-surface factory."""

        if not options_id or options_id != options_id.strip():
            raise ValueError("canvas tool options_id must be a non-blank stable ID")
        if options_id in self._options_factories:
            raise ValueError(f"canvas tool options already registered: {options_id}")
        self._options_factories[options_id] = factory

    def create_options_widget(
        self,
        options_id: str,
        parent: QWidget,
    ) -> QWidget | None:
        """Create one registered contextual options surface."""

        factory = self._options_factories.get(options_id)
        return None if factory is None else factory(parent)

    def install_provider(self, provider: CanvasToolProvider) -> None:
        """Install one runtime provider through the stable extension boundary."""

        snapshot = provider.canvas_tool_snapshot()
        contribution_ids = {item.tool_id for item in snapshot.contributions}
        action_ids = set(snapshot.actions)
        if not action_ids.issubset(contribution_ids):
            unknown = ", ".join(sorted(action_ids - contribution_ids))
            raise ValueError(
                f"canvas tool provider actions lack contributions: {unknown}"
            )
        for contribution in snapshot.contributions:
            has_action = contribution.tool_id in action_ids
            if has_action != (contribution.kind is CanvasToolKind.ACTION):
                raise ValueError(
                    "canvas tool provider action metadata does not match contribution "
                    f"kind: {contribution.tool_id}"
                )
        duplicate_options = set(snapshot.options).intersection(self._options_factories)
        if duplicate_options:
            joined = ", ".join(sorted(duplicate_options))
            raise ValueError(f"canvas tool options already registered: {joined}")
        existing_tools = {
            item.tool_id for item in self.registry.snapshot()
        }.intersection(contribution_ids)
        if existing_tools:
            joined = ", ".join(sorted(existing_tools))
            raise ValueError(f"canvas tool already registered: {joined}")
        self._actions.update(snapshot.actions)
        self._options_factories.update(snapshot.options)
        try:
            self.registry.register_many(snapshot.contributions)
        except Exception:
            for tool_id in action_ids:
                self._actions.pop(tool_id, None)
            for options_id in snapshot.options:
                self._options_factories.pop(options_id, None)
            raise

    def unregister(self, tool_id: str) -> bool:
        """Remove one mode or action contribution and any paired handler."""

        if not self.registry.unregister(tool_id):
            return False
        self._actions.pop(tool_id, None)
        return True

    def dispatch_action(self, tool_id: str) -> bool:
        """Execute one registered one-shot action without leaking exceptions to Qt."""

        contribution = self.registry.contribution(tool_id)
        action = self._actions.get(tool_id)
        if (
            contribution is None
            or contribution.kind is not CanvasToolKind.ACTION
            or action is None
        ):
            return False
        try:
            return bool(action())
        except Exception:
            log_exception(
                _LOGGER,
                "Runtime canvas tool action failed",
                tool_id=tool_id,
            )
            return False

    def close(self) -> None:
        """Release palette observation and every action handler."""

        self.palette.close()
        self._actions.clear()
        self._options_factories.clear()


__all__ = [
    "CanvasToolAction",
    "CanvasToolOptionsFactory",
    "CanvasToolProvider",
    "CanvasToolProviderSnapshot",
    "CanvasToolRuntime",
]
