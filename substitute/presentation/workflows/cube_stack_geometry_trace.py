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

"""Provide opt-in geometry tracing for cube-stack animation diagnostics."""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QPoint

from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("presentation.workflows.cube_stack_geometry_trace")


def log_cube_stack_transition_frame(
    *,
    stack: Any,
    stack_width: int,
    item_width: int,
    compact_progress: float,
) -> None:
    """Log one stack-level transition frame with local and global geometry."""

    if not _geometry_trace_enabled():
        return
    first_item = _first_item(stack)
    context = {
        "compact_progress": f"{compact_progress:.4f}",
        "stack_global_x": _global_x(stack),
        "stack_global_y": _global_y(stack),
        "stack_height": _height(stack),
        "stack_local_x": _local_x(stack),
        "stack_local_y": _local_y(stack),
        "stack_width": stack_width,
        "item_width": item_width,
    }
    if first_item is not None:
        context.update(
            {
                "first_item_global_x": _global_x(first_item),
                "first_item_global_y": _global_y(first_item),
                "first_item_height": _height(first_item),
                "first_item_local_x": _local_x(first_item),
                "first_item_local_y": _local_y(first_item),
                "first_item_route": _route_key(first_item),
                "first_item_width": _width(first_item),
            }
        )
    add_placeholder = getattr(stack, "addPlaceholder", None)
    if add_placeholder is not None:
        add_placeholder_global_x = _global_x(add_placeholder)
        stack_global_x = _global_x(stack)
        context.update(
            {
                "add_placeholder_center_from_stack_left": (
                    add_placeholder_global_x
                    + _center_offset_x(add_placeholder)
                    - stack_global_x
                ),
                "add_placeholder_global_x": add_placeholder_global_x,
                "add_placeholder_height": _height(add_placeholder),
                "add_placeholder_local_x": _local_x(add_placeholder),
                "add_placeholder_width": _width(add_placeholder),
            }
        )

    log_debug(_LOGGER, "Cube stack transition frame", **context)


def log_cube_item_icon_paint(
    *,
    item: Any,
    icon_x: int,
    icon_y: int,
    icon_size: int,
) -> None:
    """Log one cube-item icon paint rect in local and global coordinates."""

    if not _geometry_trace_enabled():
        return
    icon_global = _map_to_global(item, QPoint(icon_x, icon_y))
    context = {
        "compact": _call_bool(item, "isCompact"),
        "compact_progress": f"{_call_float(item, 'compact_progress'):.4f}",
        "icon_global_x": icon_global.x(),
        "icon_global_y": icon_global.y(),
        "icon_local_x": icon_x,
        "icon_local_y": icon_y,
        "icon_size": icon_size,
        "item_global_x": _global_x(item),
        "item_global_y": _global_y(item),
        "item_height": _height(item),
        "item_local_x": _local_x(item),
        "item_local_y": _local_y(item),
        "item_route": _route_key(item),
        "item_text": _call_str(item, "text"),
        "item_width": _width(item),
        "parent_global_x": _global_x(_parent_widget(item)),
        "transition_active": bool(getattr(item, "_compact_transition_active", False)),
    }
    log_debug(_LOGGER, "Cube item icon paint", **context)


def _geometry_trace_enabled() -> bool:
    """Return whether detailed cube-stack geometry tracing should be emitted."""

    return _LOGGER.isEnabledFor(logging.DEBUG)


def _first_item(stack: Any) -> Any | None:
    """Return the first stack item when available."""

    items = getattr(stack, "items", [])
    if not items:
        return None
    return items[0]


def _route_key(item: Any) -> str:
    """Return a stable route key label for one item."""

    return _call_str(item, "routeKey")


def _call_bool(target: Any, method_name: str) -> bool:
    """Call a boolean method for trace context."""

    method = getattr(target, method_name, None)
    return bool(method()) if callable(method) else False


def _call_float(target: Any, method_name: str) -> float:
    """Call a float-returning method for trace context."""

    method = getattr(target, method_name, None)
    if not callable(method):
        return 0.0
    return float(method())


def _call_str(target: Any, method_name: str) -> str:
    """Call a string-returning method for trace context."""

    method = getattr(target, method_name, None)
    if not callable(method):
        return ""
    value = method()
    return "" if value is None else str(value)


def _parent_widget(widget: Any) -> Any | None:
    """Return one widget's parent widget when available."""

    parent_widget = getattr(widget, "parentWidget", None)
    return parent_widget() if callable(parent_widget) else None


def _width(widget: Any) -> int:
    """Return a widget width for trace context."""

    width = getattr(widget, "width", None)
    return int(width()) if callable(width) else 0


def _center_offset_x(widget: Any) -> int:
    """Return the Qt rect-center X offset for one widget."""

    return max(0, int((_width(widget) - 1) / 2))


def _height(widget: Any) -> int:
    """Return a widget height for trace context."""

    height = getattr(widget, "height", None)
    return int(height()) if callable(height) else 0


def _local_x(widget: Any) -> int:
    """Return a widget local X position for trace context."""

    x = getattr(widget, "x", None)
    return int(x()) if callable(x) else 0


def _local_y(widget: Any) -> int:
    """Return a widget local Y position for trace context."""

    y = getattr(widget, "y", None)
    return int(y()) if callable(y) else 0


def _global_x(widget: Any | None) -> int:
    """Return global widget X position for trace context."""

    if widget is None:
        return 0
    return _map_to_global(widget, QPoint(0, 0)).x()


def _global_y(widget: Any | None) -> int:
    """Return global widget Y position for trace context."""

    if widget is None:
        return 0
    return _map_to_global(widget, QPoint(0, 0)).y()


def _map_to_global(widget: Any, point: QPoint) -> QPoint:
    """Map a point to global coordinates when the widget supports it."""

    map_to_global = getattr(widget, "mapToGlobal", None)
    if not callable(map_to_global):
        return point
    mapped = map_to_global(point)
    return mapped if isinstance(mapped, QPoint) else point


__all__ = [
    "log_cube_item_icon_paint",
    "log_cube_stack_transition_frame",
]
