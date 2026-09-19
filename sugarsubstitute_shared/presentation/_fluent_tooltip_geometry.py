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

"""Calculate bounded QFluent tooltip geometry for the presentation owner."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize
from PySide6.QtGui import QCursor, QGuiApplication

DEFAULT_CURSOR_OFFSET = QPoint(14, 18)
_SCREEN_MARGIN = 4
_MAXIMUM_WIDTH = 420
_MINIMUM_CONTENT_WIDTH = 120


def cursor_tooltip_position(
    *,
    cursor_global_pos: QPoint,
    tooltip_size: QSize,
    offset: QPoint | None = None,
    screen_geometry: QRect | None = None,
) -> QPoint:
    """Return a cursor-relative tooltip position clamped to the active screen."""

    geometry = screen_geometry or _screen_geometry(cursor_global_pos)
    desired = cursor_global_pos + (offset or DEFAULT_CURSOR_OFFSET)
    maximum_x = max(
        geometry.left(),
        geometry.right() - tooltip_size.width() - _SCREEN_MARGIN,
    )
    maximum_y = max(
        geometry.top(),
        geometry.bottom() - tooltip_size.height() - _SCREEN_MARGIN,
    )
    return QPoint(
        min(max(desired.x(), geometry.left()), maximum_x),
        min(max(desired.y(), geometry.top()), maximum_y),
    )


def configure_tooltip_bounds(tooltip: object) -> None:
    """Apply bounded wrapping to one QFluent tooltip widget."""

    _set_maximum_width(tooltip, _MAXIMUM_WIDTH)
    container = getattr(tooltip, "container", None)
    container_width = _inner_width(
        _MAXIMUM_WIDTH,
        _horizontal_margins(_layout(tooltip)),
    )
    if container is not None:
        _set_maximum_width(container, container_width)
    label = getattr(tooltip, "label", None)
    if label is None:
        return
    label.setWordWrap(True)
    _set_maximum_width(
        label,
        _inner_width(
            container_width,
            _horizontal_margins(getattr(tooltip, "containerLayout", None)),
        ),
    )


def event_global_position(watched: QObject, event: QEvent) -> QPoint:
    """Resolve the latest global cursor position from Qt event APIs."""

    global_position = getattr(event, "globalPosition", None)
    if callable(global_position):
        return cast(QPoint, global_position().toPoint())
    global_pos = getattr(event, "globalPos", None)
    if callable(global_pos):
        return cast(QPoint, global_pos())
    local_position = getattr(event, "position", None)
    map_to_global = getattr(watched, "mapToGlobal", None)
    if callable(local_position) and callable(map_to_global):
        return cast(QPoint, map_to_global(local_position().toPoint()))
    return QCursor.pos()


def _screen_geometry(cursor_position: QPoint) -> QRect:
    """Return available geometry for the screen containing the cursor."""

    screen = (
        QGuiApplication.screenAt(cursor_position) or QGuiApplication.primaryScreen()
    )
    return screen.availableGeometry() if screen is not None else QRect(0, 0, 1920, 1080)


def _layout(widget: object) -> object | None:
    """Return a widget layout when exposed."""

    getter = getattr(widget, "layout", None)
    return getter() if callable(getter) else None


def _horizontal_margins(layout: object | None) -> int:
    """Return left and right layout margins."""

    if layout is None:
        return 0
    getter = getattr(layout, "contentsMargins", None)
    if not callable(getter):
        return 0
    margins = getter()
    return int(margins.left()) + int(margins.right())


def _inner_width(width: int, margins: int) -> int:
    """Return bounded content width after layout margins."""

    return max(_MINIMUM_CONTENT_WIDTH, width - margins)


def _set_maximum_width(widget: object, width: int) -> None:
    """Set a maximum width on a QFluent tooltip component."""

    setter = getattr(widget, "setMaximumWidth", None)
    if callable(setter):
        setter(width)


__all__ = ["cursor_tooltip_position"]
