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

from collections.abc import Callable, Iterable

from substitute.shared.logging.logger import get_logger, log_exception

from .model import CanvasToolContribution, CanvasToolKind
from .palette import CanvasToolPalette
from .registry import CanvasToolRegistry

CanvasToolAction = Callable[[], bool]
_LOGGER = get_logger("presentation.canvas.tools.runtime")


class CanvasToolRuntime:
    """Pair a live contribution catalog with action handlers atomically."""

    def __init__(self) -> None:
        """Create an empty registry, palette, and action-handler catalog."""

        self.registry = CanvasToolRegistry()
        self.palette = CanvasToolPalette(self.registry)
        self._actions: dict[str, CanvasToolAction] = {}

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


__all__ = ["CanvasToolAction", "CanvasToolRuntime"]
