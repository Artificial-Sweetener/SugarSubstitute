#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Own every QFluent tooltip installed by SugarSubstitute presentation code."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ToolTipFilter, ToolTipPosition  # type: ignore[import-untyped]

_FILTER_ATTRIBUTE = "_sugarsubstitute_fluent_tooltip_filter"
_DEFAULT_CURSOR_OFFSET = QPoint(14, 18)
_SCREEN_MARGIN = 4
_MAXIMUM_WIDTH = 420
_MINIMUM_CONTENT_WIDTH = 120


class ToolTipTarget(Protocol):
    """Describe an object exposing Qt's tooltip property."""

    def setToolTip(self, text: str) -> None:
        """Set tooltip text."""


ToolTipProvider = Callable[[object, object], str | None]


class _FluentToolTip(Protocol):
    """Describe the QFluent tooltip widget surface extended by this adapter."""

    def adjustSize(self) -> None:
        """Refresh tooltip geometry."""

    def size(self) -> QSize:
        """Return current tooltip size."""

    def move(self, position: QPoint) -> None:
        """Move the tooltip to a global position."""


class FluentToolTipFilter(ToolTipFilter):  # type: ignore[misc]
    """Extend QFluent's filter with app-required cursor and dynamic behavior."""

    def __init__(
        self,
        owner: QWidget,
        *,
        show_delay_ms: int = 300,
        position: ToolTipPosition = ToolTipPosition.TOP,
        cursor_anchor: bool = False,
        cursor_offset: QPoint | None = None,
        show_when_disabled: bool = False,
        tooltip_provider: ToolTipProvider | None = None,
    ) -> None:
        """Configure one QFluent filter without creating a parallel tooltip widget."""

        super().__init__(owner, show_delay_ms, position)
        self._show_delay_ms = show_delay_ms
        self._cursor_anchor = cursor_anchor
        self._cursor_offset = cursor_offset or _DEFAULT_CURSOR_OFFSET
        self._show_when_disabled = show_when_disabled
        self._tooltip_provider = tooltip_provider
        self._cursor_global_position = QCursor.pos()
        self._tooltip: _FluentToolTip | None = None
        self._watched_widget_ids: set[int] = set()

    @property
    def show_delay_ms(self) -> int:
        """Return the configured QFluent hover delay in milliseconds."""

        return self._show_delay_ms

    def setToolTipDelay(self, delay: int) -> None:  # noqa: N802
        """Update QFluent's delay and the adapter's observable configuration."""

        self._show_delay_ms = delay
        super().setToolTipDelay(delay)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Update dynamic content and delegate display ownership to QFluent."""

        event_type = event.type()
        if event_type in {
            QEvent.Type.Enter,
            QEvent.Type.MouseMove,
            QEvent.Type.ToolTip,
        }:
            self._cursor_global_position = _event_global_position(watched, event)
            self._refresh_dynamic_tooltip(watched, event)
        if event_type == QEvent.Type.Wheel:
            self.hideToolTip()
        return bool(super().eventFilter(watched, event))

    def showToolTip(self) -> None:  # noqa: N802
        """Show QFluent's tooltip and optionally move it beside the cursor."""

        if not self._canShowToolTip():
            return
        if self._tooltip is None and self._canShowToolTip():
            self._tooltip = self._createToolTip()
        super().showToolTip()
        tooltip = self._tooltip
        if tooltip is None:
            return
        _configure_tooltip_bounds(tooltip)
        tooltip.adjustSize()
        if self._cursor_anchor:
            tooltip.move(
                cursor_tooltip_position(
                    cursor_global_pos=self._cursor_global_position,
                    tooltip_size=tooltip.size(),
                    offset=self._cursor_offset,
                )
            )

    def hide_tooltip(self) -> None:
        """Expose the app's snake-case lifecycle API over QFluent."""

        self.hideToolTip()

    def show_tooltip(self) -> None:
        """Expose the app's snake-case display API over QFluent."""

        self.showToolTip()

    def _createToolTip(self) -> _FluentToolTip:  # noqa: N802
        """Create QFluent's tooltip and apply the shared wrapping contract."""

        tooltip = cast(_FluentToolTip, super()._createToolTip())
        _configure_tooltip_bounds(tooltip)
        return tooltip

    def _canShowToolTip(self) -> bool:  # noqa: N802
        """Allow explicitly configured explanatory help on disabled controls."""

        owner = cast(QWidget, self.parent())
        return bool(
            owner.isWidgetType()
            and owner.toolTip()
            and (owner.isEnabled() or self._show_when_disabled)
        )

    def _refresh_dynamic_tooltip(self, watched: QObject, event: QEvent) -> None:
        """Resolve event-aware content through the single tooltip property owner."""

        if self._tooltip_provider is None:
            return
        owner = cast(QWidget, self.parent())
        set_fluent_tooltip_text(owner, self._tooltip_provider(watched, event) or "")

    def _forget_watched_widget(self, watched_id: int) -> None:
        """Release one destroyed widget identity from idempotent installation state."""

        self._watched_widget_ids.discard(watched_id)


def set_fluent_tooltip_text(target: ToolTipTarget, text: str) -> None:
    """Set tooltip text and ensure QWidget targets use QFluent presentation."""

    if isinstance(target, QWidget):
        QWidget.setToolTip(target, str(text))
        if not isinstance(
            getattr(target, _FILTER_ATTRIBUTE, None), FluentToolTipFilter
        ):
            ensure_fluent_tooltip_filter(target)
        return
    target.setToolTip(str(text))


def ensure_fluent_tooltip_filter(
    owner: QWidget,
    *watched_widgets: QWidget,
    show_delay_ms: int = 300,
    position: ToolTipPosition = ToolTipPosition.TOP,
    cursor_anchor: bool = False,
    cursor_offset: QPoint | None = None,
    show_when_disabled: bool = False,
    tooltip_provider: ToolTipProvider | None = None,
) -> FluentToolTipFilter:
    """Return and configure the sole QFluent tooltip filter for one owner."""

    existing = getattr(owner, _FILTER_ATTRIBUTE, None)
    if isinstance(existing, FluentToolTipFilter):
        tooltip_filter = existing
        tooltip_filter.setToolTipDelay(show_delay_ms)
        tooltip_filter.position = position
        tooltip_filter._cursor_anchor = cursor_anchor
        tooltip_filter._cursor_offset = cursor_offset or _DEFAULT_CURSOR_OFFSET
        tooltip_filter._show_when_disabled = show_when_disabled
        tooltip_filter._tooltip_provider = tooltip_provider
    else:
        tooltip_filter = FluentToolTipFilter(
            owner,
            show_delay_ms=show_delay_ms,
            position=position,
            cursor_anchor=cursor_anchor,
            cursor_offset=cursor_offset,
            show_when_disabled=show_when_disabled,
            tooltip_provider=tooltip_provider,
        )
        setattr(owner, _FILTER_ATTRIBUTE, tooltip_filter)
    for watched in watched_widgets or (owner,):
        watched.setMouseTracking(cursor_anchor or tooltip_provider is not None)
        watched_id = id(watched)
        if watched_id not in tooltip_filter._watched_widget_ids:
            watched.installEventFilter(tooltip_filter)
            tooltip_filter._watched_widget_ids.add(watched_id)
            watched.destroyed.connect(
                lambda _object=None, watched_id=watched_id: (
                    tooltip_filter._forget_watched_widget(watched_id)
                )
            )
    return tooltip_filter


def cursor_tooltip_position(
    *,
    cursor_global_pos: QPoint,
    tooltip_size: QSize,
    offset: QPoint | None = None,
    screen_geometry: QRect | None = None,
) -> QPoint:
    """Return a cursor-relative tooltip position clamped to the active screen."""

    geometry = screen_geometry or _screen_geometry(cursor_global_pos)
    desired = cursor_global_pos + (offset or _DEFAULT_CURSOR_OFFSET)
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


def _event_global_position(watched: QObject, event: QEvent) -> QPoint:
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


def _configure_tooltip_bounds(tooltip: object) -> None:
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


__all__ = [
    "FluentToolTipFilter",
    "ToolTipPosition",
    "ToolTipProvider",
    "ToolTipTarget",
    "cursor_tooltip_position",
    "ensure_fluent_tooltip_filter",
    "set_fluent_tooltip_text",
]
