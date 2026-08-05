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

"""Project a runtime tool catalog through one contextual canvas capability set."""

from __future__ import annotations

from collections.abc import Callable
from weakref import ReferenceType, ref

from sugarsubstitute_shared.localization import ApplicationText

from .model import (
    CanvasToolContext,
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolPresentation,
    CanvasToolSurface,
)
from .registry import CanvasToolRegistry, CanvasToolRegistrySubscription

CanvasToolPaletteListener = Callable[[tuple[CanvasToolPresentation, ...]], None]


class CanvasToolPaletteSubscription:
    """Own one removable palette listener without retaining the palette."""

    def __init__(self, palette: CanvasToolPalette, listener_id: int) -> None:
        """Store a weak palette reference and opaque listener identity."""

        self._palette_ref: ReferenceType[CanvasToolPalette] = ref(palette)
        self._listener_id: int | None = listener_id

    def close(self) -> None:
        """Remove the listener idempotently."""

        listener_id = self._listener_id
        if listener_id is None:
            return
        self._listener_id = None
        palette = self._palette_ref()
        if palette is not None:
            palette._unsubscribe(listener_id)


class CanvasToolPalette:
    """Own contextual tool visibility, availability, and authoritative active state."""

    def __init__(self, registry: CanvasToolRegistry) -> None:
        """Observe one runtime registry and initialize an empty context."""

        self._registry = registry
        self._context = CanvasToolContext()
        self._active_tool_id: str | None = None
        self._presentations: tuple[CanvasToolPresentation, ...] = ()
        self._listeners: dict[
            int,
            tuple[CanvasToolPaletteListener, CanvasToolSurface | None],
        ] = {}
        self._next_listener_id = 1
        self._registry_subscription: CanvasToolRegistrySubscription = (
            registry.subscribe(self._registry_changed)
        )
        self._reproject(registry.snapshot())

    @property
    def registry(self) -> CanvasToolRegistry:
        """Return the runtime contribution owner behind this palette."""

        return self._registry

    @property
    def active_tool_id(self) -> str | None:
        """Return the visible enabled persistent mode currently selected."""

        return self._active_tool_id

    def set_context(self, context: CanvasToolContext) -> None:
        """Replace contextual tags and capabilities, then reproject."""

        if context == self._context:
            return
        self._context = context
        self._reproject(self._registry.snapshot())

    def set_active_tool(self, tool_id: str | None) -> bool:
        """Select one enabled persistent mode, or explicitly clear selection."""

        if tool_id is None:
            if self._active_tool_id is None:
                return True
            self._active_tool_id = None
            self._reproject(self._registry.snapshot())
            return True
        presentation = self.presentation_for(tool_id)
        if (
            presentation is None
            or not presentation.enabled
            or presentation.kind is not CanvasToolKind.MODE
        ):
            return False
        if tool_id == self._active_tool_id:
            return True
        self._active_tool_id = tool_id
        self._reproject(self._registry.snapshot())
        return True

    def snapshot(
        self,
        surface: CanvasToolSurface | None = None,
    ) -> tuple[CanvasToolPresentation, ...]:
        """Return the current palette, optionally projected onto one surface."""

        if surface is None:
            return self._presentations
        return tuple(
            presentation
            for presentation in self._presentations
            if surface in presentation.surfaces
        )

    def presentation_for(
        self,
        tool_id: str,
        surface: CanvasToolSurface | None = None,
    ) -> CanvasToolPresentation | None:
        """Return one visible presentation by identity and optional surface."""

        return next(
            (
                presentation
                for presentation in self.snapshot(surface)
                if presentation.tool_id == tool_id
            ),
            None,
        )

    def subscribe(
        self,
        listener: CanvasToolPaletteListener,
        *,
        surface: CanvasToolSurface | None = None,
    ) -> CanvasToolPaletteSubscription:
        """Observe future palette changes through one surface projection."""

        listener_id = self._next_listener_id
        self._next_listener_id += 1
        self._listeners[listener_id] = (listener, surface)
        return CanvasToolPaletteSubscription(self, listener_id)

    def close(self) -> None:
        """Release the registry subscription and all palette listeners."""

        self._registry_subscription.close()
        self._listeners.clear()

    def _registry_changed(
        self,
        contributions: tuple[CanvasToolContribution, ...],
    ) -> None:
        """Reproject one changed runtime contribution catalog."""

        self._reproject(contributions)

    def _reproject(
        self,
        contributions: tuple[CanvasToolContribution, ...],
    ) -> None:
        """Derive visible and enabled state from the current context."""

        visible = tuple(
            contribution
            for contribution in contributions
            if contribution.required_context_tags.issubset(self._context.tags)
        )
        enabled_by_id = {
            contribution.tool_id: contribution.required_capabilities.issubset(
                self._context.capabilities
            )
            for contribution in visible
        }
        if not enabled_by_id.get(self._active_tool_id or "", False):
            self._active_tool_id = None
        presentations = tuple(
            CanvasToolPresentation(
                contribution=contribution,
                enabled=enabled_by_id[contribution.tool_id],
                active=contribution.tool_id == self._active_tool_id,
                unavailable_reason=self._unavailable_reason(contribution),
            )
            for contribution in visible
        )
        if presentations == self._presentations:
            return
        self._presentations = presentations
        for listener, surface in tuple(self._listeners.values()):
            listener(self.snapshot(surface))

    def _unavailable_reason(
        self,
        contribution: CanvasToolContribution,
    ) -> ApplicationText | None:
        """Return the first owned reason for a missing required capability."""

        return next(
            (
                reason
                for capability in contribution.required_capabilities
                if capability not in self._context.capabilities
                and (reason := self._context.denial_for(capability)) is not None
            ),
            None,
        )

    def _unsubscribe(self, listener_id: int) -> None:
        """Remove one opaque palette listener identity."""

        self._listeners.pop(listener_id, None)


__all__ = [
    "CanvasToolPalette",
    "CanvasToolPaletteListener",
    "CanvasToolPaletteSubscription",
]
