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

"""Resolve cube reveal geometry in editor scroll-content coordinates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

from PySide6.QtCore import QPoint
from shiboken6 import isValid


class RevealPointProtocol(Protocol):
    """Describe point-like objects returned by widget mapping."""

    def y(self) -> int:
        """Return the vertical coordinate."""


class RevealWidgetProtocol(Protocol):
    """Describe widget geometry needed by cube reveal resolution."""

    def height(self) -> int:
        """Return widget height."""

    def mapTo(self, parent: object, point: object) -> RevealPointProtocol:  # noqa: N802
        """Map one point into the supplied parent coordinate space."""


class RevealViewportProtocol(Protocol):
    """Describe the viewport geometry consumed by reveal resolution."""

    def height(self) -> int:
        """Return viewport height."""


class RevealScrollBarProtocol(Protocol):
    """Describe scrollbar limits used by reveal readiness."""

    def maximum(self) -> int:
        """Return the maximum scrollbar value."""


class CubeRevealGeometryScrollPort(Protocol):
    """Describe the scroll-coordinate conversions used by reveal geometry."""

    def widget(self) -> object | None:
        """Return the scroll content widget."""

    def viewport(self) -> RevealViewportProtocol:
        """Return the scroll viewport."""

    def verticalScrollBar(self) -> RevealScrollBarProtocol:  # noqa: N802
        """Return the vertical scrollbar."""

    def visible_content_top(self) -> int:
        """Return the visible content top coordinate."""

    def visible_content_bottom(self) -> int:
        """Return the visible content bottom coordinate."""

    def content_y_to_scroll_value(self, content_y: int) -> int:
        """Convert content-space y to a clamped scroll value."""


class CubeRevealGeometryHost(Protocol):
    """Describe mounted cube geometry needed by the resolver."""

    scroll: CubeRevealGeometryScrollPort
    cube_sections: Mapping[str, object]
    _stack_order: Sequence[str] | None


class CubeRevealGeometryResolver:
    """Resolve stable reveal targets without owning navigation sessions."""

    def __init__(self, host: CubeRevealGeometryHost) -> None:
        """Store the mounted view geometry host."""

        self._host = host

    def readiness_signature(self, route_key: str) -> tuple[int, ...] | None:
        """Return metrics that must stabilize before loaded-cube navigation."""

        cube_widget = self.cube_widget(route_key)
        scroll_content = self._host.scroll.widget()
        if (
            cube_widget is None
            or not isValid(cube_widget)
            or scroll_content is None
            or cube_widget.height() <= 0
        ):
            return None
        target_value = self.scroll_target_value(route_key)
        target_content_y = self.scroll_target_content_y(route_key)
        if target_value is None or target_content_y is None:
            return None
        overscroll_top = getattr(self._host.scroll, "overscroll_top", None)
        top_overscroll = int(overscroll_top()) if callable(overscroll_top) else 0
        unclamped_target_value = max(0, target_content_y + top_overscroll)
        maximum_value = int(self._host.scroll.verticalScrollBar().maximum())
        height_getter = getattr(scroll_content, "height", None)
        content_height = int(height_getter()) if callable(height_getter) else 0
        viewport_height = int(self._host.scroll.viewport().height())
        return (
            unclamped_target_value,
            maximum_value,
            int(target_value),
            int(cube_widget.height()),
            content_height,
            viewport_height,
        )

    def is_mostly_visible(
        self,
        route_key: str,
        *,
        visibility_threshold: float = 0.65,
    ) -> bool:
        """Return whether the requested cube section is already mostly visible."""

        cube_widget = self.cube_widget(route_key)
        scroll_content = self._host.scroll.widget()
        if (
            cube_widget is None
            or not isValid(cube_widget)
            or scroll_content is None
            or cube_widget.height() <= 0
        ):
            return False
        visible_top = self._host.scroll.visible_content_top()
        visible_bottom = self._host.scroll.visible_content_bottom()
        widget_top = cube_widget.mapTo(scroll_content, QPoint(0, 0)).y()
        widget_bottom = widget_top + cube_widget.height()
        visible_height = max(
            0,
            min(widget_bottom, visible_bottom) - max(widget_top, visible_top),
        )
        return (visible_height / max(1, cube_widget.height())) >= visibility_threshold

    def anchor_content_y(self, route_key: str) -> int | None:
        """Return the content-space title/header anchor for one cube section."""

        cube_widget = self.cube_widget(route_key)
        scroll_content = self._host.scroll.widget()
        if cube_widget is None or scroll_content is None:
            return None
        anchor_y = 0
        reveal_anchor_y = getattr(cube_widget, "reveal_anchor_y", None)
        if callable(reveal_anchor_y):
            try:
                anchor_y = max(0, int(reveal_anchor_y()))
            except (RuntimeError, TypeError, ValueError):
                anchor_y = 0
        try:
            return cube_widget.mapTo(scroll_content, QPoint(0, anchor_y)).y()
        except (RuntimeError, TypeError, AttributeError):
            return None

    def header_viewport_anchor_y(self) -> int:
        """Return where cube title/header centers should land in the viewport."""

        for route_key in self._host._stack_order or ():
            anchor_y = self.anchor_content_y(route_key)
            if anchor_y is not None:
                return max(0, anchor_y)
        try:
            return max(0, self._host.scroll.viewport().height() // 2)
        except (RuntimeError, AttributeError):
            return 0

    def scroll_target_value(self, route_key: str) -> int | None:
        """Return the scroll value that aligns a cube's header anchor."""

        content_target_y = self.scroll_target_content_y(route_key)
        if content_target_y is None:
            return None
        return self._host.scroll.content_y_to_scroll_value(content_target_y)

    def scroll_target_content_y(self, route_key: str) -> int | None:
        """Return the unclamped content-space target for header alignment."""

        anchor_y = self.anchor_content_y(route_key)
        if anchor_y is None:
            return None
        return anchor_y - self.header_viewport_anchor_y()

    def cube_widget(self, route_key: str) -> RevealWidgetProtocol | None:
        """Return one mounted cube through the geometry protocol."""

        widget = self._host.cube_sections.get(route_key)
        return cast(RevealWidgetProtocol, widget) if widget is not None else None


__all__ = ["CubeRevealGeometryHost", "CubeRevealGeometryResolver"]
